"""Course statistics."""
from gradebook.models import GradeBook


def class_average(book: GradeBook) -> float:
    if not book.scores:
        return 0.0
    return round(sum(book.scores) / len(book.scores), 2)


def pass_rate(book: GradeBook, threshold: float = 60.0) -> float:
    if not book.scores:
        return 0.0
    return round(sum(s >= threshold for s in book.scores) / len(book.scores), 2)
