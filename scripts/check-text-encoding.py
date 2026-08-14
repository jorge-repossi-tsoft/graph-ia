#!/usr/bin/env python3
"""Fail fast when a commit introduces invalid UTF-8 or mojibake.

The checker has two modes:
- diff mode (default / --staged / --ref): inspect only added or changed lines so
  legacy encoding problems already present in the repository do not block work.
- --all: full audit of every tracked text file.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOJIBAKE_MARKERS = (
    chr(0x00C3),
    chr(0x00C2),
    ''.join(chr(code) for code in (0x00E2, 0x20AC)),
    ''.join(chr(code) for code in (0x00E2, 0x20AC, 0x2019)),
    ''.join(chr(code) for code in (0x00E2, 0x20AC, 0x201C)),
    ''.join(chr(code) for code in (0x00E2, 0x20AC, 0x201D)),
    ''.join(chr(code) for code in (0x00E2, 0x20AC, 0x2013)),
    ''.join(chr(code) for code in (0x00E2, 0x20AC, 0x2014)),
    ''.join(chr(code) for code in (0x00E2, 0x20AC, 0x2026)),
    chr(0xFFFD),
)
BINARY_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico',
    '.zip', '.gz', '.tgz', '.bz2', '.xz', '.7z',
    '.pdf', '.exe', '.dll', '.so', '.dylib', '.pyd', '.pyc',
}


def run_git(args: list[str]) -> bytes:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace").strip() or "git failed")
    return result.stdout


def tracked_paths() -> list[Path]:
    raw_paths = [chunk for chunk in run_git(["ls-files", "-z"]).split(bytes([0])) if chunk]
    return [Path(chunk.decode("utf-8")) for chunk in raw_paths]


def changed_paths(range_spec: str | None) -> list[Path]:
    if range_spec:
        args = ["diff", "--name-only", "--diff-filter=ACMR", "-z", range_spec]
    else:
        args = ["diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"]
    raw_paths = [chunk for chunk in run_git(args).split(bytes([0])) if chunk]
    return [Path(chunk.decode("utf-8")) for chunk in raw_paths]


def is_binary_path(path: Path) -> bool:
    return path.suffix.lower() in BINARY_EXTENSIONS


def marker_label(marker: str) -> str:
    return marker.encode("unicode_escape").decode("ascii")


def scan_line(line: str, line_no: int) -> list[str]:
    issues: list[str] = []
    for marker in MOJIBAKE_MARKERS:
        if marker in line:
            excerpt = line.strip()
            if len(excerpt) > 140:
                excerpt = excerpt[:137] + "..."
            issues.append(f"{line_no}: mojibake marker {marker_label(marker)} in: {excerpt}")
            break
    return issues


def scan_text(text: str) -> list[str]:
    issues: list[str] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        issues.extend(scan_line(line, line_no))
    return issues


def count_markers(text: str) -> int:
    return sum(text.count(marker) for marker in MOJIBAKE_MARKERS)


def scan_file_on_disk(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return [f"invalid UTF-8: {exc}"]
    return scan_text(text)


def read_blob_text(spec: str, *, replace_errors: bool, missing_ok: bool) -> str:
    result = subprocess.run(["git", "show", spec], cwd=ROOT, capture_output=True, text=False)
    if result.returncode != 0:
        if missing_ok:
            return ""
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace").strip() or f"git show {spec!r} failed")
    return result.stdout.decode("utf-8", errors="replace" if replace_errors else "strict")


def scan_changed_file(path: Path, base_spec: str, target_spec: str) -> list[str]:
    base_text = read_blob_text(base_spec, replace_errors=True, missing_ok=True)
    target_text = read_blob_text(target_spec, replace_errors=True, missing_ok=False)
    base_count = count_markers(base_text)
    target_count = count_markers(target_text)
    if target_count > base_count:
        return [
            f"mojibake marker count increased from {base_count} to {target_count}"
        ]
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--all",
        action="store_true",
        help="scan the full tracked tree instead of only changed lines",
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="scan staged changes (default; accepted for hook compatibility)",
    )
    parser.add_argument(
        "--ref",
        help="scan changes between REF and HEAD",
    )
    args = parser.parse_args()

    if args.all:
        paths = tracked_paths()
        if not paths:
            print("encoding-check: no tracked files to inspect")
            return 0

        failures: list[tuple[Path, list[str]]] = []
        for rel_path in paths:
            if is_binary_path(rel_path):
                continue
            issues = scan_file_on_disk(ROOT / rel_path)
            if issues:
                failures.append((rel_path, issues))
    else:
        range_spec = f"{args.ref}..HEAD" if args.ref else None
        paths = changed_paths(range_spec)
        if not paths:
            print("encoding-check: no changed files to inspect")
            return 0

        failures = []
        for rel_path in paths:
            if is_binary_path(rel_path):
                continue
            posix_path = rel_path.as_posix()
            if args.ref:
                base_spec = f"{args.ref}:{posix_path}"
                target_spec = f"HEAD:{posix_path}"
            else:
                base_spec = f"HEAD:{posix_path}"
                target_spec = f":{posix_path}"
            issues = scan_changed_file(rel_path, base_spec, target_spec)
            if issues:
                failures.append((rel_path, issues))

    if failures:
        print("encoding-check: found text encoding problems", file=sys.stderr)
        for rel_path, issues in failures:
            print(f"- {rel_path.as_posix()}", file=sys.stderr)
            for issue in issues:
                print(f"  - {issue}", file=sys.stderr)
        print(
            "Fix the file content so it is UTF-8 and no longer introduces mojibake in the changed lines.",
            file=sys.stderr,
        )
        return 1

    print(f"encoding-check: ok ({len(paths)} files inspected)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
