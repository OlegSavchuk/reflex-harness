from datetime import date

from library.fees import overdue_fee
from library.models import Loan


def test_four_days_late():
    assert overdue_fee(Loan("Dune", date(2026, 9, 1)), date(2026, 9, 19)) == 1.0


def test_short_loan_late():
    assert overdue_fee(Loan("Emma", date(2026, 8, 1), loan_days=7), date(2026, 8, 30)) == 5.5


def test_not_yet_due():
    assert overdue_fee(Loan("Ulysses", date(2026, 9, 10)), date(2026, 9, 12)) == 0.0
