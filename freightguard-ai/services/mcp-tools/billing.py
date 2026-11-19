"""Deterministic billing math. Pure functions, Decimal-based, no LLM involvement."""
from __future__ import annotations
import hashlib, json
from decimal import Decimal, ROUND_HALF_UP
from pydantic import BaseModel, Field

CENT = Decimal("0.01")

def money(x: Decimal | float | str) -> Decimal:
    return Decimal(str(x)).quantize(CENT, rounding=ROUND_HALF_UP)

class RateCard(BaseModel):
    carrier: str
    lane: str
    rate_per_mile: Decimal
    fuel_surcharge_pct: Decimal = Field(description="Contractually allowed FSC as fraction of linehaul")
    detention_rate_per_hr: Decimal
    detention_free_hrs: Decimal = Decimal("2")

class InvoiceLines(BaseModel):
    carrier: str
    lane: str
    miles: Decimal
    linehaul: Decimal
    fuel_surcharge: Decimal
    detention_hours: Decimal
    detention_charge: Decimal

class Finding(BaseModel):
    code: str
    billed: Decimal
    expected: Decimal
    overcharge: Decimal

def expected_charges(card: RateCard, miles: Decimal, actual_detention_hrs: Decimal) -> dict[str, Decimal]:
    linehaul = money(card.rate_per_mile * miles)
    fsc = money(linehaul * card.fuel_surcharge_pct)
    billable_hrs = max(Decimal("0"), actual_detention_hrs - card.detention_free_hrs)
    detention = money(billable_hrs * card.detention_rate_per_hr)
    return {"linehaul": linehaul, "fuel_surcharge": fsc, "detention": detention,
            "total": linehaul + fsc + detention}

def audit_invoice(card: RateCard, inv: InvoiceLines, actual_detention_hrs: Decimal,
                  tolerance: Decimal = Decimal("0.50"), tolerance_pct: Decimal = Decimal("0.01")) -> list[Finding]:
    """Flag a line when overcharge exceeds max(absolute tolerance, tolerance_pct of the expected amount)."""
    exp = expected_charges(card, inv.miles, actual_detention_hrs)
    pairs = {"RATE_DRIFT": (inv.linehaul, exp["linehaul"]),
             "UNAPPROVED_FSC": (inv.fuel_surcharge, exp["fuel_surcharge"]),
             "DETENTION_MISCALC": (inv.detention_charge, exp["detention"])}
    out = []
    for code, (billed, expected) in pairs.items():
        diff = money(billed - expected)
        if diff > max(tolerance, expected * tolerance_pct):
            out.append(Finding(code=code, billed=billed, expected=expected, overcharge=diff))
    return out

def content_hash(payload: dict | bytes) -> str:
    raw = payload if isinstance(payload, bytes) else json.dumps(payload, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()

def line_item_fingerprint(carrier: str, pro_number: str, total: Decimal) -> str:
    """Duplicate detection key independent of invoice number re-issue."""
    return content_hash({"c": carrier.upper().strip(), "p": pro_number.strip(), "t": str(money(total))})
