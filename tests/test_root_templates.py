from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RootTemplateTests(unittest.TestCase):
    def test_agents_template_points_to_installed_graph_paths(self):
        content = (ROOT / 'templates' / 'AGENTS.md').read_text(encoding='utf-8')
        self.assertIn('graph-ia:bridge-block', content)
        self.assertIn('.agents/graph/GRAPH.md', content)
        self.assertIn('.agents/graph/sessions/tasks.md', content)
        self.assertIn('.agents/roles/registry.yml', content)

    def test_claude_template_points_to_installed_graph_paths(self):
        content = (ROOT / 'templates' / 'CLAUDE.md').read_text(encoding='utf-8')
        self.assertIn('graph-ia:bridge-block', content)
        self.assertIn('.agents/graph/GRAPH.md', content)
        self.assertIn('AGENTS.md', content)


if __name__ == '__main__':
    unittest.main()