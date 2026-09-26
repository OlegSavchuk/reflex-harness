"""`python -m reflex_harness run --pretty`: one line per run event, for live demo recording.

Presentation only. It receives copies of run events from `controller.run_task(events=...)` and
prints them; nothing it does feeds back into the run. Colour when stdout is a terminal or
FORCE_COLOR is set; NO_COLOR turns it off. Spinners ("model thinking… 12s") only on a terminal;
they are replaced in place by the next line and never enter the transcript kept in `lines`.
Lines stay under ~110 characters.
"""
from __future__ import annotations

import os
import re
import sys
import threading
import time

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
BOX_WIDTH = 72
MAX_DIFF_LINES = 5
FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


def clip(text: str, n: int) -> str:
    return text if len(text) <= n else text[:n - 1] + "…"


def bar(passed: int, total: int, width: int = 10) -> str:
    cells = total if 0 < total <= width else width
    full = round(cells * passed / total) if total else 0
    return "█" * full + "░" * (cells - full)


class _Spinner:
    """One animated line on a terminal, cleared when stopped."""

    def __init__(self, stream, label: str):
        self.stream, self.label, self.t0 = stream, label, time.monotonic()
        self.done = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        i = 0
        while not self.done.wait(0.1):
            self.stream.write(f"\r\033[K{FRAMES[i % len(FRAMES)]} {self.label}… "
                              f"{int(time.monotonic() - self.t0)}s")
            self.stream.flush()
            i += 1

    def stop(self):
        self.done.set()
        self.thread.join()
        self.stream.write("\r\033[K")
        self.stream.flush()
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
                 checkpoint_outcomes=None, diff: bool = True, spinner: bool | None = None):
        self.model = model
        self.stream = stream or sys.stdout
        self.color = use_color(self.stream) if color is None else color
        self.diff = diff
        self.spinner = (bool(getattr(self.stream, "isatty", lambda: False)()) if spinner is None
                        else spinner)
        self.lines: list[str] = []
        self.budget = None
        self._spin: _Spinner | None = None
        self._outcomes = checkpoint_outcomes or _outcomes_from_memory

    # ---------- formatting ----------
    def badge(self, text: str, bg: str) -> str:
        return f"\033[1;97;{BG[bg]}m  {text}  {RESET}" if self.color else f"[ {text} ]"

    def tint(self, text: str, fg: str) -> str:
        return f"\033[1;{FG[fg]}m{text}{RESET}" if self.color else text

    def mark(self, ok: bool | None) -> str:
        return self.tint("✓", "green") if ok else self.tint("–", "grey") if ok is None else self.tint("✗", "red")

    def stop_spinner(self) -> None:
        if self._spin is not None:
            self._spin.stop()
            self._spin = None

    def out(self, line: str) -> None:
        self.stop_spinner()
        print(line, file=self.stream, flush=True)
        self.lines.append(re.sub(r"\033\[[0-9;]*m", "", line))

    # ---------- events ----------
    def __call__(self, kind: str, **data) -> None:
        if kind != "wait":
            self.stop_spinner()
        handler = getattr(self, f"on_{kind}", None)
        if handler:
            handler(**data)

    def on_wait(self, *, what, **_):
        self.stop_spinner()
        if self.spinner:
            self._spin = _Spinner(self.stream, what)

    def on_start(self, *, task_id, arm, budget, visible_passed, visible_total, **_):
        self.budget = budget
        label = "PLAIN AGENT" if arm == "plain_retry" else "REFLEX"
        self.out(f"{self.badge(label, 'blue')} {self.tint(task_id, 'yellow')} · {arm} · "
                 f"{clip(self.model, 34)} · {budget} attempts max · seed {visible_passed}/{visible_total} visible")

    def on_context(self, *, config_id, shown, approx_tokens, **_):
        k = f"{approx_tokens / 1000:.1f}k" if approx_tokens >= 1000 else str(approx_tokens)
        self.out(f"{self.badge('CONTEXT', 'grey')} ({config_id}) → {clip(', '.join(shown), 60)} · ≈{k} tokens")

    def on_attempt(self, *, attempt_n, config_id, edited, visible_passed, visible_total, error, solved,
                   regressed=(), trigger=None, diff=(), **_):
        fns = [e.split("::")[-1] for e in edited]
        names = [f for f in fns if f != "<module>"] + (["module-level code"] if "<module>" in fns else [])
        what = f"editing {clip(', '.join(names), 40)}" if names else clip(f"no edit ({error})" if error else "no edit", 48)
        score = f"VISIBLE TESTS {bar(visible_passed, visible_total)} {visible_passed}/{visible_total}"
        broke = ""
        if trigger == "regression" and regressed:
            n = len(regressed)
            broke = " · " + self.tint(f"{n} previously passing test{'s' if n != 1 else ''} broke", "red")
        self.out(f"{self.badge(f'ATTEMPT {attempt_n}', 'cyan')} ({config_id}) · {what} → "
                 f"{self.tint(score, 'green' if solved else 'yellow')}{broke}")
        if self.diff:
            for line in diff[:MAX_DIFF_LINES]:
                self.out("      " + self.tint(clip(line, 96), "red" if line.startswith("-") else "green"))
            if len(diff) > MAX_DIFF_LINES:
                self.out("      …")

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
        self.out(f"{self.badge('MONGODB MEMORY', 'green')} nearest: {top['checkpoint_id']} "
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
                 output_tokens, attempts=None, **_):
        if verify is None:
            hidden = f"HIDDEN TESTS {self.mark(None)} (not run: visible tests fail)"
            static = f"STATIC CHECK {self.mark(None)} (not run)"
        else:
            hidden = f"HIDDEN TESTS {self.mark(not verify['failed'] and not verify['timed_out'])} ({pytest_summary(verify)})"
            static = f"STATIC CHECK {self.mark(not verify['static_failed'])}"
        self.out(f"{self.badge('FINAL', 'blue')} VISIBLE TESTS {self.mark(visible_pass)} · {hidden} · {static}")
        word, colour = ("FIXED", "green") if verified_fix else ("NOT FIXED", "red")
        for text in (f"{word} · {STOPS.get(stop_reason, stop_reason)}",
                     f"attempts used: {attempts} of {self.budget}",
                     f"{input_tokens + output_tokens:,} tokens ({input_tokens:,} in / {output_tokens:,} out)"
                     f" · ${cost_usd:.4f}"):
            text = clip(text, BOX_WIDTH - 4)
            self.out(f"\033[1;97;{BG[colour]}m  {text.ljust(BOX_WIDTH - 4)}  {RESET}" if self.color
                     else f"│ {text.ljust(BOX_WIDTH - 4)} │")


def _outcomes_from_memory(checkpoint_id: str) -> list[str]:
    """Configs whose dev trial verified-solved this checkpoint (read-only lookup for display)."""
    from .store import db
    doc = db()["checkpoints"].find_one({"checkpoint_id": checkpoint_id}, {"_id": 0, "outcomes": 1}) or {}
    return [o["config_id"] for o in doc.get("outcomes", []) if o.get("solved") and o.get("verified")]
