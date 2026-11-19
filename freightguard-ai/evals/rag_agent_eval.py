"""Agent eval over the labeled history: math correctness, citation accuracy, detection precision/recall, token and USD cost per 1,000 invoices.
Token counts are ESTIMATES (chars/4) unless an LLM callable reports usage; prices are configurable constants, not measured spend."""
import json, sys
from decimal import Decimal
from pathlib import Path
import pandas as pd
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
ROOT = Path(__file__).resolve().parents[1]
for p in ("services/dispute-agent", "services/mcp-tools"): sys.path.insert(0, str(ROOT / p))
from graph import build_graph
import rag
from rag import MemoryHybridStore, chunk_msa
from audit_chain import AuditChain
from billing import expected_charges, RateCard

PRICE_IN, PRICE_OUT = 0.10 / 1e6, 0.40 / 1e6   # USD per token, Gemini Flash-class assumption
EXPECTED_CLAUSE = {"UNAPPROVED_FSC": {"5.1", "5.2"}, "DETENTION_MISCALC": {"6.1", "6.2"}, "RATE_DRIFT": {"4.1"}, "DUPLICATE": {"7.1"}}

def run(out_dir: Path, limit: int = 600) -> dict:
    df = pd.read_csv(ROOT / "data/seed/historical_invoices.csv")
    df["dup"] = df.groupby(["carrier", "pro_number", "billed_total"]).cumcount() > 0
    sample = pd.concat([df[df.is_overbilled == 1], df[df.is_overbilled == 0].head(limit)]).reset_index(drop=True)
    store = MemoryHybridStore()
    for p in (ROOT / "data/seed/msa").glob("*.md"): store.upsert(chunk_msa(p.stem.replace("_MSA", "").replace("_", " "), p.read_text()))
    audit = AuditChain(); g = build_graph(store, MemorySaver(), audit, send=lambda m: None)
    tp = fp = fn = 0; math_ok = math_n = cite_ok = cite_n = 0; tin = tout = 0
    for _, r in sample.iterrows():
        card = dict(carrier=r.carrier, lane=r.lane, rate_per_mile=str(r.contract_rate_per_mile), fuel_surcharge_pct=str(r.allowed_fsc_pct), detention_rate_per_hr=str(r.detention_rate))
        inv = dict(invoice_id=r.invoice_id, carrier=r.carrier, lane=r.lane, miles=str(r.miles), linehaul=str(r.billed_linehaul), fuel_surcharge=str(r.billed_fsc),
                   detention_hours=str(r.billed_detention_hrs), detention_charge=str(r.billed_detention))
        cfg = {"configurable": {"thread_id": r.invoice_id}}
        out = g.invoke({"invoice": inv, "card": card, "actual_detention_hrs": str(r.actual_detention_hrs), "ml": {"duplicate": bool(r.dup)}}, cfg)
        flagged = "__interrupt__" in out
        if flagged and r.is_overbilled: tp += 1
        elif flagged: fp += 1
        elif r.is_overbilled: fn += 1
        if flagged:
            tin += len(out["draft"]) // 4 + sum(len(c) for c in out["clauses"]) // 4 + 150; tout += len(out["draft"]) // 4
            if r.typology not in ("duplicate_invoice",):
                e = expected_charges(RateCard(**{**card, "fuel_surcharge_pct": Decimal(card["fuel_surcharge_pct"])}), Decimal(str(r.miles)), Decimal(str(r.actual_detention_hrs)))
                true_over = Decimal(str(r.billed_total)) - e["total"]; found = sum(Decimal(f["overcharge"]) for f in out["findings"] if f["code"] != "DUPLICATE")
                if r.is_overbilled: math_n += 1; math_ok += abs(true_over - found) <= Decimal("15")
            for f in out["findings"]:
                cite_n += 1; cite_ok += any(c.split(":")[1] in EXPECTED_CLAUSE[f["code"]] for c in out["citations"])
            g.invoke(Command(resume={"action": "approve", "reviewer": "eval"}), cfg)
    n = len(sample); scale = 1000 / max(tp + fp, 1)
    res = {"invoices_evaluated": n, "detection_precision": tp / max(tp + fp, 1), "detection_recall": tp / max(tp + fn, 1),
           "math_correctness_within_$15": math_ok / max(math_n, 1), "citation_accuracy": cite_ok / max(cite_n, 1),
           "audit_chain_valid": audit.verify()[0], "est_tokens_per_1000_disputes": {"input": int(tin * scale), "output": int(tout * scale)},
           "est_usd_per_1000_disputes": round((tin * PRICE_IN + tout * PRICE_OUT) * scale, 4),
           "reranker_backend": rag.RERANKER_BACKEND, "note": "Deterministic template drafter (no LLM) in this run; token/USD figures are estimates."}
    out_dir.mkdir(exist_ok=True); (out_dir / "rag_agent_eval.json").write_text(json.dumps(res, indent=2)); return res

if __name__ == "__main__": print(json.dumps(run(ROOT / "evals/reports"), indent=2))
