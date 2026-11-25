"""Draw ledger: every scored submission (Draw) of the team, read from the Kaggle listing.

The Kaggle submissions listing is the source of truth; ``experiments/draws.csv`` is a
committed copy of it with each Draw's bundle, kernel version, draw number and Failed-draw
flag resolved. ``experiments/slot.yaml`` holds the slot rotation. This module never submits:
``next_draw`` only says what today's draw is and prints the command that would submit it.
Terms (Draw, Failed draw, Daily slot, Final pick) are defined in CONTEXT.md.
"""

from __future__ import annotations

import csv
import io
import re
import shlex
import statistics
from dataclasses import astuple, dataclass, fields
from datetime import date
from pathlib import Path
from typing import Any

import yaml

FAILED_MAX_TASKS = 2
HEALTHY_MEDIAN_TASKS = 7
FINAL_PICK_ROWS = 5
LISTING_PAGE_SIZE = 200  # the Kaggle CLI maximum; a full page may be truncated

# Exit codes of ``g4 draws next``: the daily loop submits only on SUBMIT.
SUBMIT, PENDING, SLOT_USED, PAUSED = 0, 3, 4, 5

_BUNDLE_RE = re.compile(r"^(?P<bundle>[\w.-]+) (?P<hash>[0-9a-f]{12})\b")
_KERNEL_RE = re.compile(r"\bkernel v(\d+)\b")
_DRAW_RE = re.compile(r"\bdaily draw (\d+)\b")
# Any status other than COMPLETE or ERROR counts as pending, so `next` fails closed.
_SETTLED = {"COMPLETE": "complete", "ERROR": "error"}


class LedgerError(ValueError):
    """The listing or the slot config cannot be turned into a consistent ledger."""


@dataclass(frozen=True)
class SlotConfig:
    """The slot rotation and the facts needed to name and submit a draw."""

    raw: dict[str, Any]
    competition: str
    kernel: str
    public_tasks: int
    pause: bool
    description_suffix: str
    kernels: dict[int, tuple[str, str]]  # kernel version -> (bundle, bundle hash)
    rotation: tuple[int, ...]  # draw n goes to rotation[n % len(rotation)]
    backfill: dict[str, dict[str, int]]  # submission ref -> {"draw": n, "kernel": v}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> SlotConfig:
        try:
            kernels = {int(v): (k["bundle"], k["hash"]) for v, k in raw["kernels"].items()}
            rotation = tuple(int(v) for v in raw["rotation"])
            config = cls(
                raw=raw,
                competition=raw["competition"],
                kernel=raw["kernel"],
                public_tasks=int(raw["public_tasks"]),
                pause=bool(raw.get("pause", False)),
                description_suffix=raw["description_suffix"],
                kernels=kernels,
                rotation=rotation,
                backfill={str(r): dict(b) for r, b in (raw.get("backfill") or {}).items()},
            )
        except (KeyError, TypeError, ValueError) as e:
            raise LedgerError(f"slot config is missing or has a bad field: {e}") from e
        unknown = [v for v in rotation if v not in kernels]
        if not rotation or unknown:
            raise LedgerError(f"rotation must be a non-empty list of known kernel versions, got {list(rotation)}")
        return config

    @classmethod
    def load(cls, path: str | Path) -> SlotConfig:
        return cls.from_dict(yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {})


@dataclass(frozen=True)
class Draw:
    ref: str
    date: str  # UTC timestamp as Kaggle prints it
    draw: int | None
    bundle: str
    bundle_hash: str
    kernel: int | None
    status: str  # complete | pending | error
    score: float | None
    flag: str  # ok | failed | unrated, empty when not scored


@dataclass(frozen=True)
class Decision:
    code: int
    reason: str
    draw: int | None = None
    kernel: int | None = None
    message: str = ""
    command: str = ""


def _listing_rows(text: str) -> list[dict[str, str]]:
    lines = text.splitlines(keepends=True)
    start = next((i for i, line in enumerate(lines) if line.startswith("ref,")), None)
    if start is None:
        raise LedgerError("no CSV header ('ref,...') in the submissions listing")
    return list(csv.DictReader(io.StringIO("".join(lines[start:]))))


def _parse_row(row: dict[str, str], slot: SlotConfig) -> Draw:
    ref, desc = row["ref"].strip(), row["description"]
    found = _BUNDLE_RE.match(desc)
    bundle, bundle_hash = (found["bundle"], found["hash"]) if found else ("", "")
    kernel_m, draw_m = _KERNEL_RE.search(desc), _DRAW_RE.search(desc)
    fill = slot.backfill.get(ref, {})
    kernel = int(kernel_m[1]) if kernel_m else fill.get("kernel")
    draw = int(draw_m[1]) if draw_m else fill.get("draw")
    if kernel is not None and kernel in slot.kernels and slot.kernels[kernel][1] != bundle_hash:
        raise LedgerError(
            f"submission {ref} names bundle hash {bundle_hash!r} but kernel v{kernel} "
            f"holds {slot.kernels[kernel][1]!r} in the slot config"
        )
    status = _SETTLED.get(row["status"].strip().rsplit(".", 1)[-1].upper(), "pending")
    score = float(row["publicScore"]) if row.get("publicScore", "").strip() else None
    return Draw(ref, row["date"].strip(), draw, bundle, bundle_hash, kernel, status, score, "")


def _flag(draw: Draw, others: list[Draw], public_tasks: int) -> str:
    if draw.score is None:
        return ""
    if not others:
        return "unrated"
    tasks = round(draw.score * public_tasks)
    median_others = statistics.median(round(o.score * public_tasks) for o in others)
    return "failed" if tasks <= FAILED_MAX_TASKS and median_others >= HEALTHY_MEDIAN_TASKS else "ok"


