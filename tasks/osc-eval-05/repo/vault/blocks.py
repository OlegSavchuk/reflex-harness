"""Block accounting shared by uploads and quota planning."""
BLOCK = 4096
SECTOR = 512


def blocks_needed(size_bytes: int) -> int:
    """Number of 4 KiB blocks for a sector-aligned size in bytes."""
    if not isinstance(size_bytes, int) or size_bytes < 0:
        raise ValueError(f"size_bytes must be a non-negative int, got {size_bytes!r}")
    if size_bytes % SECTOR:
        raise ValueError(f"size_bytes must be sector-aligned ({SECTOR}), got {size_bytes}")
    return -(-size_bytes // BLOCK)
