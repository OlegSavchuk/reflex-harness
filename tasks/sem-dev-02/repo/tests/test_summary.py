from timesheet.summary import weekly_summary


def test_empty_week():
    assert weekly_summary([]) == "0 entries, 0.00 billable hours"
