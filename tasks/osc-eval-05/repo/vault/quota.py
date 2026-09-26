"""Quota planning. Sizes in the quota settings file are in KiB."""
from vault.blocks import blocks_needed


def plan(settings: dict[str, int]) -> dict[str, int]:
    return {name: blocks_needed(kib) for name, kib in settings.items()}
