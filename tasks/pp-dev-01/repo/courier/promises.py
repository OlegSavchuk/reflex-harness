"""Customer-facing delivery promises."""
from datetime import date

from courier.sla import delivery_date


def promise_line(order_id: str, shipped: date, service_days: int) -> str:
    return f"{order_id}: arrives {delivery_date(shipped, service_days).isoformat()}"
