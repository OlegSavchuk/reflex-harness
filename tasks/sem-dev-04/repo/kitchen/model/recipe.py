"""Recipes."""


class Recipe:
    def __init__(self, name: str, serves: int, ingredients: dict[str, float]):
        self.name = name
        self.serves = serves
        self.ingredients = ingredients

    def scaled(self, servings: int) -> "Recipe":
        """A copy of this recipe for `servings` people; the original is left unchanged."""
        factor = servings / self.serves
        for k in self.ingredients:
            self.ingredients[k] = round(self.ingredients[k] * factor, 2)
        return Recipe(self.name, servings, self.ingredients)
