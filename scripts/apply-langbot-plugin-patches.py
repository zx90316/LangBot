#!/usr/bin/env python3
"""Apply local langbot-plugin patches into the active virtualenv.

Patches live under patches/langbot-plugin/<version>/ and are copied into
.venv/Lib/site-packages/langbot_plugin/ (Windows) or
.venv/lib/python*/site-packages/langbot_plugin/ (Unix).

Re-run after every ``uv sync`` because sync restores the upstream package.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def find_site_packages(root: Path) -> Path:
    venv = root / ".venv"
    if not venv.is_dir():
        raise SystemExit(f"Virtualenv not found: {venv}")

    if sys.platform == "win32":
        candidate = venv / "Lib" / "site-packages" / "langbot_plugin"
    else:
        lib_dir = venv / "lib"
        matches = list(lib_dir.glob("python*/site-packages/langbot_plugin"))
        if not matches:
            raise SystemExit(f"langbot_plugin not found under {lib_dir}")
        candidate = matches[0]

    if not candidate.is_dir():
        raise SystemExit(f"langbot_plugin package not installed: {candidate}")
    return candidate


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(patch_dir: Path) -> dict:
    manifest_path = patch_dir / "MANIFEST.json"
    if not manifest_path.is_file():
        raise SystemExit(f"Missing manifest: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def installed_langbot_plugin_version() -> str:
    try:
        return version("langbot-plugin")
    except PackageNotFoundError as exc:
        raise SystemExit(
            "langbot-plugin is not installed. Run `uv sync --dev` first."
        ) from exc


def apply_patches(*, check_only: bool) -> int:
    root = repo_root()
    installed_version = installed_langbot_plugin_version()
    patch_dir = root / "patches" / "langbot-plugin" / installed_version

    if not patch_dir.is_dir():
        available = sorted(
            path.name
            for path in (root / "patches" / "langbot-plugin").glob("*")
            if path.is_dir()
        )
        raise SystemExit(
            "No local patch set for langbot-plugin "
            f"{installed_version}. Available: {', '.join(available) or '(none)'}"
        )

    manifest = load_manifest(patch_dir)
    if manifest.get("version") != installed_version:
        raise SystemExit(
            f"Patch manifest version {manifest.get('version')!r} "
            f"does not match installed {installed_version!r}"
        )

    target_root = find_site_packages(root)
    files = manifest.get("files") or []
    if not files:
        raise SystemExit(f"No files listed in {patch_dir / 'MANIFEST.json'}")

    mismatches: list[str] = []
    applied = 0

    for relative in files:
        rel_path = Path(relative)
        source = patch_dir / rel_path
        destination = target_root / rel_path

        if not source.is_file():
            raise SystemExit(f"Patch file missing: {source}")

        if check_only:
            if not destination.is_file():
                mismatches.append(f"missing {rel_path.as_posix()}")
                continue
            if file_sha256(source) != file_sha256(destination):
                mismatches.append(f"outdated {rel_path.as_posix()}")
            continue

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        applied += 1

    if check_only:
        if mismatches:
            print("Patch check failed:")
            for item in mismatches:
                print(f"  - {item}")
            return 1
        print(f"Patch check OK ({len(files)} files match langbot-plugin {installed_version}).")
        return 0

    print(
        f"Applied {applied} patch file(s) to langbot-plugin {installed_version} "
        f"at {target_root}"
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify patched files match without writing.",
    )
    args = parser.parse_args()
    raise SystemExit(apply_patches(check_only=args.check))


if __name__ == "__main__":
    main()
