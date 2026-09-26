"""Invoices. Unit prices and all invoice amounts are integer cents."""
from billing.models import LineItem
from billing.tax import apply_tax


def subtotal_cents(items: list[LineItem]) -> int:
    return sum(item.quantity * item.unit_price for item in items)


def invoice_total_cents(items: list[LineItem], tax_rate: float) -> int:
    return apply_tax(subtotal_cents(items), tax_rate)


def format_cents(cents: int) -> str:
    return f"${cents // 100}.{cents % 100:02d}"


def invoice_summary(invoice_id: str, items: list[LineItem], tax_rate: float) -> dict:
    total = invoice_total_cents(items, tax_rate)
    return {"invoice_id": invoice_id, "lines": len(items),
            "total_cents": total, "total_display": format_cents(total)}
