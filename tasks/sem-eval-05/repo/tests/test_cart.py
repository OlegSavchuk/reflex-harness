from promo.cart import cart_total
from promo.receipt import receipt
from promo.rules.discount import Discount


def test_discount_only_on_its_sku():
    assert cart_total([("TEA", 300, 2), ("TEAPOT", 2500, 1)], [Discount("TEA", 10)]) == 3040


def test_receipt():
    assert receipt([("MUG", 800, 1), ("MUGSET", 3000, 1)], [Discount("MUG", 25)]) == "TOTAL 36.00"


def test_no_discounts():
    assert cart_total([("PEN", 100, 3)], []) == 300
