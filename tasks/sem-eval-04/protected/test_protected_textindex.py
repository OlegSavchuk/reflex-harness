from textindex.analysis.tokens import tokenize
from textindex.counts import top_words


def test_tokenize_lowercases():
    assert tokenize("Hello World") == ["hello", "world"]


def test_tokenize_keeps_apostrophes():
    assert tokenize("It's OK") == ["it's", "ok"]


def test_top_words_other_docs():
    assert top_words(["Apple banana", "apple APPLE", "Banana cherry"], 2) == [("apple", 3), ("banana", 2)]


def _tok(text):
    return tokenize(text)


def test_tokenize_outside_a_test_function():
    assert _tok("ABC") == ["abc"]
