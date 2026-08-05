import importlib.util
import json
import sys
import unittest
from pathlib import Path
import uuid

SCRIPT_PATH = Path(__file__).resolve().parents[1] / 'scripts' / 'bump-version.py'
SPEC = importlib.util.spec_from_file_location('bump_version', SCRIPT_PATH)
bump_version = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = bump_version
SPEC.loader.exec_module(bump_version)


class BumpVersionTests(unittest.TestCase):
    def test_validate_version_accepts_semver(self):
        self.assertEqual(bump_version.validate_version('3.1.1'), '3.1.1')

    def test_validate_version_rejects_non_semver(self):
        with self.assertRaises(ValueError):
            bump_version.validate_version('3.1')

    def test_update_manifest_version_writes_new_version(self):
        tmp_path = Path(__file__).resolve().parent / f'_tmp_manifest_{uuid.uuid4().hex}.json'
        tmp_path.write_text(json.dumps({'name': 'template-ia', 'version': '0.0.1'}), encoding='utf-8')
        try:
            bump_version.update_manifest_version(tmp_path, '3.1.1')
            data = json.loads(tmp_path.read_text(encoding='utf-8'))
            self.assertEqual(data['version'], '3.1.1')
        finally:
            if tmp_path.exists():
                tmp_path.unlink()


if __name__ == '__main__':
    unittest.main()
