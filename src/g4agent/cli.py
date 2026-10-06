"""``g4`` command line: validate / package bundles and manage dev splits."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .compare import compare_runs, load_results
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
    splits = write_splits(args.tasks, args.out, oracle_path=args.oracle, force=args.force)
    for name, ids in splits.items():
        print(f"{name:14s} {len(ids):4d} tasks")
    return 0


def _cmd_compare(args: argparse.Namespace) -> int:
    result = compare_runs(load_results(args.run_a), load_results(args.run_b))
    print(result.format(Path(args.run_a).name, Path(args.run_b).name))
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

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
