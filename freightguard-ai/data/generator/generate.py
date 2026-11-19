"""Synthetic data + chaos generator: rate cards (xlsx), MSAs (md), historical labeled invoices (csv), sample PDFs."""
from __future__ import annotations
import argparse, random
from pathlib import Path
import numpy as np, pandas as pd

CARRIERS = {"Apex Freight": 0.00, "BlueLine Logistics": 0.01, "Cobalt Carriers": 0.02, "Delta Haul": 0.00, "Evergreen Transport": 0.03}
LANES = {"CHI-DAL": 925, "LAX-PHX": 373, "ATL-MIA": 662, "SEA-POR": 173, "NYC-BOS": 215, "DEN-KCY": 600, "HOU-SAT": 197, "MEM-NSH": 210}
TYPOLOGIES = ["duplicate_invoice", "unapproved_fuel_surcharge", "detention_miscalc", "rate_card_drift", "accessorial_stacking"]

def build_rate_cards(rng) -> pd.DataFrame:
    rows = []
    for c in CARRIERS:
        for lane, miles in LANES.items():
            rows.append(dict(carrier=c, lane=lane, miles=miles,
                             rate_per_mile=round(rng.uniform(2.05, 3.10), 2),
                             fuel_surcharge_pct=round(rng.choice([0.08, 0.10, 0.12]), 2),
                             detention_rate_per_hr=float(rng.choice([55, 65, 75])),
                             detention_free_hrs=2.0))
    return pd.DataFrame(rows)

def write_msas(out: Path, cards: pd.DataFrame):
    d = out / "msa"; d.mkdir(parents=True, exist_ok=True)
    for c, g in cards.groupby("carrier"):
        fsc = g.fuel_surcharge_pct.iloc[0]; det = g.detention_rate_per_hr.iloc[0]
        (d / f"{c.replace(' ', '_')}_MSA.md").write_text(f"""# Master Service Agreement - {c}

## 4. Linehaul Rates
4.1 Linehaul charges are billed per mile at the rates in Schedule A (rate card). No other rate applies unless amended in writing.

## 5. Fuel Surcharge
5.1 Fuel surcharge is fixed at {fsc*100:.0f}% of linehaul. Surcharge code FSC-01 is the only approved fuel charge.
5.2 Any additional or indexed fuel surcharge requires prior written approval from Shipper.

## 6. Detention
6.1 The first 2.0 free hours at each stop are not billable.
6.2 Detention beyond free time is billed at ${det:.2f} per hour, prorated to the quarter hour, based on timestamped gate logs.

## 7. Duplicate Billing
7.1 Re-issued invoices for a previously billed PRO number are not payable and must be credited.

## 8. Disputes
8.1 Shipper may dispute any overcharge within 90 days of invoice date. Carrier shall issue a credit within 30 days.
""")

