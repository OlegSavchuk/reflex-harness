"""Seat-row labels."""


def row_label(index: int) -> str:
    """Spreadsheet-style label for a 0-based row index: 0 -> A, 25 -> Z, 26 -> AA, 27 -> AB."""
    label = ""
    while True:
        index, r = divmod(index, 26)
        label = chr(ord("A") + r) + label
        if index == 0:
            return label
