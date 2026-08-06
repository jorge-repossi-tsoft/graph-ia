
import importlib.util
import shutil
import sys
import uuid
from pathlib import Path
import unittest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / 'scripts' / 'graph-prompt.py'
SPEC = importlib.util.spec_from_file_location('graph_prompt', SCRIPT_PATH)
graph_prompt = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = graph_prompt
SPEC.loader.exec_module(graph_prompt)


class GraphPromptTests(unittest.TestCase):
    def test_parse_task_prompt_extracts_title_and_metadata(self):
        title, metadata = graph_prompt.parse_task_prompt(
            'Crear page path:app/pages/home.tsx type:page priority:high'
        )

        self.assertEqual(title, 'Crear page')
        self.assertEqual(
            metadata,
            {
                'path': 'app/pages/home.tsx',
                'type': 'page',
                'priority': 'high',
            },
        )

    def test_create_task_and_run_updates_backlog_progress_and_knowledge(self):
        repo_tmp = Path(__file__).resolve().parent / f'_tmp_graph_prompt_{uuid.uuid4().hex}'
        repo_tmp.mkdir(parents=True, exist_ok=False)
        try:
            inserted, node_path = graph_prompt.create_task(
                str(repo_tmp),
                'Crear page',
                {'path': 'app/pages/home.tsx', 'type': 'page', 'priority': 'high'},
            )

            self.assertEqual(inserted, '- [ ] Crear page')
            self.assertIsNotNone(node_path)
            self.assertTrue((repo_tmp / '.agents' / 'graph' / 'sessions' / 'tasks.md').exists())
            self.assertTrue((repo_tmp / '.agents' / 'graph' / 'knowledge' / 'nodes' / 'app__pages__home__tsx.json').exists())
            self.assertTrue((repo_tmp / '.agents' / 'graph' / 'knowledge' / 'communities' / 'root.json').exists())

            completed = graph_prompt.complete_tasks(str(repo_tmp), None, 'listo para integrar')
            self.assertEqual(completed, ['Crear page'])

            tasks_text = (repo_tmp / '.agents' / 'graph' / 'sessions' / 'tasks.md').read_text(encoding='utf-8')
            progress_text = (repo_tmp / '.agents' / 'graph' / 'sessions' / 'progress.md').read_text(encoding='utf-8')

            self.assertIn('- [x] Crear page', tasks_text)
            self.assertIn('path: app/pages/home.tsx', tasks_text)
            self.assertIn('Ultima ejecucion de `#run`', progress_text)
            self.assertIn('Que se hizo: listo para integrar', progress_text)
            self.assertIn('Siguiente foco', progress_text)
        finally:
            shutil.rmtree(repo_tmp, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
