from shipping.checkout import checkout_total


def test_empty_checkout():
    assert checkout_total([]) == 0
