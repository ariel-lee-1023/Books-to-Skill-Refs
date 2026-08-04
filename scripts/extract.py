#!/usr/bin/env python3
"""Entry point for the extraction runtime.

Kept as a plain script so SKILL.md Step 2 can invoke it by path without the
package being installed:

    python3 scripts/extract.py <paths...> --mode text|technical

Windows consoles default to a legacy code page, which turns any non-ASCII
output into a UnicodeEncodeError. Force UTF-8 before anything prints.
"""

import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# Make the sibling `bookrefs` package importable regardless of the working
# directory this was launched from.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bookrefs.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
