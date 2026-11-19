import sys
from decimal import Decimal
from pathlib import Path
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
ROOT = Path(__file__).resolve().parents[1]
for p in ("services/dispute-agent", "services/mcp-tools"): sys.path.insert(0, str(ROOT / p))
from graph import build_graph
from rag import MemoryHybridStore, chunk_msa, rrf
from audit_chain import AuditChain

MSA = """## 5. Fuel Surcharge
5.1 Fuel surcharge is fixed at 10% of linehaul. Surcharge code FSC-01 is the only approved fuel charge.
5.2 Any additional or indexed fuel surcharge requires prior written approval from Shipper.
## 6. Detention
6.1 The first 2.0 free hours at each stop are not billable.
6.2 Detention beyond free time is billed at $60.00 per hour.
## 8. Disputes
8.1 Shipper may dispute any overcharge within 90 days. Carrier shall issue a credit within 30 days."""
CARD = dict(carrier="Apex Freight", lane="X", rate_per_mile="2.5", fuel_surcharge_pct="0.10", detention_rate_per_hr="60")
INV = dict(invoice_id="INV-1", carrier="Apex Freight", lane="X", miles="500", linehaul="1250", fuel_surcharge="190", detention_hours="5", detention_charge="180")

def mk():
    store = MemoryHybridStore(chunk_msa("Apex Freight", MSA)); audit = AuditChain(); sent = []
    return build_graph(store, MemorySaver(), audit, send=sent.append), audit, sent

def test_chunking_keeps_clause_numbers():
    assert {c.clause for c in chunk_msa("A", MSA)} >= {"5.1", "6.1", "8.1"}

def test_rrf_prefers_docs_ranked_by_both():
    assert rrf([["a", "b", "c"], ["b", "a", "d"]])[0][0] in {"a", "b"} and rrf([["a"], ["z", "a"]])[0][0] == "a"

def test_interrupt_blocks_send_until_approved_then_resumes():
    g, audit, sent = mk(); cfg = {"configurable": {"thread_id": "t1"}}
    out = g.invoke({"invoice": INV, "card": CARD, "actual_detention_hrs": "5", "ml": {}}, cfg)
    assert "__interrupt__" in out and sent == []
    assert any("5.1" in c or "5.2" in c for c in out["citations"])
    done = g.invoke(Command(resume={"action": "approve", "reviewer": "soham"}), cfg)
    assert done["status"] == "sent" and len(sent) == 1
    assert "$65.00" in sent[0]["body"]
    assert audit.verify() == (True, None)

def test_reject_never_sends():
    g, _, sent = mk(); cfg = {"configurable": {"thread_id": "t2"}}
    g.invoke({"invoice": INV, "card": CARD, "actual_detention_hrs": "5", "ml": {}}, cfg)
    assert g.invoke(Command(resume={"action": "reject"}), cfg)["status"] == "rejected" and sent == []

def test_clean_invoice_skips_review():
    g, _, sent = mk(); inv = {**INV, "fuel_surcharge": "125"}
    assert g.invoke({"invoice": inv, "card": CARD, "actual_detention_hrs": "5", "ml": {}}, {"configurable": {"thread_id": "t3"}})["status"] == "clean"
