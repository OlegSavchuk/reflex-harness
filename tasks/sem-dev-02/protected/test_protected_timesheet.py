from timesheet.billing import billable_hours, invoice_amount
from timesheet.models import Entry
from timesheet.parsing import parse_duration
from timesheet.summary import weekly_summary


def test_parse_duration():
    assert parse_duration("1h05m") == 65
    assert parse_duration(" 0h59m ") == 59


def test_billable_mix():
    entries = [Entry("a", "0h20m"), Entry("b", "2h10m"), Entry("c", "5h00m", billable=False)]
    assert billable_hours(entries) == 2.5


def test_invoice_rounding():
    assert invoice_amount([Entry("a", "1h20m")], 90) == 119.7


def test_summary():
    assert weekly_summary([Entry("a", "1h30m")]) == "1 entries, 1.50 billable hours"
