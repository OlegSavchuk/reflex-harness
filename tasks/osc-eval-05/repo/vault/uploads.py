"""Uploads. Sizes are in bytes; partial sectors are padded."""
from vault.blocks import SECTOR, blocks_needed


def blocks_for_upload(size_bytes: int) -> int:
    aligned = -(-size_bytes // SECTOR) * SECTOR
    return blocks_needed(aligned)
