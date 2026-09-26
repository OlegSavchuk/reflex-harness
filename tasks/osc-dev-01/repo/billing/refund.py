"""Refunds. Unit prices and refund amounts are in dollars."""
from billing.models import LineItem
from billing.tax import apply_tax


def refund_total_dollars(items: list[LineItem], tax_rate: float,
                         restocking_fee: float = 0.0) -> float:
    gross = sum(item.quantity * item.unit_price for item in items)
    return round(apply_tax(gross, tax_rate) - restocking_fee, 2)


def refund_summary(order_id: str, items: list[LineItem], tax_rate: float,
                   restocking_fee: float = 0.0) -> dict:
    return {"order_id": order_id, "lines": len(items),
            "refund_dollars": refund_total_dollars(items, tax_rate, restocking_fee)}
