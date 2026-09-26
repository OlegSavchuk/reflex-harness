"""Drones. Telemetry reports airspeed in metres per second."""
from dispatch.routing.eta import eta_minutes


def drone_eta(distance_km: float, airspeed_ms: float) -> int:
    return eta_minutes(distance_km, airspeed_ms)
