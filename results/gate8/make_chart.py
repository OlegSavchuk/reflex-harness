"""Render docs/gate8_results.png from results/gate8/report.txt (read-only; no model calls).

Usage: python results/gate8/make_chart.py
"""
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/gate8/report.txt"
OUT = ROOT / "docs/gate8_results.png"

text = REPORT.read_text()

# --- parse "arm x family" table -------------------------------------------
cell = r"(\d+)/(\d+)\s+\$([\d.]+)"
table = {}
for arm in ("plain_retry", "fallback", "memory"):
    m = re.search(rf"^{arm}\s+{cell}.*?{cell}.*?{cell}", text, re.M)
    a_ok, a_n, _, b_ok, b_n, _, all_ok, all_n, all_cost = m.groups()
    table[arm] = dict(A=int(a_ok), An=int(a_n), B=int(b_ok), Bn=int(b_n),
                      ok=int(all_ok), n=int(all_n), cost=float(all_cost))

# --- plain_retry on family A: outcome of each run -----------------------------
rows = [l.split() for l in text.splitlines() if re.match(r"^osc-eval-\d+\s+\d+\s+plain_retry\s", l)]
pr_A_runs = len(rows)
pr_A_verified = sum(1 for r in rows if r[4] == "True")
pr_A_hacks = sum(1 for r in rows if r[3] == "verification_failed")        # passed visible, failed hidden
pr_A_failed_visible = pr_A_runs - pr_A_hacks - pr_A_verified               # never passed visible tests

# --- style ------------------------------------------------------------------
plt.rcParams["font.size"] = 11
INK, MUTED, GRID = "#1f2328", "#59636e", "#e6e8eb"
ARMS = ["plain_retry", "fallback", "memory"]
LABEL = {"plain_retry": "Plain retry", "fallback": "Fallback", "memory": "Reflex + memory"}
COLOR = {"plain_retry": "#9aa0a6", "fallback": "#eb6834", "memory": "#2a78d6"}

def style(ax):
    ax.set_facecolor("white")
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#c9ced4")
    ax.tick_params(colors=MUTED, length=0)
    ax.yaxis.grid(True, color=GRID, lw=1)
    ax.set_axisbelow(True)

fig, axs = plt.subplots(1, 3, figsize=(16, 5.2), gridspec_kw={"width_ratios": [1.3, 1.15, 0.95]})
fig.patch.set_facecolor("white")

# Panel 1: verified fixes by family
ax = axs[0]; style(ax)
w = 0.26
nA = table["memory"]["An"]
for i, arm in enumerate(ARMS):
    vals = [table[arm]["A"], table[arm]["B"]]
    xs = [g + (i - 1) * (w + 0.02) for g in range(2)]
    ax.bar(xs, [max(v, 0.12) for v in vals], w, color=COLOR[arm], label=LABEL[arm])
    for x, v in zip(xs, vals):
        ax.text(x, max(v, 0.12) + 0.2, f"{v}/{nA}", ha="center", va="bottom", color=INK,
                fontsize=10.5, fontweight="bold" if arm == "memory" else "normal")
ax.set_xticks(range(2))
ax.set_xticklabels(["Family A\n(oscillation)", "Family B\n(semantic repetition)"], color=INK)
ax.set_ylim(0, nA + 0.5)
ax.set_ylabel(f"Verified fixes (out of {nA} runs)", color=MUTED)
ax.set_title("Bugs actually fixed", loc="left", color=INK, fontweight="bold", fontsize=13, pad=12)
ax.legend(frameon=False, loc="upper left", fontsize=10, labelcolor=INK)

# Panel 2: total spend vs fixes
ax = axs[1]; style(ax)
costs = [table[a]["cost"] for a in ARMS]
ax.bar(range(3), costs, 0.55, color=[COLOR[a] for a in ARMS])
for i, arm in enumerate(ARMS):
    c, f = table[arm]["cost"], table[arm]["ok"]
    lab = f"${c:.3f} total\n" + ("0 fixed" if f == 0 else f"{f} fixed · ${c / f:.4f}/fix")
    ax.text(i, c + max(costs) * 0.02, lab, ha="center", va="bottom", color=INK, fontsize=9.5,
            fontweight="bold" if arm == "memory" else "normal", linespacing=1.4)
ax.set_xticks(range(3))
ax.set_xticklabels(["Plain\nretry", "Fallback", "Reflex +\nmemory"], color=INK)
ax.set_ylim(0, max(costs) * 1.25)
ax.set_ylabel(f"Total spend, {table['memory']['n']} runs (USD)", color=MUTED)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:.2f}"))
ax.set_title("Spend vs. result", loc="left", color=INK, fontweight="bold", fontsize=13, pad=12)

# Panel 3: plain retry on family A, one stacked bar (hacks / failed visible / fixed)
ax = axs[2]; style(ax)
ax.yaxis.grid(False); ax.xaxis.grid(True, color=GRID, lw=1)
segments = [(pr_A_hacks, "Passed visible tests,\nfailed hidden tests (hack)", "#d0d5da", "//"),
            (pr_A_failed_visible, "Failed visible tests", "#eef0f2", ""),
            (pr_A_verified, "Actually fixed", COLOR["memory"], "")]
left = 0
for n, label, color, hatch in segments:
    if n:
        ax.barh([0], [n], 0.5, left=left, color=color, hatch=hatch, edgecolor="white", label=label)
        ax.text(left + n / 2, 0, str(n), ha="center", va="center", color=INK, fontsize=12, fontweight="bold")
    left += n
ax.text(pr_A_runs, -0.42, f"Actually fixed: {pr_A_verified}/{pr_A_runs}", ha="right", va="center",
        color=INK, fontsize=10.5, fontweight="bold")
ax.set_xlim(0, pr_A_runs); ax.set_ylim(-0.6, 1.25)
ax.set_yticks([])
ax.set_xlabel(f"Plain retry runs on family A (of {pr_A_runs})", color=MUTED)
ax.legend(frameon=False, loc="upper left", fontsize=9.5, labelcolor=INK, handlelength=1.6)
ax.set_title(f"Plain retry: {pr_A_hacks} of {pr_A_runs} 'fixes' were hacks", loc="left", color=INK,
             fontweight="bold", fontsize=13, pad=12)

fig.suptitle(f"Reflex on 4 held-out tasks: {3 * table['memory']['n']} runs, same model in every arm",
             x=0.012, ha="left", color=INK, fontsize=15, fontweight="bold", y=1.0)
fig.text(0.012, -0.04,
         "Feasibility result: 2 tasks per family × 5 repeats (repeats not independent). "
         "Verified = passes protected hidden tests. Frozen code 26b79a7, mem-v1 c701ea5e, pre-registered 67bc540.",
         color=MUTED, fontsize=9.5, ha="left")
plt.tight_layout()
OUT.parent.mkdir(exist_ok=True)
fig.savefig(OUT, dpi=160, bbox_inches="tight", facecolor="white")
print(f"wrote {OUT.relative_to(ROOT)}")
print({a: table[a] for a in ARMS}, "plain_retry A: hacks", pr_A_hacks, "failed visible", pr_A_failed_visible,
      "verified", pr_A_verified, "of", pr_A_runs)
