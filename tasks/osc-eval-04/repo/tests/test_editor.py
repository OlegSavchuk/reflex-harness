from sprites.editor.tools import rotate_handle


def test_quarter_turn():
    assert rotate_handle((1.0, 0.0), 90) == (0.0, 1.0)


def test_half_turn():
    assert rotate_handle((2.0, 1.0), 180) == (-2.0, -1.0)


def test_forty_five():
    assert rotate_handle((1.0, 1.0), 45) == (0.0, 1.4142)
