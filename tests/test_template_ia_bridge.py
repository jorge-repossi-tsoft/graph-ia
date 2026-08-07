import importlib.util
import shutil
import sys
import uuid
from pathlib import Path
import unittest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / 'scripts' / 'template-ia.py'
SPEC = importlib.util.spec_from_file_location('template_ia', SCRIPT_PATH)
template_ia = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = template_ia
SPEC.loader.exec_module(template_ia)


def _fresh_report():
    return {
        "created": [], "skipped": [], "migrated": [], "migration_skipped": [],
        "folders_created": [], "bridges_created": [], "bridges_appended": [], "bridges_skipped": [],
        "bridges_updated": [], "bridges_stale": [],
        "index_stats": None, "index_skipped": False, "git_reconciled": None,
        "docs_updated": [], "docs_backed_up": [],
    }


class BridgeSyncTests(unittest.TestCase):
    def setUp(self):
        self.repo = Path(__file__).resolve().parent / f'_tmp_bridge_{uuid.uuid4().hex}'
        self.repo.mkdir(parents=True, exist_ok=False)

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_fresh_install_writes_single_bridge_block(self):
        report = _fresh_report()
        template_ia.place_bridge(str(self.repo), "AGENTS.md", report, legacy_exists=False)

        content = (self.repo / "AGENTS.md").read_text(encoding="utf-8")
        self.assertEqual(content.count(template_ia.BRIDGE_MARKER), 1)
        self.assertEqual(content.count(template_ia.BRIDGE_END_MARKER), 1)
        self.assertNotIn(template_ia.LEGACY_LINE_PLACEHOLDER, content)

    def test_update_resyncs_stale_block_and_preserves_user_content(self):
        agents_path = self.repo / "AGENTS.md"
        agents_path.write_text(
            "# AGENTS.md\n"
            "Nota del usuario antes del bloque.\n\n"
            f"{template_ia.BRIDGE_MARKER}\n"
            "Contenido viejo/desactualizado del bridge.\n"
            f"{template_ia.BRIDGE_END_MARKER}\n"
            "\n## Notas del equipo\nEsto no debe borrarse.\n",
            encoding="utf-8",
        )

        report = _fresh_report()
        template_ia.place_bridge(str(self.repo), "AGENTS.md", report, legacy_exists=False, update=False)
        self.assertIn(str(agents_path), report["bridges_stale"])
        self.assertIn("Contenido viejo/desactualizado", agents_path.read_text(encoding="utf-8"))

        report = _fresh_report()
        template_ia.place_bridge(str(self.repo), "AGENTS.md", report, legacy_exists=False, update=True)
        content = agents_path.read_text(encoding="utf-8")

        self.assertIn(str(agents_path), report["bridges_updated"])
        self.assertNotIn("Contenido viejo/desactualizado", content)
        self.assertIn("Nota del usuario antes del bloque.", content)
        self.assertIn("Esto no debe borrarse.", content)
        self.assertEqual(content.count(template_ia.BRIDGE_MARKER), 1)
        self.assertEqual(content.count(template_ia.BRIDGE_END_MARKER), 1)

    def test_update_is_idempotent(self):
        report = _fresh_report()
        template_ia.place_bridge(str(self.repo), "AGENTS.md", report, legacy_exists=False)

        first = (self.repo / "AGENTS.md").read_text(encoding="utf-8")

        report2 = _fresh_report()
        template_ia.place_bridge(str(self.repo), "AGENTS.md", report2, legacy_exists=False, update=True)
        second = (self.repo / "AGENTS.md").read_text(encoding="utf-8")

        self.assertEqual(first, second)
        self.assertEqual(report2["bridges_skipped"], [str(self.repo / "AGENTS.md")])
        self.assertEqual(report2["bridges_updated"], [])

    def test_legacy_format_without_end_marker_is_upgraded(self):
        agents_path = self.repo / "AGENTS.md"
        agents_path.write_text(
            "# AGENTS.md\n"
            "Nota del usuario antes del bloque.\n\n"
            f"{template_ia.BRIDGE_MARKER}\n"
            "## GRAPH viejo, sin marcador de cierre\n"
            "- graph/GRAPH.md\n",
            encoding="utf-8",
        )

        report = _fresh_report()
        template_ia.place_bridge(str(self.repo), "AGENTS.md", report, legacy_exists=False, update=True)
        content = agents_path.read_text(encoding="utf-8")

        self.assertIn("Nota del usuario antes del bloque.", content)
        self.assertEqual(content.count(template_ia.BRIDGE_MARKER), 1)
        self.assertEqual(content.count(template_ia.BRIDGE_END_MARKER), 1)

    def test_nested_agents_file_strips_agents_prefix(self):
        nested_dir = self.repo / ".agents"
        nested_dir.mkdir(parents=True)
        (nested_dir / "AGENTS.md").write_text("# nested\n", encoding="utf-8")

        report = _fresh_report()
        template_ia.place_bridge(str(self.repo), "AGENTS.md", report, legacy_exists=False)
        content = (nested_dir / "AGENTS.md").read_text(encoding="utf-8")

        self.assertNotIn(".agents/graph", content)
        self.assertIn("graph/GRAPH.md", content)

    def test_legacy_line_included_only_when_legacy_system_exists(self):
        report = _fresh_report()
        template_ia.place_bridge(str(self.repo), "AGENTS.md", report, legacy_exists=True)
        content = (self.repo / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("legacy-system.md", content)
        self.assertNotIn(template_ia.LEGACY_LINE_PLACEHOLDER, content)


if __name__ == '__main__':
    unittest.main()
