from textindex.cli import summary
from textindex.counts import top_words


def test_top_word_ignores_case():
    assert top_words(["The cat", "the dog", "THE end"], 1) == [("the", 3)]


def test_summary():
    assert summary(["Red red RED blue"]) == "red (3)"


def test_no_docs():
    assert top_words([], 3) == []
