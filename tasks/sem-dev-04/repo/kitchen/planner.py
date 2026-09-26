"""Meal planning."""
from kitchen.model.recipe import Recipe


def shopping_list(recipes: list[Recipe], servings: int) -> dict[str, float]:
    """Total ingredients to cook every recipe for `servings` people."""
    totals: dict[str, float] = {}
    for r in recipes:
        for name, qty in r.scaled(servings).ingredients.items():
            totals[name] = round(totals.get(name, 0) + qty, 2)
    return totals
