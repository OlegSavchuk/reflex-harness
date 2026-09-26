"""Weekly income tax. Amounts are in cents."""

# Bands as (upper bound in cents, rate); None = no upper bound. 0% up to 500.00,
# 20% from 500.00 to 1,500.00, 35% above 1,500.00.
BANDS = [(50_000, 0.0), (150_000, 0.20), (None, 0.45)]


def income_tax(gross_cents: int) -> int:
    """Tax on one week's gross pay, band by band, rounded to the cent."""
    tax, lower = 0.0, 0
    for upper, rate in BANDS:
        top = gross_cents if upper is None else min(gross_cents, upper)
        if top <= lower:
            break
        tax += (top - lower) * rate
        lower = top
    return round(tax)
