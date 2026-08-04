#!/usr/bin/env python3
"""Advisory scan of a generated library for injected instructions.

Threat model
------------
This skill reads documents it did not author and writes files that a host agent
later loads *as instructions*. That is a laundering path: text that would be
treated as untrusted data inside a PDF becomes trusted instruction text once it
has been distilled into a SKILL.md. Nothing in the pipeline re-establishes the
boundary, so this scan does — after generation, before the library is used.

What it looks for is text that is anomalous *for a book distillation*:
directives aimed at the reading agent, claims of authority, requests for
credentials, shell or network egress, and concealment. A reference file
legitimately says "When X, do Y" in the author's voice; it has no reason to
mention a system prompt, an API key, or `curl`.

Advisory by design: it reports and, with --strict, fails. It cannot prove
absence, and a clean report is not a safety guarantee.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

HIGH, MEDIUM, LOW = "HIGH", "MEDIUM", "LOW"


@dataclass(frozen=True)
class Rule:
    name: str
    severity: str
    pattern: re.Pattern[str]
    why: str


def _c(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


RULES: tuple[Rule, ...] = (
    Rule("instruction-override", HIGH,
         _c(r"\b(ignore|disregard|forget)\b[^.\n]{0,40}\b(previous|prior|above|earlier|all)\b"
            r"[^.\n]{0,20}\b(instruction|prompt|rule|direction)s?\b"),
         "attempts to cancel the host agent's instructions"),
    Rule("identity-override", HIGH,
         _c(r"\byou are (now|actually|really)\b|\bfrom now on,? you\b|\bact as if you\b"),
         "attempts to reassign the agent's identity"),
    Rule("system-prompt-reference", HIGH,
         _c(r"\bsystem prompt\b|</?(system|assistant|human|user)>|\[/?INST\]"),
         "refers to or forges conversation structure"),
    Rule("concealment", HIGH,
         _c(r"\b(do not|don't|never)\b[^.\n]{0,30}\b(tell|inform|mention|show|reveal)\b"
            r"[^.\n]{0,20}\b(the )?(user|human|owner)\b"),
         "instructs the agent to hide activity from the user"),
    Rule("credential-solicitation", HIGH,
         # The gap allows dots, because the target may itself start with one
         # (".env"); a \b before a dot is not a word boundary and would never fire.
         _c(r"\b(send|provide|reveal|print|output|paste|enter|export)\b[^\n]{0,40}?"
            r"(\bapi[ _-]?key\b|\bpassword\b|\bsecret\b|\btoken\b|\bcredential|"
            r"\.env\b|\bprivate key\b)"),
         "asks for secrets"),
    Rule("shell-execution", HIGH,
         _c(r"\b(curl|wget|nc|netcat)\b[^\n]{0,80}https?://|"
            r"\brm\s+-rf\b|\bchmod\s+\+x\b|\b(bash|sh)\s+-c\b|\|\s*(bash|sh)\b"),
         "embeds a command that fetches or destroys"),
    Rule("exfiltration", HIGH,
         _c(r"\b(send|post|upload|report|forward)\b[^.\n]{0,40}\bto\b[^.\n]{0,20}https?://|"
            r"https?://[^\s)]{0,120}[?&](data|content|q|text|payload|body)="),
         "moves content to an external endpoint"),

    Rule("authority-claim", MEDIUM,
         _c(r"\b(authori[sz]ed by|on behalf of|approved by|mandated by)\b[^.\n]{0,30}"
            r"\b(anthropic|openai|google|admin|administrator|security team|the system)\b|"
            r"\bas (your|the) (administrator|supervisor|developer)\b"),
         "claims an authority the text cannot have"),
    Rule("tool-directive", MEDIUM,
         _c(r"\b(run|execute|invoke|call)\b[^.\n]{0,30}\b(the following|this) "
            r"(command|script|code|tool)\b"),
         "directs the agent to execute something"),
    Rule("urgency-pressure", MEDIUM,
         _c(r"\b(urgent|immediately|right now|without delay|before (you )?(respond|continue))\b"
            r"[^.\n]{0,40}\b(must|need to|have to|should)\b"),
         "applies pressure to bypass review"),
    Rule("file-access-directive", MEDIUM,
         _c(r"\b(read|open|cat|access|list)\b[^.\n]{0,30}"
            r"(~/\.\w+|/etc/\w+|\.ssh|\.aws|id_rsa|\.git/config)"),
         "points the agent at sensitive local paths"),

    Rule("invisible-characters", LOW,
         re.compile(r"[​-‏‪-‮⁠-⁤﻿]"),
         "hidden characters a reviewer cannot see"),
)

# A distillation cites its source; it has no reason to link anywhere else.
EXTERNAL_LINK = re.compile(r"\[[^\]]*\]\((https?://[^)]+)\)")
ALLOWED_LINK_HOSTS = frozenset({
    "github.com", "www.github.com", "doi.org", "www.doi.org",
    "en.wikipedia.org", "archive.org", "web.archive.org",
})


@dataclass(frozen=True)
class Finding:
    severity: str
    rule: str
    why: str
    file: str
    line: int
    excerpt: str


def _excerpt(line: str, limit: int = 120) -> str:
    line = line.strip()
    return line if len(line) <= limit else line[: limit - 1] + "…"


def scan_text(text: str, filename: str) -> list[Finding]:
    findings: list[Finding] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for rule in RULES:
            if rule.pattern.search(line):
                findings.append(Finding(rule.severity, rule.name, rule.why,
                                        filename, lineno, _excerpt(line)))
        for url in EXTERNAL_LINK.findall(line):
            host = re.sub(r"^https?://", "", url).split("/")[0].split(":")[0].lower()
            if host not in ALLOWED_LINK_HOSTS:
                findings.append(Finding(LOW, "external-link",
                                        "links off to a host the distillation did not need",
                                        filename, lineno, _excerpt(url)))
    return findings


def scan_path(target: Path) -> list[Finding]:
    files = sorted(target.rglob("*.md")) if target.is_dir() else [target]
    findings: list[Finding] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            findings.append(Finding(LOW, "unreadable", str(exc), str(path), 0, ""))
            continue
        findings.extend(scan_text(text, str(path)))
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Scan a generated library for injected instructions.")
    ap.add_argument("target", type=Path, help="library directory or a single .md file")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 on any HIGH finding (default: advisory, always exit 0)")
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args(argv)

    if not args.target.exists():
        print(f"x no such path: {args.target}", file=sys.stderr)
        return 2

    findings = scan_path(args.target)
    order = {HIGH: 0, MEDIUM: 1, LOW: 2}
    findings.sort(key=lambda f: (order[f.severity], f.file, f.line))

    if args.as_json:
        print(json.dumps([f.__dict__ for f in findings], indent=2, ensure_ascii=False))
    elif not findings:
        print(f"clean — no injected-instruction patterns in {args.target}")
        print("(advisory: a clean report is not a guarantee)")
    else:
        for f in findings:
            print(f"[{f.severity:<6}] {f.rule} — {f.why}\n    {f.file}:{f.line}: {f.excerpt}")
        counts = {s: sum(1 for f in findings if f.severity == s) for s in (HIGH, MEDIUM, LOW)}
        print(f"\n{counts[HIGH]} high, {counts[MEDIUM]} medium, {counts[LOW]} low")
        print("Review before loading this library. Distilled text should carry the author's "
              "ideas, never directions aimed at the reading agent.")

    if args.strict and any(f.severity == HIGH for f in findings):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
