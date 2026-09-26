from airline.allowance import weight_allowance
from airline.fees import baggage_fee


def test_business_allowance():
    assert weight_allowance("business") == 35


def test_business_boundary():
    assert baggage_fee("business", [35, 36]) == 7500


def test_economy_boundary():
    assert baggage_fee("economy", [20, 21]) == 13500


def _allow(cabin):
    return weight_allowance(cabin)


def test_allowance_outside_a_test_function():
    assert _allow("business") == 35
