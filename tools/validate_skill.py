#!/usr/bin/env python3
"""Audit a SKILL.md against the rules of a chosen host agent.

This project's SKILL.md claims compatibility with GitHub Copilot CLI, Amp and
Claude Code. A claim nothing checks is a claim waiting to be wrong, so this
validates against each host's rules under a `--lens`.

    ERROR  breaks or degrades the skill on the chosen host; exits 1
    WARN   the host ignores it, or it is a soft guideline; does not exit 1

The lens differences are narrow and stated per rule rather than implied: where
hosts genuinely agree, the rule is shared.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bookrefs.tokens import estimate_tokens, strip_frontmatter  # noqa: E402

LENSES = ("claude", "copilot", "amp")

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
SLUG = re.compile(r"\A[a-z0-9]+(-[a-z0-9]+)*\Z")
FIELD = re.compile(r"^([A-Za-z0-9_-]+):", re.MULTILINE)

NAME_MAX = 64
DESCRIPTION_MAX = 1024
DESCRIPTION_MIN = 40
BODY_SOFT_LIMIT = 12_000       # a SKILL.md this long is a manual, not a router
RESERVED_WORDS = ("claude", "anthropic")

# Frontmatter keys each host understands. A key outside its set is not an
# error — hosts ignore what they do not know — but it is worth surfacing,
# because the author probably expected it to do something.
KNOWN_KEYS = {
    "claude": {"name", "description", "allowed-tools", "license", "metadata", "version"},
    "copilot": {"name", "description", "license", "version"},
    "amp": {"name", "description", "license", "version"},
}

SKILL_ROOTS = {
    "claude": ("~/.claude/skills", ".claude/skills"),
    "copilot": ("~/.copilot/skills", "~/.agents/skills", ".github/skills"),
    "amp": ("~/.config/amp/skills", "~/.config/agents/skills", ".agents/skills"),
}


@dataclass
class Audit:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    facts: dict = field(default_factory=dict)


def parse_frontmatter(text: str) -> tuple[str | None, dict[str, str]]:
    m = FRONTMATTER.match(text)
    if not m:
        return None, {}
    block = m.group(1)
    values: dict[str, str] = {}
    key = None
    for line in block.splitlines():
        hit = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if hit:
            key = hit.group(1)
            values[key] = hit.group(2).strip()
        elif key and line.startswith((" ", "\t")):
            values[key] += " " + line.strip()
    return block, values


def audit(path: Path, lens: str) -> Audit:
    result = Audit()
    text = path.read_text(encoding="utf-8")
    block, fm = parse_frontmatter(text)

    if block is None:
        result.errors.append("no YAML frontmatter — every host requires a --- delimited block")
        return result

    # -- name
    name = fm.get("name", "").strip("\"'")
    if not name:
        result.errors.append("frontmatter is missing `name:`")
    else:
        if not SLUG.match(name):
            result.errors.append(
                f"`name: {name}` must be lowercase letters, digits and hyphens only "
                f"(no spaces, no '&', no underscores)")
        if len(name) > NAME_MAX:
            result.errors.append(f"`name:` is {len(name)} chars, over the {NAME_MAX} limit")
        if any(word in name.lower() for word in RESERVED_WORDS):
            result.errors.append(f"`name: {name}` must not contain "
                                 f"{' or '.join(RESERVED_WORDS)}")
        # Only meaningful for an *installed* skill, where the directory is the
        # skill folder. In a source checkout the parent is the repo root, which
        # is expected to differ and would otherwise warn on every run.
        parent = path.resolve().parent
        installed = not (parent / ".git").exists()
        if installed and parent.name and name != parent.name:
            result.warnings.append(
                f"`name: {name}` differs from its directory '{parent.name}'; "
                f"hosts that resolve skills by directory will disagree about the name")

    # -- description
    description = fm.get("description", "").strip("\"'")
    if not description:
        result.errors.append("frontmatter is missing `description:` — without it the host "
                             "cannot decide when to load the skill")
    else:
        if len(description) < DESCRIPTION_MIN:
            result.errors.append(f"`description:` is {len(description)} chars; under "
                                 f"{DESCRIPTION_MIN} it will not trigger reliably")
        if len(description) > DESCRIPTION_MAX:
            result.warnings.append(f"`description:` is {len(description)} chars, over the "
                                   f"{DESCRIPTION_MAX} guideline")

    # -- host-specific keys
    unknown = set(fm) - KNOWN_KEYS[lens]
    for key in sorted(unknown):
        if key == "allowed-tools" and lens in ("copilot", "amp"):
            result.warnings.append(
                f"`allowed-tools:` is ignored by {lens}; the skill still works, but tool "
                f"restrictions you expect will not apply")
        else:
            result.warnings.append(f"`{key}:` is not a key {lens} recognises")

    # -- body
    body_tokens = estimate_tokens(strip_frontmatter(text))
    result.facts["body_tokens"] = body_tokens
    result.facts["name"] = name
    result.facts["lens"] = lens
    if body_tokens > BODY_SOFT_LIMIT:
        result.warnings.append(
            f"body is ~{body_tokens:,} tokens; over ~{BODY_SOFT_LIMIT:,} a SKILL.md reads as "
            f"a manual rather than a router. Move detail into on-demand reference files.")

    if not re.search(r"^#\s+\S", text, re.MULTILINE):
        result.warnings.append("no `# ` heading in the body")

    result.facts["roots"] = SKILL_ROOTS[lens]
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Audit a SKILL.md for a host agent.")
    ap.add_argument("skill", type=Path, nargs="?", default=Path("SKILL.md"))
    ap.add_argument("--lens", choices=LENSES + ("all",), default="claude")
    args = ap.parse_args(argv)

    if not args.skill.exists():
        print(f"x no such file: {args.skill}", file=sys.stderr)
        return 2

    lenses = LENSES if args.lens == "all" else (args.lens,)
    failed = False
    for lens in lenses:
        result = audit(args.skill, lens)
        print(f"--- lens: {lens}  ({args.skill}, ~{result.facts.get('body_tokens', 0):,} tok body)")
        for w in result.warnings:
            print(f"  ! {w}")
        for e in result.errors:
            print(f"  x {e}")
        if not result.errors and not result.warnings:
            print("  ok")
        elif not result.errors:
            print(f"  ok with {len(result.warnings)} warning(s)")
        else:
            print(f"  failed: {len(result.errors)} error(s)")
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
