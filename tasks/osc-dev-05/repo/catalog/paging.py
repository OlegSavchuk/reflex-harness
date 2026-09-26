"""Page slicing shared by the web listing and the export API."""


def page_slice(items: list, page: int, per_page: int) -> list:
    """Items on a 1-based page (page 1 is the first page)."""
    if page < 1:
        raise ValueError(f"page is 1-based, got {page}")
    if per_page < 1:
        raise ValueError(f"per_page must be positive, got {per_page}")
    start = (page - 1) * per_page
    return items[start:start + per_page]
