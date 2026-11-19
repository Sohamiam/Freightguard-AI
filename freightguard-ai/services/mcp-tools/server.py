"""MCP server exposing deterministic billing tools to the LangGraph agent."""
from decimal import Decimal
from mcp.server.fastmcp import FastMCP
from billing import RateCard, InvoiceLines, audit_invoice, expected_charges

mcp = FastMCP("freightguard-tools")

@mcp.tool()
def calculate_expected_charges(rate_per_mile: str, fuel_surcharge_pct: str, detention_rate_per_hr: str,
                               miles: str, actual_detention_hrs: str, detention_free_hrs: str = "2") -> dict:
    """Return contract-correct linehaul, fuel surcharge, detention and total (Decimal-exact)."""
    card = RateCard(carrier="-", lane="-", rate_per_mile=Decimal(rate_per_mile),
                    fuel_surcharge_pct=Decimal(fuel_surcharge_pct),
                    detention_rate_per_hr=Decimal(detention_rate_per_hr),
                    detention_free_hrs=Decimal(detention_free_hrs))
    return {k: str(v) for k, v in expected_charges(card, Decimal(miles), Decimal(actual_detention_hrs)).items()}

@mcp.tool()
def verify_invoice(card: dict, invoice: dict, actual_detention_hrs: str) -> list[dict]:
    """Compare billed lines to contract; return findings with overcharge amounts."""
    f = audit_invoice(RateCard(**card), InvoiceLines(**invoice), Decimal(actual_detention_hrs))
    return [x.model_dump(mode="json") for x in f]

if __name__ == "__main__":
    mcp.run()