def build_history(cards: pd.DataFrame, n: int, rate: float, rng) -> pd.DataFrame:
    rows = []
    pro = 100000
    for i in range(n):
        r = cards.iloc[rng.integers(len(cards))]
        pro += int(rng.integers(1, 5))
        miles = int(r.miles * rng.uniform(0.98, 1.04))
        det_hrs = float(rng.choice([0, 0, 0, 1.5, 2.5, 3, 4.5, 6], p=[.3, .2, .15, .1, .1, .06, .06, .03]))
        lh = r.rate_per_mile * miles
        fsc = lh * r.fuel_surcharge_pct
        bill_hrs = max(0.0, det_hrs - r.detention_free_hrs)
        det = bill_hrs * r.detention_rate_per_hr
        typ = "none"
        if rng.random() < rate:
            typ = str(rng.choice(TYPOLOGIES))
            if typ == "unapproved_fuel_surcharge": fsc *= rng.uniform(1.15, 1.6)
            elif typ == "detention_miscalc": det += rng.uniform(1.0, 3.5) * r.detention_rate_per_hr; bill_hrs = det / r.detention_rate_per_hr
            elif typ == "rate_card_drift": lh *= rng.uniform(1.03, 1.12)
            elif typ == "accessorial_stacking": lh *= rng.uniform(1.015, 1.03); fsc *= rng.uniform(1.05, 1.15)
        # benign noise: legit rounding and small mileage re-routes
        lh *= rng.normal(1.0, 0.002); 
        total = lh + fsc + det
        rows.append(dict(invoice_id=f"INV-{i:06d}", pro_number=f"PRO{pro}", carrier=r.carrier, lane=r.lane, miles=miles,
                         contract_rate_per_mile=r.rate_per_mile, allowed_fsc_pct=r.fuel_surcharge_pct,
                         detention_rate=r.detention_rate_per_hr, actual_detention_hrs=det_hrs, billed_detention_hrs=round(bill_hrs + min(det_hrs, r.detention_free_hrs), 2) if typ == "detention_miscalc" else det_hrs,
                         billed_linehaul=round(lh, 2), billed_fsc=round(fsc, 2), billed_detention=round(det, 2),
                         billed_total=round(total, 2), carrier_dispute_history=float(rng.beta(1, 8)),
                         is_overbilled=int(typ != "none"), typology=typ))
    df = pd.DataFrame(rows)
    # duplicates: re-issue with new invoice id, same PRO + amount
    dup_idx = df.index[df.typology == "duplicate_invoice"]
    originals = df[df.typology != "duplicate_invoice"].sample(len(dup_idx), random_state=1, replace=True).reset_index(drop=True)
    for k, idx in enumerate(dup_idx):
        o = originals.iloc[k]
        keep = df.loc[idx, ["invoice_id", "typology", "is_overbilled"]].copy()
        for col in df.columns:
            if col not in ("invoice_id", "typology", "is_overbilled"): df.at[idx, col] = o[col]
        df.loc[idx, ["invoice_id", "typology", "is_overbilled"]] = keep.values
    df["fingerprint_count"] = df.groupby(["carrier", "pro_number", "billed_total"]).invoice_id.transform("count")
    return df

def write_sample_pdfs(out: Path, df: pd.DataFrame, k: int = 20):
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    d = out / "pdf_invoices"; d.mkdir(parents=True, exist_ok=True)
    for _, r in df[df.is_overbilled == 1].head(k).iterrows():
        c = canvas.Canvas(str(d / f"{r.invoice_id}.pdf"), pagesize=letter)
        y = 740
        c.setFont("Helvetica-Bold", 16); c.drawString(50, y, f"{r.carrier} - FREIGHT INVOICE"); y -= 30
        c.setFont("Helvetica", 11)
        for line in [f"Invoice: {r.invoice_id}   PRO: {r.pro_number}", f"Lane: {r.lane}   Miles: {r.miles}",
                     f"Linehaul: ${r.billed_linehaul:,.2f}", f"Fuel Surcharge (FSC): ${r.billed_fsc:,.2f}",
                     f"Detention ({r.billed_detention_hrs} hrs): ${r.billed_detention:,.2f}", f"TOTAL DUE: ${r.billed_total:,.2f}"]:
            c.drawString(50, y, line); y -= 20
        c.save()

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=1800)
    ap.add_argument("--rate", type=float, default=0.045); ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="data/seed"); a = ap.parse_args()
    rng = np.random.default_rng(a.seed); random.seed(a.seed)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    cards = build_rate_cards(rng)
    with pd.ExcelWriter(out / "rate_cards.xlsx") as xw:
        for c, g in cards.groupby("carrier"): g.to_excel(xw, sheet_name=c[:31], index=False)
    write_msas(out, cards)
    df = build_history(cards, a.n, a.rate, rng)
    df.to_csv(out / "historical_invoices.csv", index=False)
    write_sample_pdfs(out, df)
    print(f"{len(df)} invoices, overbilling rate {df.is_overbilled.mean():.2%}\n{df.typology.value_counts().to_dict()}")

if __name__ == "__main__":
    main()
