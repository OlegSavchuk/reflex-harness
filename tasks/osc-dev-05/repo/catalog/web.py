"""Web listing. The ?page= query parameter is 1-based."""
from catalog.paging import page_slice

PER_PAGE = 2


def listing(products: list, page: int = 1) -> list:
    return page_slice(products, page, PER_PAGE)


def page_count(products: list) -> int:
    return -(-len(products) // PER_PAGE)
