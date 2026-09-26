"""tasks/index.json: the task registry (split, family, designed config, focal callers, depth)."""
import json

from .runner import TASKS_DIR


def load_index() -> dict[str, dict]:
    return {e["task_id"]: e for e in json.loads((TASKS_DIR / "index.json").read_text())["tasks"]}


def caller_rule(n_callers: int) -> str:
    """The structural baseline (SPEC §13, caller_count): caller if the focal has >1 caller."""
    return "caller" if n_callers > 1 else "dependency"


def is_counter_pattern(entry: dict) -> bool:
    """SPEC §13.6: the caller-count rule mispredicts the task's designed config."""
    return caller_rule(entry["n_callers"]) != entry["designed_config"]
