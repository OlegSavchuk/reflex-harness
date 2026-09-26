"""Tokenization."""
import re

_WORD = re.compile(r"[A-Za-z']+")


def tokenize(text: str) -> list[str]:
    """Lower-cased word tokens."""
    return _WORD.findall(text)
