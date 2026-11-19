"""LangGraph dispute workflow with a durable HITL interrupt before any email is dispatched."""
from __future__ import annotations
import os, sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, TypedDict
import yaml
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services/mcp-tools")); sys.path.insert(0, str(Path(__file__).parent))
from billing import RateCard, InvoiceLines, audit_invoice
from audit_chain import AuditChain
from rag import rerank

DRAFT_PROMPT = yaml.safe_load((ROOT / "prompts/v1/dispute_drafter.yaml").read_text())
CLAUSE_FOR = {"UNAPPROVED_FSC": "fuel surcharge", "DETENTION_MISCALC": "detention free hours", "RATE_DRIFT": "linehaul rates schedule",
              "DUPLICATE": "duplicate billing"}

class State(TypedDict, total=False):
    invoice: dict; card: dict; actual_detention_hrs: str; ml: dict
    findings: list[dict]; citations: list[str]; clauses: list[str]
    draft: str; decision: dict; status: str

def build_graph(store, checkpointer, audit: AuditChain, llm: Callable[[str], str] | None = None, send: Callable[[dict], None] | None = None):
    def verify(s: State) -> dict[str, Any]:
        f = audit_invoice(RateCard(**s["card"]), InvoiceLines(**s["invoice"]), Decimal(s["actual_detention_hrs"]))
        findings = [x.model_dump(mode="json") for x in f]
        if s.get("ml", {}).get("duplicate"):
            findings.append({"code": "DUPLICATE", "billed": s["invoice"]["linehaul"], "expected": "0", "overcharge": s["invoice"]["linehaul"]})
        audit.append("agent", "verify", {"invoice": s["invoice"].get("invoice_id"), "findings": findings, "ml": s.get("ml")})
        return {"findings": findings}

    def route_after_verify(s: State) -> str: return "retrieve" if s["findings"] else "close_clean"

    def close_clean(s: State): audit.append("agent", "no_dispute", {}); return {"status": "clean"}

    def retrieve(s: State):
        cits, texts = [], []
        for f in s["findings"]:
            q = f'{f["code"]} {CLAUSE_FOR.get(f["code"], "")}'
            top = rerank(q, store.search(q, s["card"]["carrier"]), top_k=1)
            for c in top:
                if c.id not in cits: cits.append(c.id); texts.append(c.text)
        return {"citations": cits, "clauses": texts}

    def draft(s: State):
        findings = "; ".join(f'{f["code"]}: billed {f["billed"]}, expected {f["expected"]}, overcharge ${f["overcharge"]}' for f in s["findings"])
        prompt = DRAFT_PROMPT["user"].format(carrier=s["card"]["carrier"], invoice_id=s["invoice"].get("invoice_id"), findings=findings, clauses=" | ".join(s["clauses"]))
        if llm: body = llm(DRAFT_PROMPT["system"] + "\n\n" + prompt)
        else:
            lines = [f'- {f["code"]}: billed ${f["billed"]} vs contract ${f["expected"]} (overcharge ${f["overcharge"]})' for f in s["findings"]]
            body = (f'Re: Invoice {s["invoice"].get("invoice_id")} - billing dispute\n\nWe identified the following discrepancies:\n' + "\n".join(lines) +
                    "\n\nContract basis: " + ", ".join(c.split(":")[1] and "MSA " + c.split(":")[1] for c in s["citations"]) + ".\nPlease issue a credit within 30 days (MSA 8.1).")
        audit.append("agent", "draft", {"citations": s["citations"]})
        return {"draft": body}

    def human_review(s: State):
        d = interrupt({"draft": s["draft"], "findings": s["findings"], "citations": s["citations"]})  # durable pause
        audit.append("human", d["action"], {"reviewer": d.get("reviewer", "unknown")})
        return {"decision": d}

    def route_after_review(s: State) -> str:
        return {"approve": "dispatch", "edit": "dispatch", "reject": "close_rejected"}[s["decision"]["action"]]

    def dispatch(s: State):
        body = s["decision"].get("edited_draft") or s["draft"] if s["decision"]["action"] == "edit" else s["draft"]
        if send: send({"to": f'ap@{s["card"]["carrier"].lower().replace(" ", "")}.example', "body": body, "invoice_id": s["invoice"].get("invoice_id")})
        audit.append("agent", "dispatched", {"invoice": s["invoice"].get("invoice_id")})
        return {"status": "sent", "draft": body}

    def close_rejected(s: State): audit.append("agent", "closed_rejected", {}); return {"status": "rejected"}

    g = StateGraph(State)
    for n, f in [("verify", verify), ("close_clean", close_clean), ("retrieve", retrieve), ("draft", draft),
                 ("human_review", human_review), ("dispatch", dispatch), ("close_rejected", close_rejected)]: g.add_node(n, f)
    g.add_edge(START, "verify")
    g.add_conditional_edges("verify", route_after_verify, ["retrieve", "close_clean"])
    g.add_edge("retrieve", "draft"); g.add_edge("draft", "human_review")
    g.add_conditional_edges("human_review", route_after_review, ["dispatch", "close_rejected"])
    for n in ("close_clean", "dispatch", "close_rejected"): g.add_edge(n, END)
    return g.compile(checkpointer=checkpointer)

def make_checkpointer():
    """PostgresSaver when DATABASE_URL is set (durable across restarts); MemorySaver otherwise."""
    dsn = os.getenv("DATABASE_URL")
    if dsn:
        import psycopg
        from langgraph.checkpoint.postgres import PostgresSaver
        saver = PostgresSaver(psycopg.connect(dsn, autocommit=True, prepare_threshold=0)); saver.setup(); return saver
    from langgraph.checkpoint.memory import MemorySaver
    return MemorySaver()
