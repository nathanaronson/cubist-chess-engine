#!/usr/bin/env python3
"""Verify markdown links and `darwin.*` symbol references resolve.

Walks README.md, docs/**/*.md, plans/**/*.md. For each markdown link:
  [text](relative/path)            -> path must exist
  [text](relative/path#L<n>)       -> path must exist and have >= n lines
  [text](relative/path#L<a>-L<b>)  -> path must exist and have >= b lines
  [text](http(s)://...)            -> skipped (external)
  [text](#anchor)                  -> skipped (in-page)
  [text](mailto:...) etc.          -> skipped (non-file scheme)

For every backtick-quoted token matching a `darwin.` dotted path, attempt
to import-and-getattr the leaf; report any that don't resolve.

Exit code: 0 if all references resolve, 1 otherwise.
Output: one finding per line, grep-friendly: <file>:<line>: <kind>: <detail>
"""

from __future__ import annotations

import importlib
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DOC_GLOBS = [
    ("README.md",),
    ("docs", "**/*.md"),
    ("plans", "**/*.md"),
]

# Markdown link regex. Captures text + target. Skips images (![...](...)).
LINK_RE = re.compile(r"(?<!\!)\[([^\]]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")

# Backtick-quoted symbol that starts with `darwin.`
SYMBOL_RE = re.compile(r"`(darwin(?:\.[A-Za-z_][A-Za-z0-9_]*)+)`")

# Recognized non-file URI schemes to skip.
URI_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")

LINE_ANCHOR_RE = re.compile(r"^L(\d+)(?:-L(\d+))?$")


def collect_doc_files() -> list[Path]:
    files: list[Path] = []
    for pieces in DOC_GLOBS:
        if len(pieces) == 1:
            target = REPO_ROOT / pieces[0]
            if target.is_file():
                files.append(target)
            continue
        base = REPO_ROOT / pieces[0]
        if not base.is_dir():
            continue
        files.extend(sorted(base.glob(pieces[1])))
    # Stable order, deduped.
    seen: set[Path] = set()
    unique: list[Path] = []
    for f in files:
        if f not in seen:
            seen.add(f)
            unique.append(f)
    return unique


def line_count(path: Path) -> int:
    with path.open("rb") as fh:
        return sum(1 for _ in fh)


def resolve_link_target(doc: Path, target: str) -> tuple[Path, str | None]:
    """Return (resolved_path, anchor_or_none). Anchor includes everything after '#'."""
    if "#" in target:
        path_part, anchor = target.split("#", 1)
    else:
        path_part, anchor = target, None
    if path_part == "":
        # Pure in-page anchor — caller filters this out, but be defensive.
        return doc, anchor
    base = doc.parent
    resolved = (base / path_part).resolve()
    return resolved, anchor


def check_link(doc: Path, lineno: int, target: str, findings: list[str]) -> None:
    # Skip external / scheme URIs and pure in-page anchors.
    if target.startswith("#"):
        return
    if URI_SCHEME_RE.match(target):
        return

    path, anchor = resolve_link_target(doc, target)

    rel_doc = doc.relative_to(REPO_ROOT)

    if not path.exists():
        findings.append(
            f"{rel_doc}:{lineno}: missing-path: target '{target}' resolves to "
            f"{path} (not found)"
        )
        return

    if anchor is None:
        return

    m = LINE_ANCHOR_RE.match(anchor)
    if not m:
        # Non-line anchors (#section-headings) — out of scope per spec.
        return

    if not path.is_file():
        findings.append(
            f"{rel_doc}:{lineno}: bad-anchor: line anchor '#{anchor}' on "
            f"non-file '{target}'"
        )
        return

    n_lines = line_count(path)
    start = int(m.group(1))
    end = int(m.group(2)) if m.group(2) else start
    needed = max(start, end)
    if n_lines < needed:
        findings.append(
            f"{rel_doc}:{lineno}: short-file: '{target}' has {n_lines} lines, "
            f"anchor needs {needed}"
        )


def check_symbol(doc: Path, lineno: int, dotted: str, findings: list[str]) -> None:
    rel_doc = doc.relative_to(REPO_ROOT)
    parts = dotted.split(".")
    # Try progressively shorter import paths, then getattr the remainder.
    # E.g. darwin.agents.builder.build_engine ->
    #   try import darwin.agents.builder.build_engine
    #   then import darwin.agents.builder, getattr build_engine
    #   etc.
    for split in range(len(parts), 0, -1):
        module_path = ".".join(parts[:split])
        attr_path = parts[split:]
        try:
            mod = importlib.import_module(module_path)
        except Exception:
            continue
        obj = mod
        ok = True
        for attr in attr_path:
            if not hasattr(obj, attr):
                ok = False
                break
            obj = getattr(obj, attr)
        if ok:
            return
    findings.append(
        f"{rel_doc}:{lineno}: unresolved-symbol: '{dotted}' could not be imported"
    )


def in_code_fence(line_idx: int, fence_state: list[bool]) -> bool:
    return fence_state[line_idx]


def compute_fence_state(lines: list[str]) -> list[bool]:
    """For each line, True if it's inside a fenced code block."""
    state = [False] * len(lines)
    inside = False
    fence_re = re.compile(r"^\s*(```|~~~)")
    for i, line in enumerate(lines):
        if fence_re.match(line):
            inside = not inside
            state[i] = inside  # the fence line itself: skip its content too
            continue
        state[i] = inside
    return state


def scan_file(path: Path, findings: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    fence_state = compute_fence_state(lines)

    for i, line in enumerate(lines, start=1):
        if fence_state[i - 1]:
            continue
        for m in LINK_RE.finditer(line):
            target = m.group(2)
            check_link(path, i, target, findings)
        for m in SYMBOL_RE.finditer(line):
            check_symbol(path, i, m.group(1), findings)


def main() -> int:
    # Make `darwin` importable when this script is run directly.
    backend = REPO_ROOT / "backend"
    if backend.is_dir() and str(backend) not in sys.path:
        sys.path.insert(0, str(backend))

    files = collect_doc_files()
    findings: list[str] = []
    for f in files:
        scan_file(f, findings)

    if findings:
        for line in findings:
            print(line)
        print(f"\n{len(findings)} issue(s) across {len(files)} doc file(s).", file=sys.stderr)
        return 1

    print(f"OK: {len(files)} doc file(s) checked, no issues.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
