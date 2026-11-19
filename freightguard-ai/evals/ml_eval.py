"""ML eval: PR-AUC, F1, Precision@K for XGBoost vs LogReg vs Isolation Forest, written as Markdown + JSON."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "ml-risk-engine"))
from train import train

def run(out_dir: Path) -> dict:
    res = train(str(ROOT / "data/seed/historical_invoices.csv"), str(ROOT / "services/ml-risk-engine/artifacts"))
    md = ["# ML Eval", "", "| model | PR-AUC | F1 | Precision@K |", "|---|---|---|---|"]
    md += [f"| {m} | {v['pr_auc']:.3f} | {v['f1']:.3f} | {v['precision_at_k']:.3f} |" for m, v in res["test"].items()]
    md.append(f"\nTuned XGBoost threshold (cost-sensitive): {res['threshold']:.4f}")
    out_dir.mkdir(exist_ok=True); (out_dir / "ml_eval.md").write_text("\n".join(md)); (out_dir / "ml_eval.json").write_text(json.dumps(res, indent=2))
    return res

if __name__ == "__main__":
    print(json.dumps(run(ROOT / "evals" / "reports"), indent=2))
