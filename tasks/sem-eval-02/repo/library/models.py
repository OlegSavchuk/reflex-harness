"""Library data types."""
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class Loan:
    title: str
    borrowed_on: date
    loan_days: int = 14

    @property
    def due_on(self) -> date:
        return self.borrowed_on + timedelta(weeks=self.loan_days)
