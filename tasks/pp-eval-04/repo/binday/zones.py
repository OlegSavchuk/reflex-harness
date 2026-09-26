"""Collection zones. North collects on Monday, East on Tuesday, South on Thursday, West on Friday."""

ZONE_DAY = {"north": 0, "east": 1, "south": 4, "west": 4}   # weekday numbers, Monday = 0


def collection_weekday(zone: str) -> int:
    return ZONE_DAY[zone]
