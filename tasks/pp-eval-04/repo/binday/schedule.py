"""Collection dates."""
from datetime import date, timedelta

from binday.zones import collection_weekday


def next_collection(zone: str, today: date) -> date:
    """The zone's next collection date strictly after `today` (never today itself)."""
    ahead = (collection_weekday(zone) - today.weekday()) % 7
    return today + timedelta(days=ahead)
