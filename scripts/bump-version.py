#!/usr/bin/env python3
"""Synchronize the plugin version across Claude and Codex manifests."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = [
    ROOT / '.claude-plugin' / 'plugin.json',
    ROOT / '.codex-plugin' / 'plugin.json',
]
SEMVER_RE = re.compile(r'^\d+\.\d+\.\d+$')


def validate_version(version: str) -> str:
    if not SEMVER_RE.match(version):
        raise ValueError(f'Invalid semver: {version}')
    return version


def update_manifest_version(manifest_path: Path, version: str) -> None:
    data = json.loads(manifest_path.read_text(encoding='utf-8'))
    data['version'] = version
    manifest_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(description='Update plugin manifest versions.')
    parser.add_argument('version', help='Semver to write, for example 3.1.1')
    args = parser.parse_args()

    version = validate_version(args.version)
    for manifest in MANIFESTS:
        update_manifest_version(manifest, version)
        print(f'Updated: {manifest}')
    print(f'Suggested tag: v{version}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
