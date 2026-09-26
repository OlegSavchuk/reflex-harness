from lending.adapters.broker_feed import quote_from_feed


def test_quote_standard_rate():
    assert quote_from_feed({"amount": 12000, "rate_pct": 4.25, "months": 48}) == 272.29


def test_quote_higher_rate():
    assert quote_from_feed({"amount": 5000, "rate_pct": 6.5, "months": 24}) == 222.73
