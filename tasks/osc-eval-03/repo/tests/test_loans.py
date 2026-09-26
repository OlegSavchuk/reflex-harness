from lending.car_loan import car_payment
from lending.mortgage import mortgage_payment


def test_mortgage():
    assert mortgage_payment(300000, 60000, 0.05, 25) == 1403.02


def test_car_interest_free():
    assert car_payment(18000, 0.0, 36) == 500.0
