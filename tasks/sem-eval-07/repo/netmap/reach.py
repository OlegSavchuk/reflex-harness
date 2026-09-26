"""Reachability."""
from netmap.graph import Graph


def reachable(graph: Graph, start: str) -> set[str]:
    """All nodes connected to start, including start."""
    seen, stack = {start}, [start]
    while stack:
        for nxt in graph.neighbors(stack.pop()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen
