"""Train LogReg baseline, SMOTE+XGBoost, Isolation Forest; tune threshold on cost-sensitive PR curve; save artifacts."""
from __future__ import annotations
import json, sys
from pathlib import Path
import joblib, numpy as np, pandas as pd
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, f1_score, precision_recall_curve
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier
sys.path.insert(0, str(Path(__file__).parent))
from features import FEATURES, engineer

def tune_threshold(y, p, avg_recovery=420.0, review_cost=18.0) -> float:
    """Pick threshold maximizing expected net value: recovered $ for TPs minus ops cost per flagged invoice."""
    prec, rec, thr = precision_recall_curve(y, p)
    pos = y.sum(); best, best_t = -1e18, 0.5
    for pr, rc, t in zip(prec[:-1], rec[:-1], thr):
        tp = rc * pos; flagged = tp / pr if pr > 0 else 0
        val = tp * avg_recovery - flagged * review_cost
        if val > best: best, best_t = val, float(t)
    return best_t

def train(csv: str, out: str, seed: int = 42) -> dict:
    df = engineer(pd.read_csv(csv)); X, y = df[FEATURES], df.is_overbilled
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, stratify=y, random_state=seed)
    Xtr2, Xval, ytr2, yval = train_test_split(Xtr, ytr, test_size=0.25, stratify=ytr, random_state=seed)
    lr = Pipeline([("sc", StandardScaler()), ("sm", SMOTE(random_state=seed, k_neighbors=3)),
                   ("m", LogisticRegression(max_iter=2000))])
    xgb = Pipeline([("sm", SMOTE(random_state=seed, k_neighbors=3)),
                    ("m", XGBClassifier(n_estimators=250, max_depth=4, learning_rate=0.05, subsample=0.9,
                                        eval_metric="aucpr", random_state=seed))])
    iso = IsolationForest(n_estimators=200, contamination=0.04, random_state=seed)
    lr.fit(Xtr2, ytr2); xgb.fit(Xtr2, ytr2); iso.fit(Xtr2)
    thr = tune_threshold(yval.values, xgb.predict_proba(Xval)[:, 1])
    res = {}
    for name, p in {"logreg": lr.predict_proba(Xte)[:, 1], "xgboost": xgb.predict_proba(Xte)[:, 1],
                    "isolation_forest": -iso.score_samples(Xte)}.items():
        t = thr if name == "xgboost" else (0.5 if name == "logreg" else np.quantile(p, 0.96))
        res[name] = {"pr_auc": float(average_precision_score(yte, p)), "f1": float(f1_score(yte, p >= t)),
                     "precision_at_k": float(yte.values[np.argsort(-p)[:int(yte.sum())]].mean())}
    Path(out).mkdir(parents=True, exist_ok=True)
    joblib.dump({"xgb": xgb, "lr": lr, "iso": iso, "threshold": thr, "features": FEATURES}, Path(out) / "model.joblib")
    (Path(out) / "metrics.json").write_text(json.dumps({"threshold": thr, "test": res}, indent=2))
    return {"threshold": thr, "test": res}

if __name__ == "__main__":
    print(json.dumps(train("data/seed/historical_invoices.csv", "services/ml-risk-engine/artifacts"), indent=2))
