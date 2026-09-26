from billing.models import LineItem
from billing.refund import refund_summary, refund_total_dollars


def test_refund_total_keeps_cents():
    items = [LineItem("mug", 2, 12.49)]
    assert refund_total_dollars(items, 0.0825) == 27.04


def test_refund_integer_dollar_prices():
    items = [LineItem("poster", 3, 4)]
    assert refund_total_dollars(items, 0.0825) == 12.99


def test_refund_with_restocking_fee():
    items = [LineItem("lamp", 1, 20.00)]
    assert refund_total_dollars(items, 0.05, restocking_fee=2.50) == 18.5


def test_refund_summary():
    items = [LineItem("pen", 2, 5), LineItem("pad", 1, 3)]
    assert refund_summary("ORD-3", items, 0.0) == {"order_id": "ORD-3", "lines": 2,
                                                   "refund_dollars": 13.0}
