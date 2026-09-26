from gradebook.models import GradeBook
from gradebook.stats import class_average, pass_rate


def test_average_first_course():
    book = GradeBook("math")
    book.add(90)
    book.add(70)
    assert class_average(book) == 80.0


def test_average_second_course():
    book = GradeBook("art")
    book.add(50)
    assert class_average(book) == 50.0


def test_pass_rate():
    book = GradeBook("bio")
    for s in (55, 65, 75, 85):
        book.add(s)
    assert pass_rate(book) == 0.75


def test_average_explicit_scores():
    assert class_average(GradeBook("none", [])) == 0.0
