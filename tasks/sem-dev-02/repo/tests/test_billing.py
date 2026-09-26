from timesheet.billing import billable_hours, invoice_amount
from timesheet.models import Entry


def test_billable_hours():
    assert billable_hours([Entry("a", "1h30m"), Entry("b", "0h45m")]) == 2.25


def test_non_billable_excluded():
    assert billable_hours([Entry("a", "2h00m", billable=False), Entry("b", "1h00m")]) == 1.0


def test_invoice_amount():
    assert invoice_amount([Entry("a", "3h00m")], 50) == 150.0


def test_no_entries():
    assert billable_hours([]) == 0.0
