"""OCR eval: field-level exact match and F1 vs ground truth. Uses Gemini when GEMINI_API_KEY is set,
otherwise a regex text-layer baseline (pypdf) so the harness always runs. The report states which backend ran."""
import json, os, re, sys
from decimal import Decimal
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/etl-ocr"))
FIELDS = ["invoice_id", "pro_number", "carrier", "lane", "miles", "linehaul", "fuel_surcharge", "detention_charge", "total"]

def ground_truth(df, ids):
    out = {}
    for _, r in df[df.invoice_id.isin(ids)].iterrows():
        out[r.invoice_id] = dict(invoice_id=r.invoice_id, pro_number=r.pro_number, carrier=r.carrier, lane=r.lane, miles=str(r.miles),
                                 linehaul=f"{r.billed_linehaul:.2f}", fuel_surcharge=f"{r.billed_fsc:.2f}",
                                 detention_charge=f"{r.billed_detention:.2f}", total=f"{r.billed_total:.2f}")
    return out

def regex_extract(pdf: Path) -> dict:
    from pypdf import PdfReader
    t = "\n".join(p.extract_text() for p in PdfReader(str(pdf)).pages)
    g = lambda pat: (re.search(pat, t) or [None, None])[1]
    money = lambda pat: (g(pat) or "").replace(",", "")
    return dict(invoice_id=g(r"Invoice:\s*(\S+)"), pro_number=g(r"PRO:\s*(\S+)"), carrier=g(r"^(.*?) - FREIGHT"),
                lane=g(r"Lane:\s*(\S+)"), miles=g(r"Miles:\s*(\d+)"), linehaul=money(r"Linehaul:\s*\$([\d,\.]+)"),
                fuel_surcharge=money(r"\(FSC\):\s*\$([\d,\.]+)"), detention_charge=money(r"hrs\):\s*\$([\d,\.]+)"), total=money(r"TOTAL DUE:\s*\$([\d,\.]+)"))

def norm(v):
    try: return str(Decimal(str(v)).quantize(Decimal("0.01")))
    except Exception: return str(v).strip() if v is not None else None

def run(out_dir: Path) -> dict:
    df = pd.read_csv(ROOT / "data/seed/historical_invoices.csv"); pdfs = sorted((ROOT / "data/seed/pdf_invoices").glob("*.pdf"))
    gt = ground_truth(df, {p.stem for p in pdfs}); backend = "regex-baseline"; pred = {}
    if os.getenv("GEMINI_API_KEY"):
        from ocr import extract; backend = "gemini"; seen = set()
        for p in pdfs:
            r = extract(p, seen, ROOT / "data/dlq"); pred[p.stem] = ({k: r["invoice"].get(k) for k in FIELDS} if r else {})
    else:
        for p in pdfs: pred[p.stem] = regex_extract(p)
    tp = fp = fn = 0; exact = 0
    for i, truth in gt.items():
        ok = True
        for f in FIELDS:
            a, b = norm(pred[i].get(f)), norm(truth[f])
            if a == b: tp += 1
            else: ok = False; fn += 1; fp += 1 if a else 0
        exact += ok
    p_, r_ = tp / max(tp + fp, 1), tp / max(tp + fn, 1)
    res = {"backend": backend, "documents": len(gt), "doc_exact_match": exact / len(gt), "field_precision": p_, "field_recall": r_,
           "field_f1": 2 * p_ * r_ / max(p_ + r_, 1e-9)}
    out_dir.mkdir(exist_ok=True); (out_dir / "ocr_eval.json").write_text(json.dumps(res, indent=2)); return res

if __name__ == "__main__": print(json.dumps(run(ROOT / "evals/reports"), indent=2))
