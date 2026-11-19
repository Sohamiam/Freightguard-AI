"""ETL service: scan a drop folder, OCR new PDFs, keep raw payloads, expose results. Hash-based idempotency + DLQ."""
from __future__ import annotations
import os, sys
from pathlib import Path
from fastapi import FastAPI
sys.path.insert(0, str(Path(__file__).parent))
from ocr import extract

app = FastAPI(title="FreightGuard ETL/OCR")
INBOX = Path(os.getenv("INBOX_DIR", "data/seed/pdf_invoices")); DLQ = Path(os.getenv("DLQ_DIR", "data/dlq"))
SEEN: set[str] = set(); RESULTS: list[dict] = []

@app.post("/ingest/scan")
def scan():
    new = []
    for pdf in sorted(INBOX.glob("*.pdf")):
        r = extract(pdf, SEEN, DLQ)
        if r: RESULTS.append(r); new.append(r)
    return {"new": len(new), "invoices": [r["invoice"] for r in new], "dlq": len(list(DLQ.glob("*.json"))) if DLQ.exists() else 0}

@app.get("/ingest/results")
def results(): return RESULTS
