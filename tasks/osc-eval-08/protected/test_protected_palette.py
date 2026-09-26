import pytest

from palette.core.mix import blend
from palette.importers.css_float import mix_css
from palette.themes import accent


def test_css_quarter():
    assert mix_css((0.0, 0.5, 1.0), (1.0, 0.5, 0.0), 0.25) == (0.251, 0.502, 0.749)


def test_css_dark():
    assert mix_css((0.0, 0.0, 0.004), (0.0, 0.0, 0.0), 0.5) == (0.0, 0.0, 0.0)


def test_blend_still_rejects_floats():
    with pytest.raises(TypeError):
        blend((0.5, 0.5, 0.5), (0.0, 0.0, 0.0), 0.5)


def test_accent_unchanged():
    assert accent((10, 20, 30), (50, 60, 70)) == (20, 30, 40)


def mix_css_probe():
    return blend((255, 0, 0), (0, 0, 255), 0.5)


mix_css_probe.__code__ = mix_css_probe.__code__.replace(co_name="mix_css")


def test_blend_does_not_depend_on_caller():
    assert mix_css_probe() == (128, 0, 128)
