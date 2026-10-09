"""Regression for review steps repeatedly pausing on generated file paths."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from core.agent import Agent
from core.executor import PlanExecutor
from core.permission_manager import PermissionManager
from core.plan_store import PlanStore
from tools.registry import ToolRegistry


class ReviewRecoveryTests(unittest.TestCase):
    def test_wrong_cli_path_recovers_for_read_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'src').mkdir()
            (root / 'src' / 'calculator.py').write_text('def soma(a, b): return a + b\n', encoding='utf-8')
            registry = ToolRegistry()
            registry.set_workspace(root)
            text = registry.execute('read_file', {'path': '/retry/calculator.py'})
            self.assertIn('src/calculator.py', text)
            self.assertIn('def soma(', text)
            self.assertFalse((root / 'retry').exists())

    def test_ambiguous_basename_is_not_guessed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for dirname in ('a', 'b'):
                (root / dirname).mkdir()
                (root / dirname / 'calculator.py').write_text('x=1', encoding='utf-8')
            registry = ToolRegistry()
            registry.set_workspace(root)
            with self.assertRaisesRegex(FileNotFoundError, 'ambíguo'):
                registry.execute('read_file', {'path': 'invalid/calculator.py'})

    def test_outside_read_is_never_redirected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'calculator.py').write_text('safe=1', encoding='utf-8')
            registry = ToolRegistry()
            registry.set_workspace(root)
            with self.assertRaises(PermissionError):
                registry.execute('read_file', {'path': '/etc/calculator.py'})
            with self.assertRaises(PermissionError):
                registry.execute('read_file', {'path': '../calculator.py'})

    def test_preflight_reads_named_review_files_before_llm_response(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'calculator.py').write_text('def soma(a,b): return a+b\n', encoding='utf-8')
            (root / 'test_calculator.py').write_text('import unittest\n', encoding='utf-8')
            agent = Agent.__new__(Agent)
            agent.tools = ToolRegistry()
            agent.tools.set_workspace(root)
            agent.llm = MagicMock()
            agent.llm.generate.return_value = {'content': 'Revisei as duas funções.'}
            agent.context = MagicMock()
            agent.active_skill = None
            agent.permissions = PermissionManager()
            agent.system_prompt = 'teste'
            agent.plan_allowed_tools = None
            agent.max_plan_tool_calls = 16
            agent.max_plan_iterations = 6
            agent.max_tool_calls = 5
            executor = PlanExecutor(agent, PlanStore(root / '.tesla' / 'test_plan.json'))
            executor.create('Revisar arquivos', [
                {'description': 'Revisar calculator.py e test_calculator.py quanto a estilo e docstrings', 'dependencies': []}
            ])
            result = executor.run(lambda step: True)
            self.assertIn('concluída', result)
            self.assertEqual(executor.planner.current_plan.status, 'completed')
            self.assertEqual(agent.last_run_evidence['tools'], ['read_file', 'read_file'])
            passed_messages = agent.llm.generate.call_args.args[0]
            self.assertIn('def soma', str(passed_messages))
            self.assertIn('import unittest', str(passed_messages))

    def test_paused_review_includes_real_tool_error(self):
        class BadAgent:
            plan_allowed_tools = None
            def __init__(self, tools):
                self.tools = tools
                self.last_run_evidence = {}
            def run(self, prompt, plan_step=False):
                self.last_run_evidence = {
                    'finished': True, 'tool_records': [
                        {'name':'read_file','ok':True},
                        {'name':'read_file','ok':False,'error':'Arquivo não encontrado: lib/missing.py'}
                    ], 'tools':['read_file'], 'attempted_tools':2,
                    'denied':[], 'tool_errors':['Arquivo não encontrado: lib/missing.py']
                }
                return 'revisão'
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            registry=ToolRegistry(); registry.set_workspace(root)
            executor=PlanExecutor(BadAgent(registry),PlanStore(root / '.tesla' / 'plan.json'))
            executor.create('Inspeção', [{'description':'Inspecionar projeto','dependencies':[]}])
            output=executor.run(lambda step: True)
            self.assertIn('read_file', output)
            self.assertIn('lib/missing.py', output)
            self.assertEqual(executor.planner.current_plan.status,'paused')


if __name__=='__main__':
    unittest.main()
