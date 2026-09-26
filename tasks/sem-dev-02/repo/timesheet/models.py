"""Timesheet data types."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Entry:
    project: str
    duration: str
    billable: bool = True
