from fitlog.sessions import from_manual, from_watch


def test_manual_5k():
    assert from_manual(5.0, 25) == {'km': 5.0, 'pace': '5:00 /km'}


def test_manual_half_marathon():
    assert from_manual(21.1, 110) == {'km': 21.1, 'pace': '5:13 /km'}


def test_watch():
    assert from_watch({"distance_m": 10000, "elapsed_s": 3000}) == {'km': 10.0, 'pace': '5:00 /km'}
