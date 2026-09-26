"""Word statistics."""
from collections import Counter

from textindex.analysis.tokens import tokenize


def top_words(docs: list[str], n: int) -> list[tuple[str, int]]:
    """The n most frequent words across docs; ties are broken alphabetically."""
    counts = Counter(tok for doc in docs for tok in tokenize(doc))
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:n]
