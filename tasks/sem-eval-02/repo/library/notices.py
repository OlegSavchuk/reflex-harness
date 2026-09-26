"""Overdue notices."""
from datetime import date

from library.fees import overdue_fee
from library.models import Loan


def overdue_notice(loan: Loan, today: date) -> str | None:
    fee = overdue_fee(loan, today)
    return None if fee == 0 else f"{loan.title}: {fee:.2f} due"
