"""Overdue fees."""
from datetime import date

from library.models import Loan

DAILY_FEE = 0.25
MAX_FEE = 10.0


def overdue_fee(loan: Loan, today: date) -> float:
    days_late = (today - loan.due_on).days
    if days_late <= 0:
        return 0.0
    return round(min(days_late * DAILY_FEE, MAX_FEE), 2)
