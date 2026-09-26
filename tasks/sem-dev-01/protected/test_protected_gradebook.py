from gradebook.models import GradeBook
from gradebook.report import course_line
from gradebook.stats import class_average, pass_rate


def test_default_books_are_independent():
    a, b = GradeBook("a"), GradeBook("b")
    a.add(100)
    b.add(40)
    assert class_average(a) == 100.0
    assert class_average(b) == 40.0
    assert a.count() == 1 and b.count() == 1


def test_pass_rate_fresh_book():
    book = GradeBook("c")
    for s in (59, 60, 61):
        book.add(s)
    assert pass_rate(book) == 0.67


def test_report_default_book():
    book = GradeBook("d")
    book.add(70)
    assert course_line(book) == "d: avg 70.00, pass 100%"
