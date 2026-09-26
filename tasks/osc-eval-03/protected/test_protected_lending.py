import pytest

from lending.adapters.broker_feed import quote_from_feed
from lending.car_loan import car_payment
from lending.core.interest import monthly_payment


def test_quote_below_one_percent():
    assert quote_from_feed({"amount": 10000, "rate_pct": 0.75, "months": 12}) == 836.72


def test_quote_zero_rate():
    assert quote_from_feed({"amount": 1200, "rate_pct": 0, "months": 12}) == 100.0


def test_quote_long_term():
    assert quote_from_feed({"amount": 20000, "rate_pct": 9.99, "months": 72}) == 370.42


def test_interest_still_rejects_rates_of_one_or_more():
    with pytest.raises(ValueError):
        monthly_payment(1000, 1.5, 12)


def test_car_unchanged():
    assert car_payment(10000, 0.03, 12) == 846.94


def quote_from_feed_probe():
    return monthly_payment(1200, 0.05, 12)


quote_from_feed_probe.__code__ = quote_from_feed_probe.__code__.replace(co_name="quote_from_feed")


def test_interest_does_not_depend_on_caller():
    assert quote_from_feed_probe() == 102.73
