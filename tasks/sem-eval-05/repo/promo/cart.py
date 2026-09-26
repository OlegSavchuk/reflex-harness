"""Cart totals in cents."""
from promo.rules.discount import Discount


def cart_total(lines: list[tuple[str, int, int]], discounts: list[Discount]) -> int:
    """Total in cents for (sku, unit_cents, qty) lines after per-SKU percentage discounts."""
    total = 0
    for sku, unit, qty in lines:
        pct = max((d.percent for d in discounts if d.applies_to(sku)), default=0)
        total += round(unit * qty * (100 - pct) / 100)
    return total
