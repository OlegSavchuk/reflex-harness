from flagship.app import banner
from flagship.flags import enabled_features


def test_false_values_are_off():
    env = {"FEATURE_BETA": "true", "FEATURE_DARK": "false", "FEATURE_X": "0", "HOME": "/root"}
    assert enabled_features(env) == ["beta"]


def test_banner():
    assert banner({"FEATURE_SEARCH": "yes", "FEATURE_ADS": "off"}) == "features: search"


def test_no_flags():
    assert enabled_features({}) == []
