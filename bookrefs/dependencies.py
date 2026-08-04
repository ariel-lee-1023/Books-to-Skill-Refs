"""What is installed, what is missing, and what to do about it.

Backs `extract.py --check` and the Step 1 preflight. The point is to fail
*before* the user answers content-type and purpose questions, with a remedy
rather than a traceback.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from dataclasses import dataclass

from .config import OPTIONAL_FORMATS, STDLIB_FORMATS


@dataclass(frozen=True)
class Capability:
    formats: str          # human-readable extension list
    requirement: str      # what must be present
    available: bool
    remedy: str = ""      # empty when nothing is needed

    @property
    def status(self) -> str:
        return "ok" if self.available else "missing"


def _pdf_capability() -> Capability:
    from .parsers.pdf import INSTALL_HINT, available_backends
    found = available_backends()
    return Capability(
        formats=".pdf",
        requirement="a PDF backend (" + (", ".join(found) if found else "pymupdf / pdfplumber / pypdf") + ")",
        available=bool(found),
        remedy="" if found else INSTALL_HINT,
    )


def _calibre_capability() -> Capability:
    from .parsers.calibre import INSTALL_HINT, TOOL, is_available
    return Capability(
        formats=" ".join(sorted(ext for ext, fam in OPTIONAL_FORMATS.items() if fam == "calibre")),
        requirement=f"calibre's {TOOL} on PATH",
        available=is_available(),
        remedy="" if is_available() else INSTALL_HINT,
    )


def survey() -> list[Capability]:
    """Every format family and whether this machine can handle it."""
    return [
        Capability(
            formats=" ".join(sorted(STDLIB_FORMATS)),
            requirement="python standard library only",
            available=True,
        ),
        _pdf_capability(),
        _calibre_capability(),
    ]


def missing_for(extensions: set[str]) -> list[Capability]:
    """Capabilities that are missing *and* actually needed for these inputs."""
    needed: list[Capability] = []
    if any(ext == ".pdf" for ext in extensions):
        cap = _pdf_capability()
        if not cap.available:
            needed.append(cap)
    if any(ext in (".mobi", ".azw", ".azw3") for ext in extensions):
        cap = _calibre_capability()
        if not cap.available:
            needed.append(cap)
    return needed


def report(stream=sys.stdout) -> bool:
    """Print the capability table. Returns True if everything is available."""
    caps = survey()
    width = max(len(c.formats) for c in caps)
    print("Extraction capabilities:", file=stream)
    for cap in caps:
        mark = "+" if cap.available else "-"
        print(f"  {mark} {cap.formats:<{width}}  {cap.requirement}", file=stream)
        if cap.remedy:
            print(f"      -> {cap.remedy}", file=stream)
    complete = all(c.available for c in caps)
    print(
        "\nAll formats available."
        if complete else
        "\nSome optional formats are unavailable. Everything else still works.",
        file=stream,
    )
    return complete


def offer_install(caps: list[Capability], policy: str, stream=sys.stderr) -> None:
    """Handle --install-missing for capabilities that pip can actually supply.

    `policy` is one of: never (default), ask, auto. Only PDF backends are
    installable this way; calibre is an application, not a package, so it is
    always reported rather than installed.
    """
    for cap in caps:
        if ".pdf" not in cap.formats:
            print(f"! {cap.formats} needs {cap.requirement}\n  -> {cap.remedy}", file=stream)
            continue
        if policy == "never":
            print(f"! {cap.formats} needs {cap.requirement}\n  -> {cap.remedy}", file=stream)
            continue
        if policy == "ask":
            try:
                answer = input(f"Install pypdf to read PDFs? [y/N] ").strip().lower()
            except EOFError:
                answer = "n"
            if answer not in ("y", "yes"):
                print(f"  -> skipped; {cap.remedy}", file=stream)
                continue
        print("Installing pypdf...", file=stream)
        result = subprocess.run([sys.executable, "-m", "pip", "install", "pypdf"],
                                capture_output=True, text=True, check=False)
        if result.returncode != 0:
            print(f"! pip failed: {(result.stderr or '').strip().splitlines()[-1:]}\n"
                  f"  -> {cap.remedy}", file=stream)
        else:
            importlib.util.find_spec("pypdf")  # refresh the finder cache
            print("Installed.", file=stream)


def which(tool: str) -> str | None:
    return shutil.which(tool)
