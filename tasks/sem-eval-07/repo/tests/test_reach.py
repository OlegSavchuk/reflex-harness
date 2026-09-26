from netmap.graph import Graph
from netmap.health import components
from netmap.reach import reachable


def graph(*edges):
    g = Graph()
    for a, b in edges:
        g.add_edge(a, b)
    return g


def test_reachable_through_shared_node():
    assert reachable(graph(("a", "b"), ("c", "b")), "a") == {"a", "b", "c"}


def test_components():
    assert components(graph(("b", "a"), ("c", "d"))) == 2


def test_reachable_single_edge():
    assert reachable(graph(("a", "b")), "a") == {"a", "b"}
