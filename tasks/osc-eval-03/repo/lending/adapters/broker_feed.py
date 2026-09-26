"""Broker feed. Each row quotes the annual rate as a percentage (4.25 means 4.25%)."""
from lending.core.interest import monthly_payment


def quote_from_feed(row: dict) -> float:
    return monthly_payment(row["amount"], row["rate_pct"], row["months"])
