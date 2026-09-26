from gradebook.models import GradeBook
from gradebook.report import course_line


def test_course_line():
    assert course_line(GradeBook("chem", [80.0, 40.0])) == "chem: avg 60.00, pass 50%"


def test_count():
    assert GradeBook("geo", [1.0, 2.0, 3.0]).count() == 3