def build_ledger(listing: str, slot: SlotConfig) -> list[Draw]:
    """Turn the ``kaggle competitions submissions --csv`` output into Draws, newest first."""
    rows = _listing_rows(listing)
    if len(rows) >= LISTING_PAGE_SIZE:
        raise LedgerError(f"listing has {len(rows)} rows, a full page of {LISTING_PAGE_SIZE}: it may be truncated")
    draws = [_parse_row(row, slot) for row in rows]
    scored = [d for d in draws if d.score is not None]

    def group(d: Draw) -> str:
        return d.bundle_hash or d.ref

    return [
        Draw(**{**_as_dict(d), "flag": _flag(d, [o for o in scored if group(o) == group(d) and o.ref != d.ref], slot.public_tasks)})
        for d in draws
    ]


def check_listing_covers(old: list[Draw], new: list[Draw]) -> None:
    """Refuse a fresh listing that lost submissions the ledger already holds (wrong account, CLI change)."""
    if old and not new:
        raise LedgerError("the fresh listing has no submissions but the ledger has some; not overwriting it")
    missing = {d.ref for d in old} - {d.ref for d in new}
    if missing:
        raise LedgerError(f"the fresh listing drops {len(missing)} known submissions ({', '.join(sorted(missing)[:3])}...); not overwriting the ledger")


def _as_dict(d: Draw) -> dict[str, Any]:
    return {f.name: getattr(d, f.name) for f in fields(Draw)}


def write_ledger(path: str | Path, draws: list[Draw]) -> None:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow([f.name for f in fields(Draw)])
    for d in draws:
        writer.writerow(["" if v is None else v for v in astuple(d)])
    Path(path).write_text(out.getvalue(), encoding="utf-8")


def read_ledger(path: str | Path) -> list[Draw]:
    rows = csv.DictReader(io.StringIO(Path(path).read_text(encoding="utf-8")))

    def opt_int(v: str) -> int | None:
        return int(v) if v else None

    return [
        Draw(
            ref=r["ref"], date=r["date"], draw=opt_int(r["draw"]), bundle=r["bundle"],
            bundle_hash=r["bundle_hash"], kernel=opt_int(r["kernel"]), status=r["status"],
            score=float(r["score"]) if r["score"] else None, flag=r["flag"],
        )
        for r in rows
    ]


def next_draw(draws: list[Draw], slot: SlotConfig, today: date) -> Decision:
    """Say whether today's Daily slot is free and, if so, which draw goes in it."""
    if not draws:
        raise LedgerError("the Draw ledger is empty; run `g4 draws sync` against the right Kaggle account first")
    if slot.pause:
        return Decision(PAUSED, "slot rotation is paused in the slot config")
    pending = [d.ref for d in draws if d.status == "pending"]
    if pending:
        return Decision(PENDING, f"submission {', '.join(pending)} is still pending")
    today_s = today.isoformat()
    used = [d.ref for d in draws if d.date[:10] == today_s]
    if used:
        return Decision(SLOT_USED, f"{today_s} already has submission {', '.join(used)}")
    numbered = [d.draw for d in draws if d.draw is not None]
    n = max(numbered, default=0) + 1
    kernel = slot.rotation[n % len(slot.rotation)]
    bundle, bundle_hash = slot.kernels[kernel]
    message = f"{bundle} {bundle_hash}, kernel v{kernel}, daily draw {n}, {slot.description_suffix}"
    command = shlex.join(
        ["kaggle", "competitions", "submit", slot.competition, "-k", slot.kernel,
         "-f", "submission.zip", "-v", str(kernel), "-m", message]
    )
    return Decision(SUBMIT, f"draw {n} goes to kernel v{kernel} ({bundle})", n, kernel, message, command)


def report(draws: list[Draw]) -> str:
    """Per-bundle mean (Failed draws left out), failure rate and the Final pick candidates."""
    scored = [d for d in draws if d.score is not None]
    by_bundle: dict[str, list[Draw]] = {}
    for d in scored:
        by_bundle.setdefault(d.bundle or d.ref, []).append(d)

    def mean_kept(ds: list[Draw]) -> float:
        kept = [d.score for d in ds if d.flag != "failed"]
        return statistics.fmean(kept) if kept else 0.0

    lines = ["Per bundle (mean leaves out Failed draws):"]
    for name, ds in sorted(by_bundle.items(), key=lambda kv: -mean_kept(kv[1])):
        failed = sum(d.flag == "failed" for d in ds)
        scores = [d.score for d in ds]
        lines.append(
            f"{name}  n={len(ds)}  mean={mean_kept(ds):.3f}  failed={failed}/{len(ds)}  "
            f"min={min(scores):.2f}  max={max(scores):.2f}"
        )
    pending = [d for d in draws if d.status == "pending"]
    if pending:
        lines.append(f"pending: {', '.join(f'{d.ref} ({d.bundle})' for d in pending)}")

    healthy = sorted((d for d in scored if d.flag != "failed"), key=lambda d: (-d.score, d.date))
    lines.append("")
    lines.append("Final pick candidates (advisory; highest public score, earlier date wins ties):")
    lines.extend(
        f"{d.ref}  {d.date[:10]}  {d.bundle}  draw {d.draw if d.draw is not None else '-'}  {d.score:.2f}  {d.flag}"
        for d in healthy[:FINAL_PICK_ROWS]
    )
    return "\n".join(lines)
