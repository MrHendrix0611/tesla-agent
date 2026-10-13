"""V0.5.8: offline RAG, persistence, isolation, security and bounded context."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from core.context import ContextManager
from core.knowledge import ProjectKnowledgeIndex
from core.memory import ProjectMemory
from tools.registry import ToolRegistry


class ProjectKnowledgeTests(unittest.TestCase):
    def test_indexes_code_with_file_and_line_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'calc.py').write_text('def calcular_media(valores):\n    return sum(valores) / len(valores)\n')
            index = ProjectKnowledgeIndex(root)
            status = index.refresh()
            self.assertEqual(status['files'], 1)
            matches = index.search('calcular_media soma valores')
            self.assertTrue(matches)
            self.assertEqual(matches[0]['file'], 'calc.py')
            self.assertEqual(matches[0]['start_line'], 1)
            self.assertIn('calcular_media', matches[0]['snippet'])
            self.assertTrue((root / '.tesla' / 'knowledge_index.json').exists())

    def test_incremental_refresh_detects_changes_and_removal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            file = root / 'mod.py'
            file.write_text('def inicio(): return 1\n')
            index = ProjectKnowledgeIndex(root)
            self.assertTrue(index.refresh()['changed'])
            self.assertFalse(index.refresh()['changed'])
            file.write_text('def muito_diferente(): return 15\n')
            self.assertTrue(index.search('muito_diferente'))
            self.assertFalse(index.search('inicio'))
            file.unlink()
            self.assertEqual(index.refresh()['files'], 0)
            self.assertFalse(index.search('muito_diferente'))

    def test_respects_hidden_gitignored_secrets_and_symlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / '.env').write_text('OPENROUTER_API_KEY=sk-very-private-credential\n')
            (root / '.gitignore').write_text('hidden.py\n')
            (root / 'hidden.py').write_text('def do_not_index(): pass\n')
            (root / 'src.py').write_text('GROQ_API_KEY = "sk-SuperSecretExample123456"\ndef public_helper(): return True\n')
            (root / 'node_modules').mkdir()
            (root / 'node_modules' / 'bad.py').write_text('def private_name(): pass')
            try:
                (root / 'outside.py').symlink_to(root / '.env')
            except (OSError, NotImplementedError):
                pass
            index = ProjectKnowledgeIndex(root)
            self.assertEqual(index.refresh()['files'], 1)
            raw = (root / '.tesla' / 'knowledge_index.json').read_text()
            self.assertNotIn('SuperSecretExample', raw)
            self.assertNotIn('very-private', raw)
            self.assertNotIn('do_not_index', raw)
            self.assertNotIn('private_name', raw)
            self.assertIn('REDACTED', raw)

    def test_project_isolation(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            (Path(first) / 'one.py').write_text('def alpha_function(): pass')
            (Path(second) / 'two.py').write_text('def beta_function(): pass')
            idx_a = ProjectKnowledgeIndex(first)
            idx_b = ProjectKnowledgeIndex(second)
            self.assertTrue(idx_a.search('alpha_function'))
            self.assertFalse(idx_b.search('alpha_function'))
            self.assertTrue(idx_b.search('beta_function'))
            self.assertFalse(idx_a.search('beta_function'))

    def test_stored_source_cannot_redirect_index(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            path = Path(root) / '.tesla'
            path.symlink_to(Path(outside), target_is_directory=True)
            (Path(root) / 'safe.py').write_text('print(1)')
            with self.assertRaises(PermissionError):
                ProjectKnowledgeIndex(root).refresh()
            self.assertEqual(list(Path(outside).iterdir()), [])

    def test_index_reload(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / 'mod.py').write_text('def persistent_example(): pass\n')
            ProjectKnowledgeIndex(root).refresh()
            loaded = ProjectKnowledgeIndex(root)
            self.assertTrue(loaded.search('persistent_example', refresh=False))


class ProjectMemoryTests(unittest.TestCase):
    def test_add_recall_forget_and_restart(self):
        with tempfile.TemporaryDirectory() as root:
            memory = ProjectMemory(root)
            entry = memory.add('Escolhemos unittest para os testes Python.')
            restarted = ProjectMemory(root)
            self.assertEqual(restarted.list()[0]['id'], entry['id'])
            self.assertEqual(restarted.recall('unittest Python')[0]['id'], entry['id'])
            self.assertTrue(restarted.forget(entry['id']))
            self.assertFalse(restarted.forget(entry['id']))
            self.assertEqual(memory.list(), [])

    def test_does_not_save_secret_looking_notes(self):
        with tempfile.TemporaryDirectory() as root:
            memory = ProjectMemory(root)
            with self.assertRaises(ValueError):
                memory.add('Minha senha é ABCDE12345')
            with self.assertRaises(ValueError):
                memory.add('GROQ_API_KEY=sk-FakeCredentialxxxxxx')
            self.assertEqual(memory.list(), [])

    def test_requires_selected_project_for_tools(self):
        registry = ToolRegistry()
        with self.assertRaises(ValueError):
            registry.get_knowledge()
        with self.assertRaises(ValueError):
            registry.get_project_memory()
        with tempfile.TemporaryDirectory() as root:
            registry.set_workspace(root)
            names = {d['function']['name'] for d in registry.get_tool_definitions()}
            self.assertIn('knowledge_search', names)
            (Path(root) / 'example.py').write_text('def useful_function(): pass')
            found = registry.execute('knowledge_search', {'query': 'useful_function'})
            self.assertEqual(found[0]['file'], 'example.py')

    def test_notes_in_different_projects_do_not_mix(self):
        with tempfile.TemporaryDirectory() as root_a, tempfile.TemporaryDirectory() as root_b:
            ProjectMemory(root_a).add('Padrão arquitetura hexagonal.')
            self.assertEqual(ProjectMemory(root_b).recall('arquitetura hexagonal'), [])


class ChatContextTests(unittest.TestCase):
    def test_trims_old_turns_and_marks_summary_as_unverified(self):
        ctx = ContextManager(max_messages=4, max_chars=280, summary_chars=150)
        for index in range(9):
            ctx.add_user_message(f'Pedido de implementação número {index}')
            ctx.add_assistant_message(f'Resposta {index}')
        result = ctx.get_messages()
        self.assertTrue(len(result) <= 5)
        self.assertTrue(any('PEDIDOS ANTERIORES' in msg['content'] for msg in result))
        self.assertTrue(any('número 8' in msg['content'] for msg in result))
        ctx.clear()
        self.assertEqual(ctx.get_messages(), [])

    def test_large_message_cannot_evict_itself(self):
        ctx = ContextManager(max_chars=500)
        ctx.add_user_message('z' * 1200)
        self.assertEqual(len(ctx.get_messages()), 1)
        self.assertIn('truncada', ctx.get_messages()[0]['content'])


if __name__ == '__main__':
    unittest.main()
