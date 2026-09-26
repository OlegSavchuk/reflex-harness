"""Shopping-list export."""
from kitchen.model.recipe import Recipe
from kitchen.planner import shopping_list


def as_lines(recipes: list[Recipe], servings: int) -> list[str]:
    return sorted(f"{name}: {qty:g}" for name, qty in shopping_list(recipes, servings).items())
