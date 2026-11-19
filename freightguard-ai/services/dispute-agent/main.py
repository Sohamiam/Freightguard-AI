"""FastAPI wrapper: start a dispute run, list pending reviews, resume with approve/reject/edit."""
from __future__ import annotations
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langgraph.types import Command
sys.path.insert(0, str(Path(__file__).parent))
from graph import build_graph, make_checkpointer
from rag import MemoryHybridStore, PgHybridStore, chunk_msa
from audit_chain import AuditChain
import os

app = FastAPI(title="FreightGuard Dispute Agent")
audit = AuditChain(); outbox: list[dict] = []
store = PgHybridStore(os.environ["DATABASE_URL"]) if os.getenv("DATABASE_URL") else MemoryHybridStore()
for p in (Path(__file__).parents[2] / "data/seed/msa").glob("*.md"):
    store.upsert(chunk_msa(p.stem.replace("_MSA", "").replace("_", " "), p.read_text()))
graph = build_graph(store, make_checkpointer(), audit, send=outbox.append)

class Run(BaseModel):
    thread_id: str; invoice: dict; card: dict; actual_detention_hrs: str; ml: dict = {}
class Review(BaseModel):
    action: str; reviewer: str = "ops"; edited_draft: str | None = None

@app.post("/disputes")
def start(r: Run):
    cfg = {"configurable": {"thread_id": r.thread_id}}
    out = graph.invoke({"invoice": r.invoice, "card": r.card, "actual_detention_hrs": r.actual_detention_hrs, "ml": r.ml}, cfg)
    return {"interrupted": "__interrupt__" in out, "state": {k: v for k, v in out.items() if k != "__interrupt__"},
            "interrupt": [i.value for i in out.get("__interrupt__", [])]}

@app.post("/disputes/{thread_id}/review")
def review(thread_id: str, r: Review):
    if r.action not in {"approve", "reject", "edit"}: raise HTTPException(400, "bad action")
    out = graph.invoke(Command(resume=r.model_dump()), {"configurable": {"thread_id": thread_id}})
    sent = out.get("status") == "sent"
    return {"status": out.get("status"), "message": outbox[-1] if sent and outbox else None}

@app.get("/audit/verify")
def verify(): ok, at = audit.verify(); return {"valid": ok, "broken_at": at, "entries": len(audit.entries)}
