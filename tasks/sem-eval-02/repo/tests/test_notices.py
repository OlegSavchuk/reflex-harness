from datetime import date

from library.models import Loan
from library.notices import overdue_notice


def test_no_notice_when_on_time():
    assert overdue_notice(Loan("Beloved", date(2026, 9, 20)), date(2026, 9, 21)) is None
