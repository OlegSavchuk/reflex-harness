from payroll.pay import net_pay
from payroll.tax import income_tax


def test_top_band_rate():
    assert income_tax(200000) == 37500
    assert income_tax(160000) == 23500


def test_lower_bands():
    assert income_tax(50000) == 0
    assert income_tax(100000) == 10000


def test_overtime_high_earner():
    assert net_pay(50, 4000) == 175500


def _tax(gross):
    return income_tax(gross)


def test_tax_outside_a_test_function():
    assert _tax(160000) == 23500
