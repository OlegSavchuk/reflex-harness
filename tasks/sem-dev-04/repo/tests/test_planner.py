from kitchen.export import as_lines
from kitchen.model.recipe import Recipe
from kitchen.planner import shopping_list


def pancakes():
    return Recipe("pancakes", 2, {"flour": 200, "egg": 2})


def test_single_recipe():
    assert shopping_list([pancakes()], 4) == {"flour": 400, "egg": 4}


def test_same_recipe_twice():
    p = pancakes()
    assert shopping_list([p, p], 4) == {"flour": 800, "egg": 8}


def test_planning_twice():
    p = pancakes()
    shopping_list([p], 4)
    assert shopping_list([p], 2) == {"flour": 200, "egg": 2}


def test_export():
    assert as_lines([Recipe("soup", 4, {"leek": 2, "stock": 1.5})], 2) == ["leek: 1", "stock: 0.75"]
