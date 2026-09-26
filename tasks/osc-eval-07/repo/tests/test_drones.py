from dispatch.drones import drone_eta


def test_slow_drone():
    assert drone_eta(3, 4) == 13


def test_indoor_drone():
    assert drone_eta(1.5, 2.5) == 10
