"""Feature flags from the environment."""
from flagship.env import parse_bool

PREFIX = "FEATURE_"


def enabled_features(env: dict[str, str]) -> list[str]:
    """Sorted names of features switched on through FEATURE_<NAME> variables."""
    return sorted(k[len(PREFIX):].lower() for k, v in env.items()
                  if k.startswith(PREFIX) and parse_bool(v))
