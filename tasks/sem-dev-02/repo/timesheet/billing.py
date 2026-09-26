"""Billable hours."""
from timesheet.models import Entry
from timesheet.parsing import parse_duration


def billable_hours(entries: list[Entry]) -> float:
    minutes = sum(parse_duration(e.duration) for e in entries if e.billable)
    return round(minutes / 60, 2)


def invoice_amount(entries: list[Entry], hourly_rate: float) -> float:
    return round(billable_hours(entries) * hourly_rate, 2)
