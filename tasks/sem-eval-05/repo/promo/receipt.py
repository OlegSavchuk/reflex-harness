"""Receipts."""
from promo.cart import cart_total
from promo.rules.discount import Discount


def receipt(lines: list[tuple[str, int, int]], discounts: list[Discount]) -> str:
    return f"TOTAL {cart_total(lines, discounts) / 100:.2f}"
