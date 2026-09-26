from netmap.graph import Graph
from netmap.reach import reachable


def test_neighbors_are_symmetric():
    g = Graph()
    g.add_edge("x", "y")
    assert g.neighbors("y") == {"x"} and g.neighbors("x") == {"y"}


def test_reachable_chain():
    g = Graph()
    for a, b in (("p", "q"), ("r", "q"), ("r", "s")):
        g.add_edge(a, b)
    assert reachable(g, "p") == {"p", "q", "r", "s"}


def _nb(g, node):
    return g.neighbors(node)


def test_neighbors_outside_a_test_function():
    g = Graph()
    g.add_edge("m", "n")
    assert _nb(g, "n") == {"m"}
