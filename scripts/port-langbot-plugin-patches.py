#!/usr/bin/env python3
"""Port langbot-plugin Windows patch hunks from one version onto another."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Hunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[str]


def parse_unified_diff(text: str) -> list[Hunk]:
    hunks: list[Hunk] = []
    current: Hunk | None = None
    for line in text.splitlines():
        if line.startswith("@@"):
            match = re.match(
                r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line
            )
            if not match:
                continue
            old_start = int(match.group(1))
            old_count = int(match.group(2) or "1")
            new_start = int(match.group(3))
            new_count = int(match.group(4) or "1")
            current = Hunk(old_start, old_count, new_start, new_count, [])
            hunks.append(current)
            continue
        if current is not None and line[:1] in {" ", "+", "-"}:
            current.lines.append(line)
    return hunks


def apply_hunk(lines: list[str], hunk: Hunk, fuzz: int = 8) -> bool:
    old_block = [line[1:] for line in hunk.lines if line.startswith(" ") or line.startswith("-")]
    new_block = [line[1:] for line in hunk.lines if line.startswith(" ") or line.startswith("+")]
    if not old_block:
        insert_at = min(max(hunk.old_start - 1, 0), len(lines))
        lines[insert_at:insert_at] = new_block
        return True

    start = max(hunk.old_start - 1 - fuzz, 0)
    end = min(hunk.old_start - 1 + fuzz, len(lines))
    for idx in range(start, end + 1):
        segment = lines[idx : idx + len(old_block)]
        if segment == old_block:
            lines[idx : idx + len(old_block)] = new_block
            return True
    return False


def apply_diff_to_file(target: Path, diff_text: str) -> tuple[bool, list[str]]:
    lines = target.read_text(encoding="utf-8").splitlines()
    failed: list[str] = []
    for hunk in parse_unified_diff(diff_text):
        if not apply_hunk(lines, hunk):
            failed.append(
                f"old_start={hunk.old_start} preview={hunk.lines[:3]!r}"
            )
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return not failed, failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-version", default="0.5.5")
    parser.add_argument("--to-version", required=True)
    parser.add_argument("--upstream-from", type=Path, required=True)
    parser.add_argument("--upstream-to", type=Path, required=True)
    parser.add_argument("--patched-from", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    rel_files = [
        Path("runtime/plugin/mgr.py"),
        Path("runtime/plugin/worker_launcher.py"),
        Path("runtime/app.py"),
    ]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    all_ok = True

    for rel in rel_files:
        upstream_from = args.upstream_from / rel
        patched_from = args.patched_from / rel
        upstream_to = args.upstream_to / rel
        output = args.output_dir / rel
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(upstream_to, output)

        diff_lines: list[str] = []
        import difflib

        from_lines = upstream_from.read_text(encoding="utf-8").splitlines(keepends=True)
        to_lines = patched_from.read_text(encoding="utf-8").splitlines(keepends=True)
        diff_lines = list(
            difflib.unified_diff(
                from_lines,
                to_lines,
                fromfile=str(upstream_from),
                tofile=str(patched_from),
                lineterm="",
            )
        )
        diff_text = "\n".join(diff_lines)
        if not diff_text.strip():
            print(f"{rel.as_posix()}: no changes to port")
            continue

        ok, failed = apply_diff_to_file(output, diff_text)
        if ok:
            print(f"{rel.as_posix()}: ported OK")
        else:
            all_ok = False
            print(f"{rel.as_posix()}: FAILED {len(failed)} hunk(s)")
            for item in failed:
                print(f"  - {item}")

    manifest = {
        "package": "langbot-plugin",
        "version": args.to_version,
        "description": (
            f"Windows local fixes ported from {args.from_version} onto "
            f"{args.to_version} (stdio/WinError, SystemRoot env, auto dependency install)."
        ),
        "files": [path.as_posix() for path in rel_files],
    }
    import json

    (args.output_dir / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
