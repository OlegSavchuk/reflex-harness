from billing.invoice import format_cents, invoice_summary, invoice_total_cents
from billing.models import LineItem


def test_invoice_total_cents():
    items = [LineItem("widget", 3, 1999)]
    total = invoice_total_cents(items, 0.0825)
    assert total == 6492
    assert isinstance(total, int)


def test_invoice_summary():
    items = [LineItem("gadget", 2, 1250)]
    summary = invoice_summary("INV-7", items, 0.0725)
    assert summary == {"invoice_id": "INV-7", "lines": 1,
                       "total_cents": 2681, "total_display": "$26.81"}


def test_format_cents():
    assert format_cents(6492) == "$64.92"
    assert format_cents(5) == "$0.05"
