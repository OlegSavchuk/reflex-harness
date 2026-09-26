from vault.quota import plan


def test_plan_small_areas():
    assert plan({"logs": 3, "cache": 10}) == {"logs": 1, "cache": 3}


def test_plan_odd_size():
    assert plan({"tmp": 7}) == {"tmp": 2}
