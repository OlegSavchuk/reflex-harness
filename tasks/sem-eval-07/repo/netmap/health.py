"""Topology health."""
from netmap.graph import Graph
from netmap.reach import reachable


def components(graph: Graph) -> int:
    seen, count = set(), 0
    for node in sorted(graph.nodes()):
        if node not in seen:
            count += 1
            seen |= reachable(graph, node)
    return count
