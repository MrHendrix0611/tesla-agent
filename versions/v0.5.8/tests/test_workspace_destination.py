"""Regression: a completed plan must deliver into the selected project."""
import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import MagicMock

from core.executor import PlanExecutor
from core.plan_store import PlanStore
from tools.registry import ToolRegistry
from tools.terminal import TerminalTool


class DummyAgent:
    def __init__(self, tools=None):
        self.tools = tools or ToolRegistry()
        self.last_run_evidence = {}
        self.plan_allowed_tools = None
        self.calls = []

    def run(self, message, plan_step=False):
        self.calls.append(message)
        self.last_run_evidence = {
            'finished': True, 'tool_records': [{'name': 'write_file', 'ok': True}],
            'tools': ['write_file'], 'attempted_tools': 1,
            'denied': [], 'tool_errors': [],
        }
        return 'Fiz tudo, confie em mim.'


class WorkspaceDestinationTests(unittest.TestCase):
    def test_agent_denies_write_before_project_selection(self):
        from core.agent import Agent
        from core.permission_manager import PermissionManager

        with tempfile.TemporaryDirectory() as directory:
            agent = Agent.__new__(Agent)
            agent.tools = ToolRegistry()
            agent.tools.set_workspace(directory, explicit=False)
            agent.llm = MagicMock()
            agent.llm.generate.side_effect = [
                {'tool_calls': [{'id': 'one', 'name': 'write_file',
                                 'arguments': json.dumps({'path': 'calculator.py', 'content': 'x=1'})}]},
                {'content': 'Pronto'},
            ]
            agent.context = MagicMock()
            agent.context.get_messages.return_value = []
            agent.active_skill = None
            agent.permissions = PermissionManager()
            agent.system_prompt = 'teste'
            agent.plan_allowed_tools = None
            agent.max_tool_calls = 4
            agent.max_plan_tool_calls = 4
            agent.max_plan_iterations = 5
            agent.confirm_tool = lambda *_: True
            agent.run('Crie um arquivo')
            self.assertFalse((Path(directory) / 'calculator.py').exists())
            self.assertIn('/project', str(agent.last_run_evidence['tool_errors']))

    def test_initial_cwd_not_an_explicit_project(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = ToolRegistry()
            registry.set_workspace(directory, explicit=False)
            self.assertFalse(registry.workspace_selected)
            executor = PlanExecutor(DummyAgent(registry), PlanStore(Path(directory) / 'checkpoint.json'))
            with self.assertRaisesRegex(ValueError, '/project'):
                executor.create('Criar arquivo', [{'description': 'Criar calculator.py'}])
            self.assertIsNone(executor.planner.current_plan)

    def test_explicit_selection_persists_in_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = ToolRegistry()
            registry.set_repository(str(root))
            executor = PlanExecutor(DummyAgent(registry), PlanStore(root / 'checkpoint.json'))
            plan = executor.create('Criar código', [{'description': 'Criar calculator.py'}])
            self.assertEqual(Path(plan.workspace), root.resolve())
            self.assertTrue(registry.workspace_selected)

    def test_cannot_resume_in_a_different_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            first, second = Path(temp) / 'first', Path(temp) / 'second'
            first.mkdir(); second.mkdir()
            registry = ToolRegistry(); registry.set_workspace(first)
            agent = DummyAgent(registry)
            executor = PlanExecutor(agent, PlanStore(Path(temp) / 'checkpoint.json'))
            executor.create('Criar projeto', [{'description': 'Criar calculator.py'}])
            registry.set_workspace(second)
            result = executor.run(lambda _: True)
            self.assertIn(str(first), result)
            self.assertIn(str(second), result)
            self.assertEqual(agent.calls, [])
            self.assertFalse((second / 'calculator.py').exists())

    def test_cannot_complete_plan_if_expected_file_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = ToolRegistry(); registry.set_workspace(root)
            agent = DummyAgent(registry)
            executor = PlanExecutor(agent, PlanStore(root / 'checkpoint.json'))
            executor.create('Criar calculadora', [
                {'description': 'Criar calculator.py e test_calculator.py'}])
            result = executor.run(lambda _: True)
            self.assertIn('pausada', result)
            self.assertIn('calculator.py', result)
            self.assertEqual(executor.planner.current_plan.status, 'paused')

    def test_shell_cd_is_rejected_even_if_user_approves_command(self):
        with tempfile.TemporaryDirectory() as directory:
            terminal = TerminalTool(directory)
            for command in ('cd C:\\somewhere && py -m unittest',
                            'echo ok && cd ..', 'pushd C:\\other'):
                with self.subTest(command=command):
                    with self.assertRaisesRegex(PermissionError, '/project'):
                        terminal.run_command(command)


if __name__ == '__main__':
    unittest.main()
