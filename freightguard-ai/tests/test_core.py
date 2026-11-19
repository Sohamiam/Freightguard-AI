import sys
from decimal import Decimal
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/mcp-tools"))
from billing import RateCard, InvoiceLines, expected_charges, audit_invoice, line_item_fingerprint
from audit_chain import AuditChain

CARD = RateCard(carrier="A", lane="X", rate_per_mile=Decimal("2.50"), fuel_surcharge_pct=Decimal("0.10"), detention_rate_per_hr=Decimal("60"))

def test_expected_charges_exact():
    e = expected_charges(CARD, Decimal("500"), Decimal("5"))
    assert e["linehaul"] == Decimal("1250.00") and e["fuel_surcharge"] == Decimal("125.00") and e["detention"] == Decimal("180.00")

def test_detects_unapproved_fsc_and_detention():
    inv = InvoiceLines(carrier="A", lane="X", miles=Decimal("500"), linehaul=Decimal("1250"), fuel_surcharge=Decimal("190"),
                       detention_hours=Decimal("5"), detention_charge=Decimal("300"))
    codes = {f.code: f.overcharge for f in audit_invoice(CARD, inv, Decimal("5"))}
    assert codes == {"UNAPPROVED_FSC": Decimal("65.00"), "DETENTION_MISCALC": Decimal("120.00")}

def test_clean_invoice_has_no_findings():
    inv = InvoiceLines(carrier="A", lane="X", miles=Decimal("500"), linehaul=Decimal("1250"), fuel_surcharge=Decimal("125"),
                       detention_hours=Decimal("5"), detention_charge=Decimal("180"))
    assert audit_invoice(CARD, inv, Decimal("5")) == []

def test_fingerprint_stable():
    assert line_item_fingerprint("a ", "P1", Decimal("10")) == line_item_fingerprint("A", "P1", Decimal("10.00"))

def test_audit_chain_detects_tampering():
    c = AuditChain(); c.append("ml", "score", {"p": 0.9}); c.append("human", "approve", {"id": 1})
    assert c.verify() == (True, None)
    c.entries[0]["payload"]["p"] = 0.1
    assert c.verify() == (False, 0)
