from __future__ import annotations
from decimal import Decimal
from pydantic import BaseModel, Field

class ExtractedInvoice(BaseModel):
    invoice_id: str
    pro_number: str
    carrier: str
    lane: str | None = None
    miles: Decimal | None = Field(default=None, ge=0)
    linehaul: Decimal = Field(ge=0)
    fuel_surcharge: Decimal = Field(default=Decimal("0"), ge=0)
    detention_hours: Decimal = Field(default=Decimal("0"), ge=0)
    detention_charge: Decimal = Field(default=Decimal("0"), ge=0)
    total: Decimal = Field(ge=0)
