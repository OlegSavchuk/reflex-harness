"""Weekly summaries."""
from timesheet.billing import billable_hours
from timesheet.models import Entry


def weekly_summary(entries: list[Entry]) -> str:
    return f"{len(entries)} entries, {billable_hours(entries):.2f} billable hours"
