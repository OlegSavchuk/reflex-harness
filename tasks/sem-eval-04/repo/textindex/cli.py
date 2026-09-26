"""Command-line summary."""
from textindex.counts import top_words


def summary(docs: list[str]) -> str:
    top = top_words(docs, 1)
    return f"{top[0][0]} ({top[0][1]})" if top else "no words"
