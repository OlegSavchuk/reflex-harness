"""Gradebook data types."""


class GradeBook:
    def __init__(self, course: str, scores: list[float] = []):
        self.course = course
        self.scores = scores

    def add(self, score: float) -> None:
        self.scores.append(score)

    def count(self) -> int:
        return len(self.scores)
