"""``g4`` command line: validate / package bundles, manage dev splits and the Draw ledger."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from . import draws as draws_mod
from .compare import compare_runs, load_results, run_label
from .kaggle_ops import render_kernel, render_oracle_kernel, render_submission_kernel
from .package import PackagingError, bundle_hash, package_bundle
from .splits import write_splits
from .validate import validate_bundle

ROOT = Path(__file__).resolve().parents[2]


def _cmd_validate(args: argparse.Namespace) -> int:
    report = validate_bundle(args.bundle)
    print(report.format())
    return 0 if report.ok else 1


def _cmd_package(args: argparse.Namespace) -> int:
    out = args.out or ROOT / "dist" / f"{Path(args.bundle).name}.zip"
    try:
        path = package_bundle(args.bundle, out)
    except PackagingError as e:
        print(e, file=sys.stderr)
        return 1
    print(f"{path}  ({path.stat().st_size / 1024:.1f} KiB, bundle hash {bundle_hash(args.bundle)})")
    return 0


def _cmd_splits(args: argparse.Namespace) -> int:
    splits = write_splits(args.tasks, args.out, oracle_path=args.oracle, empty_path=args.empty, force=args.force)
    for name, ids in splits.items():
        print(f"{name:14s} {len(ids):4d} tasks")
    return 0


def _cmd_compare(args: argparse.Namespace) -> int:
    result = compare_runs(load_results(args.run_a), load_results(args.run_b))
    print(result.format(run_label(args.run_a), run_label(args.run_b)))
    return 0


def _cmd_kernel(args: argparse.Namespace) -> int:
    splits = json.loads(Path(args.splits).read_text(encoding="utf-8"))
    if args.split not in splits:
        print(f"unknown split {args.split!r}; available: {', '.join(splits)}", file=sys.stderr)
        return 1
    run_name = args.name or f"{Path(args.bundle).name}-{args.split}"
    out = render_kernel(args.bundle, splits[args.split], run_name, concurrency=args.concurrency)
    print(f"kernel rendered in {out}\npush with: kaggle kernels push -p {out}")
    return 0


def _cmd_oracle_kernel(args: argparse.Namespace) -> int:
    splits = json.loads(Path(args.splits).read_text(encoding="utf-8"))
    out = render_oracle_kernel(args.bundle, splits[args.split])
    print(f"oracle kernel rendered in {out}\npush with: kaggle kernels push -p {out}")
    return 0


def _cmd_submission_kernel(args: argparse.Namespace) -> int:
    out = render_submission_kernel(args.bundle)
    print(f"submission kernel rendered in {out}\npush with: kaggle kernels push -p {out}")
    return 0


def _fetch_listing(competition: str) -> str:
    """Adapter at the listing seam: the live Kaggle CLI (tests pass --listing instead)."""
    kaggle = shlex.split(os.environ.get("KAGGLE_BIN", "kaggle"))
    if shutil.which(kaggle[0]) is None:
        raise draws_mod.LedgerError(f"kaggle CLI not found ({kaggle[0]!r}); set KAGGLE_BIN")
    proc = subprocess.run([*kaggle, "competitions", "submissions", competition, "--csv",
                           "--page-size", str(draws_mod.LISTING_PAGE_SIZE)],
                          capture_output=True, text=True, timeout=120, check=False)
    if proc.returncode != 0:
        raise draws_mod.LedgerError(f"kaggle submissions failed ({proc.returncode}): {proc.stderr.strip()[-300:]}")
    return proc.stdout


def _cmd_draws(args: argparse.Namespace) -> int:
    try:
        slot = draws_mod.SlotConfig.load(args.slot)
        if args.action == "sync":
            listing = Path(args.listing).read_text(encoding="utf-8") if args.listing else _fetch_listing(slot.competition)
            ledger = draws_mod.build_ledger(listing, slot)
            if Path(args.ledger).exists():
                draws_mod.check_listing_covers(draws_mod.read_ledger(args.ledger), ledger)
            draws_mod.write_ledger(args.ledger, ledger)
            print(f"{len(ledger)} submissions written to {args.ledger}")
            return 0
        ledger = draws_mod.read_ledger(args.ledger)
    except (draws_mod.LedgerError, OSError) as e:
        print(f"g4 draws {args.action}: {e}", file=sys.stderr)
        return 1
    if args.action == "report":
        print(draws_mod.report(ledger))
        return 0
    today = date.fromisoformat(args.today) if args.today else datetime.now(timezone.utc).date()
    try:
        decision = draws_mod.next_draw(ledger, slot, today)
    except draws_mod.LedgerError as e:
        print(f"g4 draws next: {e}", file=sys.stderr)
        return 1
    if args.shell:
        values = {"DRAW": decision.draw or "", "KERNEL_VERSION": decision.kernel or "",
                  "MESSAGE": decision.message, "REASON": decision.reason,
                  "COMPETITION": slot.competition, "KERNEL": slot.kernel}
        print("\n".join(f"{k}={shlex.quote(str(v))}" for k, v in values.items()))
    else:
        print(decision.reason)
        if decision.command:
            print(decision.command)
    return decision.code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="g4")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("validate", help="compile + lint a submission bundle")
    p.add_argument("bundle")
    p.set_defaults(func=_cmd_validate)

    p = sub.add_parser("package", help="validate and zip a bundle into dist/")
    p.add_argument("bundle")
    p.add_argument("--out")
    p.set_defaults(func=_cmd_package)

    p = sub.add_parser("splits", help="create/verify frozen dev splits")
    p.add_argument("--tasks", default=str(ROOT / "data" / "tasks.jsonl"))
    p.add_argument("--out", default=str(ROOT / "experiments" / "splits.json"))
    p.add_argument("--oracle", default=str(ROOT / "experiments" / "oracle_kaggle.json"),
                   help="reference-fix results; their resolvable tasks form the sound40 split")
    p.add_argument("--empty", default=str(ROOT / "experiments" / "empty_local.json"),
                   help="empty-patch results; resolvable tasks that fail with an empty patch form sound<N>")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=_cmd_splits)

    p = sub.add_parser("compare", help="paired per-task comparison of two eval runs (exact McNemar)")
    p.add_argument("run_a", help="run directory or task_results.jsonl")
    p.add_argument("run_b")
    p.set_defaults(func=_cmd_compare)

    p = sub.add_parser("kernel", help="render a Kaggle eval kernel for a bundle and split")
    p.add_argument("bundle")
    p.add_argument("--split", default="dev30")
    p.add_argument("--name")
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--splits", default=str(ROOT / "experiments" / "splits.json"))
    p.set_defaults(func=_cmd_kernel)

    p = sub.add_parser("oracle-kernel", help="render a CPU kernel measuring the Kaggle-env ceiling")
    p.add_argument("bundle")
    p.add_argument("--split", default="full")
    p.add_argument("--splits", default=str(ROOT / "experiments" / "splits.json"))
    p.set_defaults(func=_cmd_oracle_kernel)

    p = sub.add_parser("submission-kernel", help="render a CPU kernel that outputs submission.zip")
    p.add_argument("bundle")
    p.set_defaults(func=_cmd_submission_kernel)

    p = sub.add_parser("draws", help="Draw ledger: sync from Kaggle, report means, say today's draw")
    p.add_argument("action", choices=["sync", "report", "next"])
    p.add_argument("--slot", default=str(ROOT / "experiments" / "slot.yaml"))
    p.add_argument("--ledger", default=str(ROOT / "experiments" / "draws.csv"))
    p.add_argument("--listing", help="sync: read this saved `kaggle ... --csv` output instead of calling Kaggle")
    p.add_argument("--today", help="next: UTC date to decide for (default: today, UTC)")
    p.add_argument("--shell", action="store_true", help="next: print shell-quoted DRAW/KERNEL_VERSION/MESSAGE")
    p.set_defaults(func=_cmd_draws)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
