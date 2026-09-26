"""Running pace, shared by watch imports, manual entries and reports."""


def pace(distance_m: int, duration_s: int) -> str:
    """Pace as "m:ss /km" for `distance_m` metres covered in `duration_s` seconds."""
    if distance_m <= 0 or duration_s <= 0:
        raise ValueError("distance and duration must be positive")
    per_km = round(duration_s * 1000 / distance_m)
    return f"{per_km // 60}:{per_km % 60:02d} /km"
