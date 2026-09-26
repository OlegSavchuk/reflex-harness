from promo.cart import cart_total
from promo.rules.discount import Discount


def test_discount_matches_the_exact_sku_only():
    d = Discount("CAP", 20)
    assert d.applies_to("CAP") and not d.applies_to("CAPE") and not d.applies_to("CA")


def test_cart_other_skus():
    assert cart_total([("KEY", 1000, 1), ("KEYRING", 400, 2)], [Discount("KEY", 50)]) == 1300


def _applies(d, sku):
    return d.applies_to(sku)


def test_rule_outside_a_test_function():
    assert _applies(Discount("BAG", 5), "BAGEL") is False
