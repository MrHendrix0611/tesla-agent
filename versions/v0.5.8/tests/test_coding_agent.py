import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from core.coding import CodingWorkspace
from core.agent import Agent
from core.executor import PlanExecutor
from core.plan_store import PlanStore
from tools.registry import ToolRegistry
from tools.terminal import TerminalTool
from core.permission_manager import PermissionManager


class CodingAgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.ws = CodingWorkspace(self.root)

    def test_new_file_patch_preview_apply_and_rollback(self):
        preview = self.ws.preview_patch('app.py', '', 'print(1)\n')
        self.assertIn('+print(1)', preview['diff'])
        self.assertFalse((self.root / 'app.py').exists())
        self.ws.apply_patch(preview['proposal_id'])
        self.assertEqual((self.root / 'app.py').read_text(), 'print(1)\n')
        self.ws.rollback_file('app.py')
        self.assertFalse((self.root / 'app.py').exists())

    def test_precise_patch_and_rollback_existing(self):
        original = 'def soma(a, b):\n    return a-b\n'
        self.ws.write('calc.py', original)
        preview = self.ws.preview_patch('calc.py', 'return a-b', 'return a+b')
        self.assertIn('-    return a-b', preview['diff'])
        self.ws.apply_patch(preview['proposal_id'])
        self.assertIn('return a+b', self.ws.read('calc.py'))
        self.assertIn('return a+b', self.ws.diff_file('calc.py')['diff'])
        self.ws.rollback_file('calc.py')
        self.assertEqual(self.ws.read('calc.py'), original)

    def test_stale_patch_refused(self):
        self.ws.write('calc.py', 'valor=1\n')
        proposal = self.ws.preview_patch('calc.py', 'valor=1', 'valor=2')
        (self.root / 'calc.py').write_text('valor=3\n')
        with self.assertRaisesRegex(RuntimeError, 'mudou'):
            self.ws.apply_patch(proposal['proposal_id'])
        self.assertEqual(self.ws.read('calc.py'), 'valor=3\n')

    def test_ambiguous_patch_refused(self):
        self.ws.write('calc.py', 'valor\nvalor\n')
        with self.assertRaises(ValueError):
            self.ws.preview_patch('calc.py', 'valor', 'novo')

    def test_block_secret_and_escape(self):
        for filename in ('.env', '.env.local', '.tesla/plan.json', '.git/config', '../outside.py',
                         '/retry/calculator.py', 'id_rsa', 'secrets.json'):
            with self.subTest(filename=filename):
                with self.assertRaises((PermissionError, ValueError)):
                    self.ws.write(filename, 'secret')
        self.assertFalse((self.root / '.env').exists())

    def test_symlink_cannot_escape_workspace(self):
        with tempfile.TemporaryDirectory() as other:
            linked = self.root / 'outside'
            try:
                linked.symlink_to(other, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest('Symlink indisponível neste sistema')
            with self.assertRaises(PermissionError):
                self.ws.write('outside/file.py', 'escape')

    def test_rollback_refuses_external_changes(self):
        self.ws.write('calc.py', 'before')
        self.ws.write('calc.py', 'after')
        (self.root / 'calc.py').write_text('someone else edited', encoding='utf-8')
        with self.assertRaises(RuntimeError):
            self.ws.rollback_file('calc.py')

    def test_registry_tools_and_permission(self):
        registry = ToolRegistry()
        registry.set_workspace(self.root)
        names = {t['function']['name'] for t in registry.get_tool_definitions()}
        for name in ('preview_patch', 'apply_patch', 'rollback_file', 'diff_file', 'run_tests'):
            self.assertIn(name, names)
        permissions = PermissionManager()
        self.assertEqual(permissions.get_status('preview_patch'), 'allowed')
        self.assertEqual(permissions.get_status('apply_patch'), 'confirmation_required')
        self.assertEqual(permissions.get_status('rollback_file'), 'confirmation_required')
        with self.assertRaises(PermissionError):
            registry.execute('read_file', {'path': '.env'})

    def test_tests_real_exit_code(self):
        (self.root / 'test_sample.py').write_text('import unittest\nclass T(unittest.TestCase):\n  def test_x(self): self.assertEqual(2+2,4)\n')
        terminal = TerminalTool(self.root)
        report = terminal.run_tests('test_sample')
        self.assertIn('exit_code: 0', report)
        self.assertIn('Ran 1 test', report)
        (self.root / 'test_sample.py').write_text('import unittest\nclass T(unittest.TestCase):\n  def test_x(self): self.assertEqual(2+2,50)\n# changed\n')
        with self.assertRaisesRegex(RuntimeError, 'exit_code: 1'):
            terminal.run_tests('test_sample')

    def test_shell_injection_in_test_target_denied(self):
        with self.assertRaises(ValueError):
            TerminalTool(self.root).run_tests('test_x && echo unsafe')

    def test_agent_tool_evidence_tracks_failure_and_success(self):
        # Avoid API calls by bypassing initialization and mocking the LLM responses.
        agent = Agent.__new__(Agent)
        agent.context = MagicMock()
        agent.context.get_messages.return_value = []
        agent.active_skill = None
        agent.tools = ToolRegistry()
        agent.tools.set_workspace(self.root)
        agent.permissions = PermissionManager()
        agent.plan_allowed_tools = {'read_file', 'list_files'}
        agent.max_plan_tool_calls = 5
        agent.max_plan_iterations = 5
        agent.max_tool_calls = 5
        agent.system_prompt = 'test'
        agent.llm = MagicMock()
        agent.llm.generate.side_effect = [
            {'tool_calls': [
                {'id': '1', 'name': 'read_file', 'arguments': json.dumps({'path': 'missing.py'})},
                {'id': '2', 'name': 'list_files', 'arguments': json.dumps({'path': '.'})},
            ]},
            {'content': 'Arquivo não encontrado'}
        ]
        answer = agent.run('Liste', plan_step=True)
        self.assertIn('Arquivo', answer)
        self.assertEqual(agent.last_run_evidence['attempted_tools'], 2)
        self.assertEqual(agent.last_run_evidence['tools'], ['list_files'])
        self.assertEqual(len(agent.last_run_evidence['tool_errors']), 1)
        self.assertTrue(agent.last_run_evidence['finished'])

    def test_plan_uses_workspace_and_pauses_unproved_steps(self):
        class A:
            def __init__(self, root):
                self.tools = ToolRegistry()
                self.tools.set_workspace(root)
                self.plan_allowed_tools = None
                self.prompts = []
                self.last_run_evidence = {}
            def run(self, prompt, plan_step=False):
                self.prompts.append((prompt, self.plan_allowed_tools))
                self.last_run_evidence = {'finished': True, 'tools': ['list_files'],
                                          'tool_records': [{'name':'list_files','ok':True}],
                                          'attempted_tools':1, 'denied':[], 'tool_errors':[]}
                return 'Feito'
        a = A(self.root)
        executor = PlanExecutor(a, PlanStore(self.root / 'checkpoint.json'))
        executor.create('Criar app', [{'description': 'Criar app.py', 'dependencies': []}])
        result = executor.run(lambda x: True)
        self.assertIn('pausada', result)
        self.assertEqual(executor.planner.get_step(1).status, 'paused')
        self.assertIn('write_file', a.prompts[0][1])
        self.assertNotIn('run_command', a.prompts[0][1])
        self.assertEqual(executor.planner.current_plan.workspace, str(self.root))


class UpdatedFileSnapshotTests(unittest.TestCase):
    def test_explicit_analysis_pulls_fresh_file_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / 'teste.py'
            target.write_text('def antigo():\n    return 1\n', encoding='utf-8')
            agent = Agent.__new__(Agent)
            agent.context = MagicMock()
            agent.context.get_messages.return_value = []
            agent.active_skill = None
            agent.tools = ToolRegistry()
            agent.tools.set_workspace(root)
            agent.permissions = PermissionManager()
            agent.plan_allowed_tools = None
            agent.max_plan_tool_calls = 5
            agent.max_plan_iterations = 5
            agent.max_tool_calls = 5
            agent.system_prompt = 'test'
            agent.llm = MagicMock()
            agent.llm.generate.return_value = {'content': 'OK'}
            agent.run('Analise o arquivo teste.py')
            sent = agent.llm.generate.call_args.args[0]
            self.assertIn('def antigo()', sent[-1]['content'])
            target.write_text('def novo():\n    return 2\n', encoding='utf-8')
            agent.run('Analise o arquivo teste.py')
            sent = agent.llm.generate.call_args.args[0]
            self.assertIn('def novo()', sent[-1]['content'])
            self.assertNotIn('def antigo()', sent[-1]['content'])
            self.assertEqual(agent.last_run_evidence['tools'], ['read_file'])

    def test_explicit_analysis_of_missing_file_reports_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            agent = Agent.__new__(Agent)
            agent.context = MagicMock()
            agent.context.get_messages.return_value = []
            agent.active_skill = None
            agent.tools = ToolRegistry()
            agent.tools.set_workspace(temporary)
            agent.permissions = PermissionManager()
            agent.plan_allowed_tools = None
            agent.max_plan_iterations = 5
            agent.max_tool_calls = 5
            agent.system_prompt = 'test'
            agent.llm = MagicMock()
            agent.llm.generate.return_value = {'content': 'Falha de leitura'}
            agent.run('Leia arquivo inexistente.py')
            sent = agent.llm.generate.call_args.args[0]
            self.assertIn('NÃO afirme ter lido', sent[-1]['content'])
            self.assertEqual(agent.last_run_evidence['tools'], [])


if __name__ == "__main__":
    unittest.main()
