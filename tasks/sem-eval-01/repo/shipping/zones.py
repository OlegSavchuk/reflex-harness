"""Destination zones and per-kg rates."""

ZONES = {"US": "domestic", "CA": "north_america", "MX": "north_america",
         "GB": "europe", "DE": "europe", "FR": "europe", "JP": "asia", "AU": "oceania"}
RATES_PER_KG = {"domestic": 4.0, "north_america": 7.5, "europe": 11.0, "asia": 13.5,
                "oceania": 15.0, "rest_of_world": 18.0}


def zone_for(country_code: str) -> str:
    return ZONES.get(country_code.strip().lower(), "rest_of_world")


def rate_per_kg(zone: str) -> float:
    return RATES_PER_KG[zone]
