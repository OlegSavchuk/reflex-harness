"""Report rendering."""
from gradebook.models import GradeBook
from gradebook.stats import class_average, pass_rate


def course_line(book: GradeBook) -> str:
    return f"{book.course}: avg {class_average(book):.2f}, pass {pass_rate(book):.0%}"
