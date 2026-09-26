"""Team totals."""
from payroll.pay import net_pay


def team_net(entries: list[tuple[float, int]]) -> int:
    """Total net pay for (hours, rate_cents) entries."""
    return sum(net_pay(h, r) for h, r in entries)
