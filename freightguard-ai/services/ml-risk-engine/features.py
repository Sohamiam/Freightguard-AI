from __future__ import annotations
import pandas as pd

FEATURES = ["linehaul_delta_pct", "fsc_delta_pct", "detention_delta_hrs", "detention_delta_usd",
            "total_delta_pct", "is_repeat_fingerprint", "billed_vs_actual_hrs_ratio", "carrier_dispute_history",
            "detention_share", "fsc_share"]

def engineer(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    exp_lh = d.contract_rate_per_mile * d.miles
    exp_fsc = exp_lh * d.allowed_fsc_pct
    exp_det = (d.actual_detention_hrs - 2.0).clip(lower=0) * d.detention_rate
    exp_total = exp_lh + exp_fsc + exp_det
    d["linehaul_delta_pct"] = (d.billed_linehaul - exp_lh) / exp_lh
    d["fsc_delta_pct"] = (d.billed_fsc - exp_fsc) / exp_fsc.where(exp_fsc > 0, 1)
    d["detention_delta_hrs"] = d.billed_detention_hrs - d.actual_detention_hrs
    d["detention_delta_usd"] = d.billed_detention - exp_det
    d["total_delta_pct"] = (d.billed_total - exp_total) / exp_total
    d["is_repeat_fingerprint"] = (d.groupby(["carrier", "pro_number", "billed_total"]).cumcount() > 0).astype(int)
    d["billed_vs_actual_hrs_ratio"] = d.billed_detention_hrs / d.actual_detention_hrs.where(d.actual_detention_hrs > 0, 1)
    d["detention_share"] = d.billed_detention / d.billed_total
    d["fsc_share"] = d.billed_fsc / d.billed_total
    return d
