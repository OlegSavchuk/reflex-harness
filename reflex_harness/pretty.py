"""`python -m reflex_harness run --pretty`: one line per run event, for live demo recording.

Presentation only. It receives copies of run events from `controller.run_task(events=...)` and
prints them; nothing it does feeds back into the run. Colour when stdout is a terminal or
FORCE_COLOR is set; NO_COLOR turns it off. A plain-text transcript is kept in `lines`.
"""
from __future__ import annotations

import os
import re
import sys

RESET = "\033[0m"
BG = {"blue": 44, "cyan": 46, "green": 42, "red": 41, "yellow": 43, "magenta": 45, "grey": 100}
FG = {"green": 32, "red": 31, "yellow": 33, "grey": 90}
TRIGGERS = {"regression": ("REGRESSION", "red"), "exact_repeat": ("REPEAT", "magenta"),
            "same_strategy": ("SAME STRATEGY", "yellow")}
STOPS = {"solved": "hidden tests passed", "verification_failed": "visible tests passed, hidden tests failed",
         "budget_exhausted": "attempt budget used up", "rolled_back_budget_exhausted": "attempt budget used up",
         "intervention_limit_reached": "second trigger after the one allowed switch",
         "configurations_exhausted": "no untried configuration left", "reset_failed": "reset to seed failed",
         "infrastructure_error": "infrastructure error"}
BANNER_WIDTH = 64
PYTEST_ORDER = ("failed", "passed", "skipped", "xfailed", "xpassed", "error")


def use_color(stream) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    return bool(os.environ.get("FORCE_COLOR")) or bool(getattr(stream, "isatty", lambda: False)())


def pytest_summary(verify: dict) -> str:
    """The protected run's counts in pytest's own summary format, e.g. '1 failed, 4 passed in 0.31s'."""
    s = verify.get("summary") or {}
    parts = []
    for key in PYTEST_ORDER:
        n = s.get(key, 0)
        if n:
            parts.append(f"{n} {'errors' if key == 'error' and n > 1 else key}")
    return f"{', '.join(parts) or 'no tests ran'} in {verify.get('duration_s') or 0:.2f}s"


class Pretty:
    def __init__(self, *, model: str = "?", stream=None, color: bool | None = None,
                 checkpoint_outcomes=None):
        self.model = model
        self.stream = stream or sys.stdout
        self.color = use_color(self.stream) if color is None else color
        self.lines: list[str] = []
        self._outcomes = checkpoint_outcomes or _outcomes_from_memory

    # ---------- formatting ----------
    def badge(self, text: str, bg: str) -> str:
        return f"\033[1;97;{BG[bg]}m  {text}  {RESET}" if self.color else f"[ {text} ]"

    def tint(self, text: str, fg: str) -> str:
        return f"\033[1;{FG[fg]}m{text}{RESET}" if self.color else text

    def mark(self, ok: bool | None) -> str:
        return self.tint("✓", "green") if ok else self.tint("–", "grey") if ok is None else self.tint("✗", "red")

    def out(self, line: str) -> None:
        print(line, file=self.stream, flush=True)
        self.lines.append(re.sub(r"\033\[[0-9;]*m", "", line))

    # ---------- events ----------
    def __call__(self, kind: str, **data) -> None:
        handler = getattr(self, f"on_{kind}", None)
        if handler:
            handler(**data)

    def on_start(self, *, task_id, arm, budget, visible_passed, visible_total, **_):
        self.out(f"{self.badge('REFLEX', 'blue')} task {self.tint(task_id, 'yellow')} · arm {arm} · "
                 f"model {self.model} · budget {budget} attempts · seed: visible tests "
                 f"{visible_passed}/{visible_total}")

    def on_attempt(self, *, attempt_n, config_id, edited, visible_passed, visible_total, error, solved, **_):
        fns = [e.split("::")[-1] for e in edited]
        names = [f for f in fns if f != "<module>"] + (["module-level code"] if "<module>" in fns else [])
        what = f"editing {', '.join(names)}" if names else f"no edit ({error})" if error else "no edit"
        score = f"VISIBLE TESTS {visible_passed}/{visible_total}"
        self.out(f"{self.badge(f'ATTEMPT {attempt_n}', 'cyan')} ({config_id}) · {what} → "
                 f"{self.tint(score, 'green' if solved else 'yellow')}")

    def on_trigger(self, *, trigger, **_):
        label, colour = TRIGGERS.get(trigger, (trigger.upper(), "red"))
        tail = " → edits rolled back" if trigger == "regression" else ""
        self.out(f"{self.badge(label, colour)} detected{tail}")

    def on_selection(self, *, arm, row, **_):
        if arm != "memory":
            return
        top = (row.get("retrieved") or [None])[0]
        if top is None:
            self.out(f"{self.badge('MONGODB MEMORY', 'green')} → no past case found ({row.get('status')})")
            return
        solved_by = self._outcomes(top["checkpoint_id"])
        score = top.get("semantic_score")
        self.out(f"{self.badge('MONGODB MEMORY', 'green')} → nearest past case: {top['checkpoint_id']} "
                 f"({top.get('family')}, similarity {score:.2f}) → solved by "
                 f"{', '.join(solved_by) if solved_by else 'no configuration'}"
                 f"{'' if row.get('status') == 'selected' else ' · ' + str(row.get('status'))}")

    def on_reset(self, *, verified, seed_hash=None, tree_hash=None, **_):
        if verified:
            self.out(f"{self.badge('RESET', 'grey')} → seed hash verified ({(seed_hash or '')[:12]})")
        else:
            self.out(f"{self.badge('RESET FAILED', 'red')} → tree {(tree_hash or '')[:12]} ≠ seed "
                     f"{(seed_hash or '')[:12]}; run stopped")

    def on_switch(self, *, to_config, **_):
        self.out(f"{self.badge('SWITCH', 'magenta')} → {to_config}")

    def on_final(self, *, stop_reason, verified_fix, visible_pass, verify, cost_usd, input_tokens,
                 output_tokens, **_):
        if verify is None:
            hidden = f"HIDDEN TESTS {self.mark(None)} (not run: visible tests fail)"
            static = f"STATIC CHECK {self.mark(None)} (not run)"
        else:
            hidden = f"HIDDEN TESTS {self.mark(not verify['failed'] and not verify['timed_out'])} ({pytest_summary(verify)})"
            static = f"STATIC CHECK {self.mark(not verify['static_failed'])}"
        self.out(f"{self.badge('FINAL', 'blue')} VISIBLE TESTS {self.mark(visible_pass)} · {hidden} · {static}")
        word, colour = ("FIXED", "green") if verified_fix else ("NOT FIXED", "red")
        text = (f"{word}  ·  ${cost_usd:.4f}  ·  {input_tokens + output_tokens:,} tokens "
                f"({input_tokens:,} in / {output_tokens:,} out)")
        if not verified_fix:
            text += f"  ·  {STOPS.get(stop_reason, stop_reason)}"
        self.out(self.badge(text.center(BANNER_WIDTH), colour))


def _outcomes_from_memory(checkpoint_id: str) -> list[str]:
    """Configs whose dev trial verified-solved this checkpoint (read-only lookup for display)."""
    from .store import db
    doc = db()["checkpoints"].find_one({"checkpoint_id": checkpoint_id}, {"_id": 0, "outcomes": 1}) or {}
    return [o["config_id"] for o in doc.get("outcomes", []) if o.get("solved") and o.get("verified")]
