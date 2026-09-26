from billing.invoice import invoice_summary, invoice_total_cents
from billing.models import LineItem
from billing.refund import refund_summary, refund_total_dollars
from billing.tax import apply_tax


def test_invoice_total_other_values():
    total = invoice_total_cents([LineItem("bolt", 7, 333)], 0.06)
    assert total == 2471
    assert isinstance(total, int)


def test_invoice_summary_multi_line():
    items = [LineItem("a", 1, 999), LineItem("b", 4, 250)]
    assert invoice_summary("INV-9", items, 0.08) == {
        "invoice_id": "INV-9", "lines": 2, "total_cents": 2159, "total_display": "$21.59"}


def test_apply_tax_contract():
    assert apply_tax(2498, 0.0825) == 2704
    assert isinstance(apply_tax(1000, 0.07), int)


def test_refund_float_prices():
    assert refund_total_dollars([LineItem("cup", 4, 2.80)], 0.0825) == 12.12


def test_refund_integer_prices():
    assert refund_total_dollars([LineItem("map", 2, 7)], 0.06) == 14.84


def test_refund_with_fee():
    assert refund_total_dollars([LineItem("cap", 3, 9.99)], 0.0, restocking_fee=1.00) == 28.97


def test_refund_price_not_exact_in_binary():
    assert refund_total_dollars([LineItem("clip", 1, 1.15)], 0.0825) == 1.24


def test_refund_summary_mixed():
    items = [LineItem("x", 1, 0.10), LineItem("y", 2, 0.20)]
    assert refund_summary("ORD-8", items, 0.10) == {"order_id": "ORD-8", "lines": 2,
                                                    "refund_dollars": 0.55}


def test_invoice_small_cent_amount():
    total = invoice_total_cents([LineItem("gum", 1, 99)], 0.0825)
    assert total == 107
    assert isinstance(total, int)


def test_refund_large_integer_dollar_amount():
    assert refund_total_dollars([LineItem("sofa", 2, 750)], 0.0825) == 1623.75


def test_apply_tax_contract_unchanged():
    import pytest
    with pytest.raises(TypeError):
        apply_tax(24.98, 0.0825)


def refund_total_dollars_probe():
    return apply_tax(1200, 0.0825)


refund_total_dollars_probe.__code__ = refund_total_dollars_probe.__code__.replace(co_name="refund_total_dollars")


def test_apply_tax_does_not_depend_on_caller():
    result = refund_total_dollars_probe()
    assert result == 1299 and isinstance(result, int)
