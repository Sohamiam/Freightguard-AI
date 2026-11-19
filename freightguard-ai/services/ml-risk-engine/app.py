"""FastAPI scoring service: XGBoost probability + Isolation Forest anomaly + SHAP top-3 drivers."""
from __future__ import annotations
import sys
from functools import lru_cache
from pathlib import Path
import joblib, pandas as pd, shap
from fastapi import FastAPI
from pydantic import BaseModel
sys.path.insert(0, str(Path(__file__).parent))
from features import engineer

ART = Path(__file__).parent / "artifacts" / "model.joblib"
app = FastAPI(title="FreightGuard Risk Engine")

class InvoiceIn(BaseModel):
    invoice_id: str; pro_number: str; carrier: str; lane: str; miles: float
    contract_rate_per_mile: float; allowed_fsc_pct: float; detention_rate: float
    actual_detention_hrs: float; billed_detention_hrs: float
    billed_linehaul: float; billed_fsc: float; billed_detention: float; billed_total: float
    carrier_dispute_history: float = 0.1

class Score(BaseModel):
    invoice_id: str; risk_probability: float; anomaly_score: float; flagged: bool
    top_drivers: list[dict]

@lru_cache
def bundle():
    b = joblib.load(ART); b["explainer"] = shap.TreeExplainer(b["xgb"].named_steps["m"]); return b

@app.get("/health")
def health(): return {"ok": ART.exists()}

@app.post("/score", response_model=list[Score])
def score(batch: list[InvoiceIn]):
    b = bundle(); df = engineer(pd.DataFrame([i.model_dump() for i in batch])); X = df[b["features"]]
    p = b["xgb"].predict_proba(X)[:, 1]; an = -b["iso"].score_samples(X)
    sv = b["explainer"].shap_values(X); out = []
    for i, inv in enumerate(batch):
        top = sorted(zip(b["features"], sv[i]), key=lambda t: -abs(t[1]))[:3]
        out.append(Score(invoice_id=inv.invoice_id, risk_probability=float(p[i]), anomaly_score=float(an[i]),
                         flagged=bool(p[i] >= b["threshold"]),
                         top_drivers=[{"feature": f, "shap": float(v), "value": float(X.iloc[i][f])} for f, v in top]))
    return out
