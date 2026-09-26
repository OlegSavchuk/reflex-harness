"""Tax calculation shared by invoicing and refunds."""


def apply_tax(amount_cents: int, rate: float) -> int:
    """Return amount_cents plus tax at `rate`, rounded to the nearest cent."""
    if not isinstance(amount_cents, int):
        raise TypeError(f"amount_cents must be int, got {type(amount_cents).__name__}")
    return round(amount_cents * (1 + rate))
