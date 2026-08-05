#!/usr/bin/env python3
"""Build a clean release bundle for the template-ia plugin.

The bundle includes source files only and excludes runtime output such as
.agents/, caches, temp folders, and local test artifacts.
"""

from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "dist" / "template-ia-release"
CLAUDE_PLUGIN_MANIFEST = ROOT / ".claude-plugin" / "plugin.json"
CODEX_PLUGIN_MANIFEST = ROOT / ".codex-plugin" / "plugin.json"

TOP_LEVEL_FILES = [
    "README.md",
    "INSTALL.md",
    "LICENSE",
    "install.sh",
]

TOP_LEVEL_DIRS = [
    ".claude-plugin",
    ".codex-plugin",
    "commands",
    "hooks",
    "scripts",
    "skills",
    "templates",
]

EXCLUDED_DIR_NAMES = {
    ".agents",
    ".git",
    ".venv",
    "__pycache__",
    "dist",
    "tests",
}

EXCLUDED_FILE_NAMES = {
    "NEXT_STEPS.md",
}


def read_version(manifest_path: Path) -> str:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    version = data.get("version")
    if not version:
        raise ValueError(f"Missing version in {manifest_path}")
    return str(version)


def resolve_release_version() -> str:
    versions = {
        read_version(CLAUDE_PLUGIN_MANIFEST),
        read_version(CODEX_PLUGIN_MANIFEST),
    }
    if len(versions) != 1:
        raise ValueError(
            "Plugin manifest versions do not match: " + ", ".join(sorted(versions))
        )
    return versions.pop()


def safe_rmtree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def safe_unlink(path: Path) -> None:
    if path.exists():
        path.unlink()


def cleanup_release_family(out_dir: Path) -> None:
    parent = out_dir.parent
    if not parent.exists():
        return
    prefix = out_dir.name
    for candidate in parent.iterdir():
        if not candidate.name.startswith(prefix):
            continue
        if candidate.is_dir():
            shutil.rmtree(candidate)
        else:
            candidate.unlink()


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def should_skip(rel: Path) -> bool:
    return any(part in EXCLUDED_DIR_NAMES or part.startswith("tmp") for part in rel.parts)


def copy_tree(src: Path, dst: Path) -> list[str]:
    copied: list[str] = []
    for item in src.rglob("*"):
        if item.is_dir():
            continue
        rel = item.relative_to(ROOT)
        if should_skip(rel):
            continue
        if rel.name in EXCLUDED_FILE_NAMES:
            continue
        target = dst / rel
        copy_file(item, target)
        copied.append(str(rel).replace("\\", "/"))
    return copied


def write_manifest(out_dir: Path, version: str, copied: list[str]) -> None:
    manifest = {
        "name": "template-ia",
        "version": version,
        "suggested_tag": f"v{version}",
        "source_root": str(ROOT).replace("\\", "/"),
        "output_root": str(out_dir).replace("\\", "/"),
        "included_files": copied,
        "excluded_dirs": sorted(EXCLUDED_DIR_NAMES),
        "excluded_files": sorted(EXCLUDED_FILE_NAMES),
    }
    (out_dir / "release-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def zip_path_for(source_dir: Path) -> Path:
    return Path(str(source_dir) + ".zip")


def zip_directory(source_dir: Path) -> Path:
    zip_path = zip_path_for(source_dir)
    safe_unlink(zip_path)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in source_dir.rglob("*"):
            if path.is_file():
                zf.write(path, arcname=path.relative_to(source_dir))
    return zip_path


def build_release(out_dir: Path, version: str) -> list[str]:
    safe_rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    for filename in TOP_LEVEL_FILES:
        src = ROOT / filename
        if src.exists():
            copy_file(src, out_dir / filename)
            copied.append(filename)

    for dirname in TOP_LEVEL_DIRS:
        src = ROOT / dirname
        if src.exists():
            copied.extend(copy_tree(src, out_dir))

    write_manifest(out_dir, version, copied)
    zip_directory(out_dir)
    return copied


def duplicate_versioned_bundle(out_dir: Path, version: str) -> Path:
    versioned_dir = out_dir.parent / f"{out_dir.name}-v{version}"
    safe_rmtree(versioned_dir)
    shutil.copytree(out_dir, versioned_dir)
    zip_directory(versioned_dir)
    return versioned_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a clean release bundle for template-ia.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output directory for the release bundle")
    parser.add_argument(
        "--versioned",
        action="store_true",
        help="Also emit a semver-tagged sibling bundle and zip using the plugin version",
    )
    args = parser.parse_args()

    out_dir = Path(args.out).resolve()
    cleanup_release_family(out_dir)
    version = resolve_release_version()
    copied = build_release(out_dir, version)

    print(f"Created: {out_dir}")
    print(f"Created: {zip_path_for(out_dir)}")
    if args.versioned:
        versioned_dir = duplicate_versioned_bundle(out_dir, version)
        print(f"Created: {versioned_dir}")
        print(f"Created: {zip_path_for(versioned_dir)}")
    print(f"Version: {version}")
    print(f"Suggested tag: v{version}")
    print(f"Files included: {len(copied)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
