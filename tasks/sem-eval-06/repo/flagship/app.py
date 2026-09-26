"""Startup banner."""
from flagship.flags import enabled_features


def banner(env: dict[str, str]) -> str:
    names = enabled_features(env)
    return "features: " + (", ".join(names) if names else "none")
