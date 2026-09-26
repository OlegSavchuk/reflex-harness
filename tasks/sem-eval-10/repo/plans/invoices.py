"""Invoice schedules."""
from datetime import date

from plans.renewals import renewal_dates


def invoice_schedule(start: date, every_months: int, count: int, amount_cents: int) -> list[tuple[str, int]]:
    return [(d.isoformat(), amount_cents) for d in renewal_dates(start, every_months, count)]
