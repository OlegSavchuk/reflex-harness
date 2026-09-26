from kitchen.model.recipe import Recipe
from kitchen.planner import shopping_list


def test_scaling_leaves_the_original_unchanged():
    r = Recipe("bread", 1, {"flour": 500, "yeast": 7})
    s = r.scaled(3)
    assert s.ingredients == {"flour": 1500, "yeast": 21}
    assert r.ingredients == {"flour": 500, "yeast": 7} and r.serves == 1


def test_week_plan():
    r = Recipe("stew", 4, {"beef": 800})
    assert shopping_list([r, r, r], 2) == {"beef": 1200}


def _scale(r, n):
    return r.scaled(n)


def test_scaling_outside_a_test_function():
    r = Recipe("salad", 2, {"leaf": 100})
    _scale(r, 4)
    assert r.ingredients == {"leaf": 100}
