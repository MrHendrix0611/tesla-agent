"""Full team workflow using the real Agent, scoped tools and real unittest.
The language model is scripted to keep the test offline and deterministic.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from core.agent import Agent
from core.executor import PlanExecutor
from core.multiagent import TeamOrchestrator
from core.plan_store import PlanStore
from core.permission_manager import PermissionManager
from tools.registry import ToolRegistry


def call(name, args, code):
    return {'id':code, 'name':name, 'arguments':json.dumps(args)}


class ScriptedModel:
    def __init__(self, scripted):
        self.scripted = list(scripted)
        self.seen_tools = []
        self.seen_system_prompts = []

    def generate(self, messages, tools=None, **kwargs):
        self.seen_tools.append({t['function']['name'] for t in tools or []})
        self.seen_system_prompts.append(messages[0]['content'])
        if not self.scripted:
            raise AssertionError('Model scripted responses exhausted')
        return self.scripted.pop(0)


class MultiAgentIntegration(unittest.TestCase):
    def test_architect_developer_qa_reviewer_real_unittest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            implementation = 'def soma(a, b):\n    return a + b\n'
            tests = ('import unittest\nfrom calc import soma\n'
                     'class CalcTests(unittest.TestCase):\n'
                     '    def test_soma(self):\n        self.assertEqual(soma(2, 3), 5)\n')
            llm = ScriptedModel([
                {'content':json.dumps({'steps': [
                    {'description':'Implementar calc.py', 'dependencies':[]},
                    {'description':'Criar testes test_calc.py com unittest', 'dependencies':[1]},
                ]})},
                {'tool_calls':[call('repository_map', {}, 'arch-tool')]},
                {'content':'Projeto vazio; implementar calc.py e test_calc.py'},
                {'tool_calls':[call('write_file', {'path':'calc.py','content':implementation}, 'dev-1')]},
                {'content':'calc.py criado'},
                {'tool_calls':[call('write_file', {'path':'test_calc.py','content':tests}, 'dev-2')]},
                {'content':'test_calc.py criado'},
                {'tool_calls':[call('run_tests', {'target':'all'}, 'qa-1')]},
                {'content':'run_tests retornou exit_code 0 com 1 teste'},
                {'tool_calls':[call('read_file', {'path':'calc.py'}, 'review-1')]},
                {'content':'Código lido; teste unitário aprovado.\nVEREDITO: APROVADO'},
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
            agent.max_plan_iterations = 14
            agent.plan_allowed_tools = None
            agent.plan_role = None
            agent.system_prompt = 'Tesla teste offline'
            accepted = []
            agent.confirm_tool = lambda name, args: (accepted.append(name) or True)
            executor = PlanExecutor(agent, PlanStore(root/'.tesla'/'plan.json'))
            team = TeamOrchestrator(executor)
            plan = team.create('Implementar calc.py e test_calc.py e rodar unittest')
            self.assertEqual([s.role for s in plan.steps],
                             ['architect','developer','developer','qa','reviewer'])
            result = team.run(lambda step: True)
            self.assertIn('Estado: completed', result)
            self.assertEqual((root/'calc.py').read_text(), implementation)
            self.assertEqual((root/'test_calc.py').read_text(), tests)
            self.assertEqual(accepted, ['write_file','write_file','run_tests'])
            self.assertTrue(team.status()['qa_verified'])
            self.assertTrue(team.status()['review_approved'])
            self.assertNotIn('write_file', llm.seen_tools[1])  # Architect
            self.assertIn('write_file', llm.seen_tools[3])     # Developer
            self.assertNotIn('write_file', llm.seen_tools[7]) # QA
            self.assertNotIn('write_file', llm.seen_tools[9]) # Reviewer
            self.assertEqual(PlanStore(root/'.tesla'/'plan.json').load().status, 'completed')


    def test_failed_unittest_pauses_qa_and_never_runs_reviewer(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            llm = ScriptedModel([
                {'content':json.dumps({'steps':[
                    {'description':'Implementar calc.py e testes test_calc.py', 'dependencies':[]}
                ]})},
                {'tool_calls':[call('repository_map', {}, 'a')]},
                {'content':'Projeto inspecionado'},
                {'tool_calls':[call('write_file', {'path':'calc.py',
                    'content':'def soma(a,b): return a-b\n'}, 'd1'),
                    call('write_file', {'path':'test_calc.py',
                    'content':('import unittest\nfrom calc import soma\n'
                        'class TestCalc(unittest.TestCase):\n'
                        '    def test_soma(self):\n        self.assertEqual(soma(2,3),5)\n')}, 'd2')]},
                {'content':'Arquivos criados'},
                {'tool_calls':[call('run_tests', {'target':'all'}, 'qa')]},
                {'content':'Testes falharam'},
            ])
            agent = Agent.__new__(Agent)
            agent.llm = llm
            agent.context = MagicMock()
            agent.context.get_messages.return_value = []
            agent.active_skill = None
            agent.tools = ToolRegistry()
            agent.tools.set_workspace(root)
            agent.permissions = PermissionManager()
            agent.system_prompt = 'offline test'
            agent.max_plan_tool_calls = 12
            agent.max_plan_iterations = 12
            agent.plan_role = None
            agent.plan_allowed_tools = None
            agent.confirm_tool = lambda name, args: True
            executor = PlanExecutor(agent, PlanStore(root/'plan.json'))
            team = TeamOrchestrator(executor)
            team.create('Implementar calc.py e testes test_calc.py')
            report = team.run(lambda _: True)
            self.assertIn('Estado: paused', report)
            self.assertEqual([step.status for step in executor.planner.current_plan.steps],
                             ['completed', 'completed', 'paused', 'pending'])
            self.assertFalse(team.status()['qa_verified'])
            self.assertFalse(team.status()['review_approved'])
            self.assertTrue((root/'calc.py').is_file())



if __name__ == '__main__':
    unittest.main()
