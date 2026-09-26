"""Undirected graph."""


class Graph:
    def __init__(self):
        self._adj: dict[str, set[str]] = {}

    def add_edge(self, a: str, b: str) -> None:
        """Connect a and b (undirected)."""
        self._adj.setdefault(a, set()).add(b)
        self._adj.setdefault(b, set())

    def neighbors(self, node: str) -> set[str]:
        return set(self._adj.get(node, set()))

    def nodes(self) -> set[str]:
        return set(self._adj)
