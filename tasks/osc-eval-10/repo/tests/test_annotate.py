import pytest

from codeview.annotate import lint_annotation, search_annotation
from codeview.core.source import snippet

LINES = ["import os", "", "def main():", "    path = os.getcwd()", "    print(path)", "", "main()"]


def test_search_marks_the_matching_line():
    assert search_annotation(LINES, {"index": 3, "term": "getcwd"}).splitlines() == ["# found 'getcwd'", '   3 def main():', '>  4     path = os.getcwd()', '   5     print(path)']


def test_search_last_line():
    assert search_annotation(LINES, {"index": 6, "term": "main"}).splitlines() == ["# found 'main'", '   6 ', '>  7 main()']


def test_lint_annotation():
    assert lint_annotation(LINES, {"line": 5, "code": "T201", "message": "print found"}).splitlines() == ['# T201: print found', '   4     path = os.getcwd()', '>  5     print(path)', '   6 ']


def test_snippet_rejects_line_zero():
    with pytest.raises(ValueError):
        snippet(LINES, 0)
