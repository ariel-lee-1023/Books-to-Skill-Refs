#!/usr/bin/env python3
"""Turn a multi-file source into the single file `extract.py` expects.

Why this exists
---------------
Step 1 assumes documents on disk. Sources increasingly are not: a textbook is a
GitHub repository, a documentation site, or a set of chapter URLs. Those can be
downloaded, but downloading is not the hard part — `extract.py` emits one
`SOURCE:` fence per *file*, so handing it a directory of 51 chapter pages
produces 51 "books" and the one-reference-file-per-book contract collapses.

This consolidates one source into one file, **in the order the project itself
declares** (`_toc.yml`, or `index.rst` toctrees followed recursively), so the
chapter spine Step 3 plans against survives.

Usage
-----
    # a local tree, order auto-detected
    python tools/build_corpus.py path/to/docs --out corpus/book.md

    # clone first
    python tools/build_corpus.py https://github.com/org/book --out corpus/book.md

    # a list of chapter URLs, one per line
    python tools/build_corpus.py --urls-from chapters.txt --out corpus/book.md

    # see the order without writing anything
    python tools/build_corpus.py path/to/docs --dry-run

Run once per source, then pass the outputs to `extract.py` together.

Exit codes: 0 ok, 1 nothing to consolidate, 2 usage or fetch failure.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bookrefs.corpus import (  # noqa: E402
    build_plan,
    detect_order,
    render,
)

USER_AGENT = "books-to-skill-refs/build_corpus (+https://github.com/)"
FETCH_TIMEOUT = 60


def clone(url: str, into: Path) -> Path:
    """Shallow-clone `url` into `into`, reusing an existing checkout."""
    target = into / (url.rstrip("/").split("/")[-1].removesuffix(".git") or "source")
    if (target / ".git").is_dir():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "clone", "--depth", "1", url, str(target)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git clone failed: {result.stderr.strip().splitlines()[-1:] or url}")
    return target


def download(urls: list[str], into: Path) -> Path:
    """Fetch each URL into `into`, naming files by their path so order is stable.

    Failures are reported and skipped rather than fatal: one dead chapter link
    should not cost the other fifty.
    """
    into.mkdir(parents=True, exist_ok=True)
    ok = 0
    for i, url in enumerate(urls, start=1):
        stem = "_".join(p for p in urllib.parse.urlparse(url).path.split("/") if p) or f"page{i}"
        name = stem if Path(stem).suffix else f"{stem}.html"
        out = into / f"{i:04d}_{name}"
        if out.exists():
            ok += 1
            continue
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT) as response:
                out.write_bytes(response.read())
            ok += 1
        except (urllib.error.URLError, OSError, ValueError) as exc:
            print(f"! skipped {url}: {exc}", file=sys.stderr)
    print(f"fetched {ok}/{len(urls)} url(s) -> {into}", file=sys.stderr)
    return into


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Consolidate a multi-file source into one corpus file, in declared order.",
        epilog="Ordering is read from _toc.yml or index.rst toctrees; "
               "Sphinx toctrees are followed recursively.",
    )
    ap.add_argument("source", nargs="?",
                    help="local directory, or a git URL to clone")
    ap.add_argument("--urls-from", type=Path, metavar="FILE",
                    help="download the URLs in FILE (one per line) instead")
    ap.add_argument("--out", type=Path, help="write the consolidated corpus here")
    ap.add_argument("--workdir", type=Path,
                    help="where clones and downloads land (default: <out>.src)")
    ap.add_argument("--order", default="auto",
                    choices=["auto", "sphinx", "jupyter-book", "natural"])
    ap.add_argument("--include", action="append", default=None, metavar="GLOB",
                    help="natural order only; repeatable (default: **/*)")
    ap.add_argument("--exclude", action="append", default=[], metavar="GLOB")
    ap.add_argument("--title", help="header line for the corpus (e.g. the book title)")
    ap.add_argument("--show-unreached", action="store_true",
                    help="list files on disk the declared order never mentions")
    ap.add_argument("--dry-run", action="store_true", help="list parts, write nothing")
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args(argv)

    if not args.source and not args.urls_from:
        ap.error("give a source directory, a git URL, or --urls-from")
    if not args.out and not args.dry_run:
        ap.error("--out is required unless --dry-run")

    workdir = args.workdir or (args.out.with_suffix(".src") if args.out else Path("./corpus.src"))

    try:
        if args.urls_from:
            urls = [ln.strip() for ln in args.urls_from.read_text(encoding="utf-8").splitlines()
                    if ln.strip() and not ln.startswith("#")]
            if not urls:
                print("x no urls in the list", file=sys.stderr)
                return 2
            root = download(urls, workdir)
        elif args.source.startswith(("http://", "https://", "git@")):
            root = clone(args.source, workdir)
        else:
            root = Path(args.source)
    except (RuntimeError, OSError) as exc:
        print(f"x {exc}", file=sys.stderr)
        return 2

    if not root.is_dir():
        print(f"x not a directory: {root}", file=sys.stderr)
        return 2

    plan = build_plan(
        root,
        order=args.order,
        include=tuple(args.include) if args.include else ("**/*",),
        exclude=tuple(args.exclude),
    )

    if not plan.count:
        print(f"x nothing to consolidate under {root} "
              f"(order={plan.order}, detected={detect_order(root)})", file=sys.stderr)
        return 1

    if args.as_json:
        print(json.dumps({
            "source": str(root),
            "order": plan.order,
            "parts": [{"rel": p.rel, "caption": p.caption} for p in plan.parts],
            "unreached": plan.unreached,
            "out": str(args.out) if args.out else None,
        }, indent=2))
    else:
        print(f"{plan.count} part(s), order={plan.order}", file=sys.stderr)
        if args.dry_run:
            caption = None
            for part in plan.parts:
                if part.caption != caption:
                    caption = part.caption
                    if caption:
                        print(f"  [{caption}]")
                print(f"    {part.rel}")
        if plan.unreached:
            note = f"{len(plan.unreached)} file(s) not referenced by the declared order"
            print(f"! {note}" + ("" if args.show_unreached else " (--show-unreached to list)"),
                  file=sys.stderr)
            if args.show_unreached:
                for rel in plan.unreached:
                    print(f"    ? {rel}", file=sys.stderr)

    if args.dry_run:
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(plan, title=args.title), encoding="utf-8")
    size_kb = args.out.stat().st_size / 1024
    print(f"wrote {args.out}  ({size_kb:,.0f} KB from {plan.count} part(s))", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
