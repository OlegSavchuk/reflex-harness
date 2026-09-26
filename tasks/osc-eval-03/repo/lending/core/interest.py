"""Payment maths shared by mortgages, car loans and the broker feed."""


def monthly_payment(principal: float, annual_rate: float, months: int) -> float:
    """Level monthly payment; annual_rate is a fraction (0.05 means 5% a year)."""
    if not 0 <= annual_rate < 1:
        raise ValueError(f"annual_rate must be a fraction in [0, 1), got {annual_rate}")
    if months < 1:
        raise ValueError("months must be at least 1")
    r = annual_rate / 12
    if r == 0:
        return round(principal / months, 2)
    return round(principal * r / (1 - (1 + r) ** -months), 2)
