"""Render the Writeup's figures as PNGs into docs/paper/figures/.

Usage: uv run --with matplotlib python docs/paper/make_figures.py

Numbers are copied from committed sources (experiments/EXPERIMENTS.md, oracle_*.json and the
Kaggle run outputs summarised there), so the figures rebuild without the gitignored results/.
Colors are the validated categorical slots 1-4 (light surface); two of them sit below 3:1
contrast on the surface, so every bar segment carries a direct label and the paper keeps the
same numbers in tables.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUT = Path(__file__).resolve().parent / "figures"
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3df"
TRACK = "#ecebe7"
SLOTS = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100")  # blue, orange, aqua, yellow
DPI = 200

# Leaderboard: public scores per bundle (EXPERIMENTS.md, "Leaderboard submissions").
LEADERBOARD = {
    "public bundle, same archive ×3": [0.12, 0.10, 0.06],
    "v4_guard_budget, same archive ×2": [0.13, 0.10],
    "v3_guard": [0.10],
    "v2_noskill, same archive ×2": [0.13, 0.12],
    "v1_scaffold (skill)": [0.08],
    "v2_fast (skill)": [0.06],
}

# (label, split size, reference-fix ceiling in the Kaggle env, resolved by the agent)
CEILINGS = [
    ("dev30 · v2_fast", 30, 18, 6),
    ("sound40 · v2_fast", 40, 40, 15),
    ("sound40 · v2_noskill", 40, 40, 20),
]

# sound40 outcome breakdown on harness 0.2.11 (EXPERIMENTS.md, "Outcome breakdown").
OUTCOMES = ("resolved", "no patch", "scratch/test files only", "source patch, tests fail")
BREAKDOWN = {"v2_fast (skill)": (15, 12, 3, 10), "v2_noskill": (20, 11, 1, 8)}


def _style(ax: plt.Axes) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=TEXT_2, length=0, labelsize=9)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _figure(width: float, height: float) -> tuple[plt.Figure, plt.Axes]:
    fig, ax = plt.subplots(figsize=(width, height), dpi=DPI)
    fig.patch.set_facecolor(SURFACE)
    _style(ax)
    return fig, ax


def _title(ax: plt.Axes, title: str, subtitle: str) -> None:
    ax.set_title(title, loc="left", color=TEXT, fontsize=11, fontweight="bold", pad=22)
    ax.text(0, 1.03, subtitle, transform=ax.transAxes, color=TEXT_2, fontsize=8.5)


def leaderboard_noise() -> Path:
    fig, ax = _figure(6.4, 2.8)
    labels = list(LEADERBOARD)[::-1]
    for y, label in enumerate(labels):
        scores = LEADERBOARD[label]
        if len(scores) > 1:
            ax.plot([min(scores), max(scores)], [y, y], color=TRACK, linewidth=6, solid_capstyle="round", zorder=1)
        ax.scatter(scores, [y] * len(scores), s=46, color=SLOTS[0], edgecolor=SURFACE, linewidth=1.5, zorder=2)
    ax.set_yticks(range(len(labels)), labels, color=TEXT, fontsize=9)
    ax.set_xlim(0.04, 0.15)
    ax.set_xlabel("public leaderboard score (one task ≈ 0.017)", color=TEXT_2, fontsize=9)
    _title(ax, "Identical bundles move as much as different ones",
           "Each dot is one submission; grey bars span resubmissions of the same archive")
    return _save(fig, "fig1_leaderboard_noise.png")


def ceilings() -> Path:
    fig, ax = _figure(6.4, 2.4)
    for y, (label, size, ceiling, resolved) in enumerate(CEILINGS):
        ax.barh(y, 100, color=TRACK, height=0.62, zorder=1)
        ax.barh(y, 100 * ceiling / size, color="#b8d3f2", height=0.62, zorder=2)
        ax.barh(y, 100 * resolved / size, color=SLOTS[0], height=0.62, zorder=3)
        ax.text(100 * resolved / size - 1.5, y, f"{resolved}", va="center", ha="right", color="white",
                fontsize=8.5, fontweight="bold", zorder=4)
        share = f"{resolved}/{ceiling} solvable" if ceiling < size else f"{resolved}/{size}"
        ax.text(101.5, y, share, va="center", ha="left", color=TEXT_2, fontsize=8.5)
    ax.set_yticks(range(len(CEILINGS)), [c[0] for c in CEILINGS], color=TEXT, fontsize=9)
    ax.set_xlim(0, 100)
    ax.set_xlabel("% of split tasks", color=TEXT_2, fontsize=9)
    _title(ax, "Read dev scores against what the environment can solve",
           "Dark: resolved by the agent · light: reference fix passes on Kaggle · grey: rest of the split")
    return _save(fig, "fig2_ceilings.png")


def outcome_breakdown() -> Path:
    fig, ax = _figure(6.4, 2.3)
    labels = list(BREAKDOWN)
    for y, label in enumerate(labels):
        left = 0
        for count, color, name in zip(BREAKDOWN[label], SLOTS, OUTCOMES):
            ax.barh(y, count, left=left, color=color, height=0.6, edgecolor=SURFACE, linewidth=2,
                    label=name if y == 0 else None)
            if count >= 2:
                ink = "white" if color in (SLOTS[0], SLOTS[1]) else TEXT
                ax.text(left + count / 2, y, str(count), va="center", ha="center", color=ink, fontsize=8.5)
            left += count
    ax.set_yticks(range(len(labels)), labels, color=TEXT, fontsize=9)
    ax.set_xlim(0, 40)
    ax.set_xlabel("sound40 tasks (harness 0.2.11, serial, 5 min / 40 calls)", color=TEXT_2, fontsize=9)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.30), ncol=4, frameon=False, fontsize=8,
              labelcolor=TEXT_2, handlelength=1, columnspacing=1.2)
    _title(ax, "About half of all failures never reach a patch",
           "Outcome of each task, by what the submitted patch contained")
    return _save(fig, "fig3_outcomes.png")


def _save(fig: plt.Figure, name: str) -> Path:
    OUT.mkdir(exist_ok=True)
    path = OUT / name
    fig.savefig(path, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    return path


if __name__ == "__main__":
    for path in (leaderboard_noise(), ceilings(), outcome_breakdown()):
        print(path)
