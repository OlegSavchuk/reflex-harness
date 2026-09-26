import pytest

from codeview.annotate import _annotation, lint_annotation, search_annotation
from codeview.core.source import snippet

LINES = ["import os", "", "def main():", "    path = os.getcwd()", "    print(path)", "", "main()"]


def test_search_first_line():
    assert search_annotation(LINES, {"index": 0, "term": "os"}).splitlines() == ["# found 'os'", '>  1 import os', '   2 ']


def test_search_middle_line():
    assert search_annotation(LINES, {"index": 4, "term": "print"}).splitlines() == ["# found 'print'", '   4     path = os.getcwd()', '>  5     print(path)', '   6 ']


def test_lint_unchanged():
    assert lint_annotation(LINES, {"line": 1, "code": "F401", "message": "unused import"}).splitlines() == ['# F401: unused import', '>  1 import os', '   2 ']


def test_snippet_is_one_based():
    assert snippet(LINES, 3, 0) == ['>  3 def main():']


def test_snippet_still_rejects_line_zero():
    with pytest.raises(ValueError):
        snippet(LINES, 0)


def search_annotation_probe():
    return _annotation(LINES, 4, "x")


search_annotation_probe.__code__ = search_annotation_probe.__code__.replace(co_name="search_annotation")


def test_annotation_does_not_depend_on_caller():
    assert search_annotation_probe().splitlines() == ['# x', '   3 def main():', '>  4     path = os.getcwd()', '   5     print(path)']
