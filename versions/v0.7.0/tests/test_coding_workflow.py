"""Integration test: scripted LLM decisions, real tools, no remote requests."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from core.agent import Agent
from core.executor import PlanExecutor
from core.plan_store import PlanStore
from core.permission_manager import PermissionManager
from tools.registry import ToolRegistry


def call(name, arguments, id):
    return {'id': id, 'name': name, 'arguments': json.dumps(arguments)}


class ScriptedLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.sent_tools = []

    def generate(self, messages, tools=None, **kwargs):
        self.sent_tools.append({t['function']['name'] for t in (tools or [])})
        return self.responses.pop(0)


class CodingWorkflowTest(unittest.TestCase):
    def test_complete_plan_with_real_file_write_and_unittest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            implementation = 'def soma(a, b):\n    return a + b\n'
            tests = ('import unittest\nfrom calculator import soma\n'
                     'class TestCalc(unittest.TestCase):\n'
                     '    def test_soma(self):\n        self.assertEqual(soma(2, 3), 5)\n')
            llm = ScriptedLLM([
                {'tool_calls': [call('list_files', {'path': '.'}, '1')]},
                {'content': 'Projeto está vazio.'},
                {'tool_calls': [call('write_file', {'path': 'calculator.py', 'content': implementation}, '2'),
                                call('write_file', {'path': 'test_calculator.py', 'content': tests}, '3')]},
                {'content': 'Arquivos criados.'},
                {'tool_calls': [call('run_tests', {'target': 'test_calculator'}, '4')]},
                {'content': 'Os testes passaram.'},
            ])
            agent = Agent.__new__(Agent)
            agent.llm = llm
            agent.context = MagicMock()
            agent.context.get_messages.return_value = []
            agent.active_skill = None
            agent.tools = ToolRegistry()
            agent.tools.set_workspace(root)
            agent.permissions = PermissionManager()
            agent.max_tool_calls = 8
            agent.max_plan_tool_calls = 12
            agent.max_plan_iterations = 15
            agent.plan_allowed_tools = None
            agent.system_prompt = 'test'
            agent.confirm_tool = lambda name, arguments: True  # sandbox only
            executor = PlanExecutor(agent, PlanStore(root / '.tesla' / 'plan.json'))
            executor.create('Criar calculadora', [
                {'description': 'Inspecionar diretório', 'dependencies': []},
                {'description': 'Criar calculator.py e test_calculator.py', 'dependencies': [1]},
                {'description': 'Executar testes com unittest', 'dependencies': [2]},
            ])
            report = executor.run(lambda step: True)
            self.assertIn('Estado: completed', report)
            self.assertEqual((root / 'calculator.py').read_text(), implementation)
            self.assertEqual(executor.planner.get_step(2).tool_calls, 2)
            self.assertEqual(executor.planner.get_step(2).attempted_tool_calls, 2)
            self.assertIn('read_file', llm.sent_tools[0])
            self.assertNotIn('run_command', llm.sent_tools[2])
            self.assertIn('run_tests', llm.sent_tools[4])
            reloaded = PlanExecutor(agent, PlanStore(root / '.tesla' / 'plan.json'))
            self.assertEqual(reloaded.planner.current_plan.status, 'completed')


if __name__ == '__main__':
    unittest.main()

class ImplementationProofTests(unittest.TestCase):
    def test_existing_file_alone_does_not_prove_bug_fixed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'calculator.py').write_text('def div(a,b): return a / b\n')
            class ReadOnlyAgent:
                def __init__(self):
                    self.tools = ToolRegistry()
                    self.tools.set_workspace(root)
                    self.plan_allowed_tools = None
                    self.last_run_evidence = {}
                def run(self, instruction, plan_step=False):
                    self.last_run_evidence = {'finished':True,'attempted_tools':1,
                        'tools':['read_file'], 'tool_records':[{'name':'read_file','ok':True}],
                        'denied':[], 'tool_errors':[]}
                    return 'Eu consertei o bug'
            agent = ReadOnlyAgent()
            plan = PlanExecutor(agent, PlanStore(root / 'plan.json'))
            plan.create('Corrigir código', [{'description':'Corrigir divisão por zero em calculator.py'}])
            result = plan.run(lambda _: True)
            self.assertIn('paused', result)
            self.assertEqual(plan.planner.get_step(1).status, 'paused')
