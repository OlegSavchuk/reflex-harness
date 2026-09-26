"""Payslips."""
from payroll.pay import net_pay


def payslip_line(name: str, hours: float, rate_cents: int) -> str:
    return f"{name}: {net_pay(hours, rate_cents) / 100:.2f}"
