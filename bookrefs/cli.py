"""Command-line interface for the extraction runtime."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import dependencies
from .config import SUPPORTED_FORMATS
from .exceptions import BookrefsError, MissingDependency
from .extract import collect_inputs, default_workdir, run


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="extract.py",
        description="Extract one or more documents into full_text.txt + metadata.json.",
    )
    ap.add_argument("inputs", nargs="*", type=Path,
                    help="files, directories, or globs")
    ap.add_argument("--mode", choices=("text", "technical"), default="text",
                    help="technical prefers a layout-aware PDF backend")
    ap.add_argument("--workdir", type=Path, default=None,
                    help=f"output directory (default: {default_workdir()})")
    ap.add_argument("--check", action="store_true",
                    help="report which formats this machine can handle, then exit")
    ap.add_argument("--install-missing", choices=("never", "ask", "auto"), default="never",
                    help="offer to pip-install a missing PDF backend")
    ap.add_argument("--quiet", action="store_true")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.check:
        return 0 if dependencies.report() else 0  # advisory: never fails the run

    if not args.inputs:
        print("x no inputs. Supported extensions: " + " ".join(sorted(SUPPORTED_FORMATS)),
              file=sys.stderr)
        return 2

    # Preflight: only complain about dependencies these inputs actually need.
    try:
        planned = collect_inputs(args.inputs)
    except BookrefsError as exc:
        print(f"x {exc}", file=sys.stderr)
        return 2
    missing = dependencies.missing_for({p.suffix.lower() for p in planned})
    if missing:
        dependencies.offer_install(missing, args.install_missing)
        still = dependencies.missing_for({p.suffix.lower() for p in planned})
        if still and args.install_missing == "never":
            print("\nRun with --install-missing ask, or install the above, then re-run.",
                  file=sys.stderr)

    try:
        result = run(args.inputs, mode=args.mode, workdir=args.workdir)
    except MissingDependency as exc:
        print(f"x {exc}\n  -> {exc.remedy}", file=sys.stderr)
        return 1
    except BookrefsError as exc:
        print(f"x {exc}", file=sys.stderr)
        return 1

    if not args.quiet:
        width = max((len(s.filename) for s in result.sources), default=1)
        print(f"Extracted {len(result.sources)} source(s) -> {result.full_text_path}")
        for s in result.sources:
            print(f"  {s.filename:<{width}}  {s.format:<5} ~{s.pages:>4}p  "
                  f"~{s.estimated_tokens:>8,} tok  {s.chapters_detected:>3} chapters"
                  f"{'  +toc' if s.has_toc else ''}")
        print(f"  {'TOTAL':<{width}}  {'':<5} {'':>5}  ~{result.total_tokens:>8,} tok")
        print(f"Metadata: {result.metadata_path}")

    for f in result.failures:
        print(f"! skipped {f.filename}: {f.error}", file=sys.stderr)

    if not result.sources:
        print("x every input failed to parse", file=sys.stderr)
        return 1
    return 0
