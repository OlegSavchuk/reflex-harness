"""Reminder messages."""
from datetime import date

from binday.schedule import next_collection

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]


def reminder_text(zone: str, today: date) -> str:
    d = next_collection(zone, today)
    return f"Put your bins out for {DAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]}"
