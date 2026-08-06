import importlib.util
import json
import shutil
import sys
import unittest
from pathlib import Path
import uuid

SCRIPT_PATH = Path(__file__).resolve().parents[1] / 'scripts' / 'build-release.py'
SPEC = importlib.util.spec_from_file_location('build_release', SCRIPT_PATH)
build_release = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = build_release
SPEC.loader.exec_module(build_release)


class BuildReleaseTests(unittest.TestCase):
    def test_resolve_release_version_matches_plugin_manifests(self):
        self.assertEqual(build_release.resolve_release_version(), '3.1.0')

    def test_build_release_creates_versioned_bundle(self):
        repo_tests = Path(__file__).resolve().parent
        out_dir = repo_tests / f'_tmp_release_{uuid.uuid4().hex}'
        versioned_dir = None
        try:
            copied = build_release.build_release(out_dir, '3.1.0')
            versioned_dir = build_release.duplicate_versioned_bundle(out_dir, '3.1.0')

            self.assertTrue((out_dir / 'release-manifest.json').exists())
            self.assertTrue(build_release.zip_path_for(out_dir).exists())
            self.assertTrue(versioned_dir.exists())
            self.assertTrue(build_release.zip_path_for(versioned_dir).exists())
            self.assertEqual(
                build_release.zip_path_for(versioned_dir).name,
                f'{versioned_dir.name}.zip',
            )

            manifest = json.loads((out_dir / 'release-manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['version'], '3.1.0')
            self.assertEqual(manifest['suggested_tag'], 'v3.1.0')
            self.assertGreater(len(copied), 0)
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)
            if versioned_dir is not None:
                shutil.rmtree(versioned_dir, ignore_errors=True)

    def test_cleanup_release_family_removes_stale_artifacts(self):
        repo_tests = Path(__file__).resolve().parent
        out_dir = repo_tests / f'_tmp_release_{uuid.uuid4().hex}'
        stale_zip = Path(str(out_dir.parent / f'{out_dir.name}-v3.1') + '.zip')
        out_dir.parent.mkdir(parents=True, exist_ok=True)
        stale_zip.write_text('stale', encoding='utf-8')
        try:
            build_release.cleanup_release_family(out_dir)
            self.assertFalse(stale_zip.exists())
        finally:
            if out_dir.exists():
                shutil.rmtree(out_dir, ignore_errors=True)
            if stale_zip.exists():
                stale_zip.unlink()


if __name__ == '__main__':
    unittest.main()

