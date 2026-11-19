"""Unified scorecard: OCR + ML + RAG/agent -> Markdown + JSON."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import ml_eval, ocr_eval, rag_agent_eval
rep = Path(__file__).parent / "reports"; rep.mkdir(exist_ok=True)
card = {"ocr": ocr_eval.run(rep), "ml": ml_eval.run(rep), "rag_agent": rag_agent_eval.run(rep)}
(rep / "scorecard.json").write_text(json.dumps(card, indent=2))
md = ["# FreightGuard Scorecard", "", f"**OCR** ({card['ocr']['backend']}): doc exact-match {card['ocr']['doc_exact_match']:.2%}, field F1 {card['ocr']['field_f1']:.3f}", "",
      "**ML** (test split)", "", "| model | PR-AUC | F1 | P@K |", "|---|---|---|---|"]
md += [f"| {m} | {v['pr_auc']:.3f} | {v['f1']:.3f} | {v['precision_at_k']:.3f} |" for m, v in card["ml"]["test"].items()]
a = card["rag_agent"]
md += ["", "**Agent**", "", f"- detection precision {a['detection_precision']:.3f}, recall {a['detection_recall']:.3f}", f"- math within $15: {a['math_correctness_within_$15']:.3f}; citation accuracy: {a['citation_accuracy']:.3f}",
       f"- audit chain valid: {a['audit_chain_valid']}", f"- est. tokens/1000 disputes: {a['est_tokens_per_1000_disputes']}; est. USD/1000: ${a['est_usd_per_1000_disputes']}", f"- {a['note']}"]
(rep / "scorecard.md").write_text("\n".join(md)); print("\n".join(md))
