"""Export API. Cursors are 0-based batch indexes (cursor 0 is the first batch)."""
from catalog.paging import page_slice


def export_batch(records: list, cursor: int, batch_size: int = 3) -> list:
    return page_slice(records, cursor, batch_size)
