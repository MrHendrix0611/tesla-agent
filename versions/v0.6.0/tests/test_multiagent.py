"""V0.6.0 multiagent role gates, persistence, actual tool chain; offline only."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from core.planner import Planner
from core.plan_store import PlanStore
from core.executor import PlanExecutor
from core.multiagent import (
    TeamOrchestrator, organize_team_tasks, role_allowed_tools,
    handoff_context, role_instructions
)


class FakeModel:
    def generate(self, messages, **kwargs):
        return {'content': json.dumps({'steps': [
            {'description': 'Inspecionar projeto', 'dependencies': []},
            {'description': 'Implementar calculadora.py', 'dependencies': [1]},
            {'description': 'Executar testes existentes', 'dependencies': [2]},
        ]})}


class RoleAgent:
    def __init__(self, root):
        from tools.registry import ToolRegistry
        self.tools = ToolRegistry()
        self.tools.set_workspace(root)
        self.llm = FakeModel()
        self.plan_allowed_tools = None
        self.plan_role = None
        self.calls = []
        self.last_run_evidence = {}
        self.qa_failed = False
        self.review_result = 'VEREDITO: APROVADO'

    def run(self, text, plan_step=False):
        role = self.plan_role
        self.calls.append((role, text, set(self.plan_allowed_tools or [])))
        if role == 'architect':
            calls = ['repository_map']
            result = 'Projeto inspecionado.'
        elif role == 'developer':
            calls = ['write_file']
            result = 'Arquivo criado no workspace.'
            # Simulate real artifact actually saved inside selected project root.
            (Path(self.tools.get_workspace())/'calculadora.py').write_text('def soma(a,b): return a+b\n', encoding='utf-8')
        elif role == 'qa':
            calls = [] if self.qa_failed else ['run_tests']
            result = 'Testes reais executados' if not self.qa_failed else 'Falha na execução'
        elif role == 'reviewer':
            calls = ['read_file']
            result = self.review_result
        else:
            raise AssertionError('Role not set')
        self.last_run_evidence = {'finished': True, 'tools': calls, 'denied': [],
            'attempted_tools': len(calls), 'tool_errors': [],
            'tool_records': [{'name': c, 'ok': True, 'exit_code': 0} for c in calls]}
        return result


class TeamUnitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.agent = RoleAgent(self.root)
        self.executor = PlanExecutor(self.agent, PlanStore(self.root/'.tesla'/'plan.json'))
        self.team = TeamOrchestrator(self.executor)

    def test_roles_permissions_minimum_privilege(self):
        for role in ('architect', 'qa', 'reviewer'):
            self.assertNotIn('write_file', role_allowed_tools(role))
            self.assertNotIn('apply_patch', role_allowed_tools(role))
            self.assertNotIn('run_command', role_allowed_tools(role))
            self.assertFalse(any(x.startswith('mcp__') for x in role_allowed_tools(role)))
        self.assertIn('write_file', role_allowed_tools('developer'))
        self.assertIn('run_tests', role_allowed_tools('qa'))
        self.assertNotIn('run_tests', role_allowed_tools('reviewer'))

    def test_organize_role_chain_when_model_omits_qa_review(self):
        tasks = organize_team_tasks('Criar calculadora', [{'description': 'Criar calculadora.py'}],
                                    self.executor._kind)
        self.assertEqual(tasks[0]['role'], 'architect')
        self.assertIn('developer', [t['role'] for t in tasks])
        self.assertEqual([t['role'] for t in tasks][-2:], ['qa', 'reviewer'])
        self.assertTrue(all(i == 0 or t['dependencies'] == [i]
                            for i, t in enumerate(tasks)))

    def test_cannot_create_team_without_selected_project(self):
        self.agent.tools.workspace_selected = False
        with self.assertRaises(ValueError):
            self.team.create('Criar módulo Python')

    def test_create_persists_role_metadata(self):
        plan = self.team.create('Criar módulo Python')
        self.assertTrue(plan.team_mode)
        copy = PlanStore(self.root/'.tesla'/'plan.json').load()
        self.assertTrue(copy.team_mode)
        self.assertEqual([s.role for s in copy.steps], [s.role for s in plan.steps])
        self.assertEqual(Path(copy.workspace).resolve(), self.root.resolve())

    def test_team_workflow_reaches_completed_with_qa_and_reviewer(self):
        self.team.create('Criar calculadora.py')
        report = self.team.run(lambda step: True)
        self.assertIn('Estado: completed', report)
        self.assertEqual(self.executor.planner.current_plan.status, 'completed')
        self.assertEqual(self.agent.calls[0][0], 'architect')
        self.assertEqual(self.agent.calls[-2][0], 'qa')
        self.assertEqual(self.agent.calls[-1][0], 'reviewer')
        self.assertNotIn('write_file', self.agent.calls[-1][2])
        self.assertIn('HANDOFF', self.agent.calls[-1][1])
        self.assertTrue(self.team.status()['qa_verified'])
        self.assertTrue(self.team.status()['review_approved'])

    def test_qa_evidence_missing_pauses_plan(self):
        self.agent.qa_failed = True
        self.team.create('Criar calculadora.py')
        text = self.team.run(lambda _: True)
        self.assertIn('Estado: paused', text)
        qa = next(s for s in self.executor.planner.current_plan.steps if s.role == 'qa')
        self.assertEqual(qa.status, 'paused')
        self.assertFalse(self.team.status()['qa_verified'])
        self.assertFalse(any(role == 'reviewer' for role, _, _ in self.agent.calls))

    def test_reviewer_must_explicitly_approve(self):
        self.agent.review_result = 'VEREDITO: AJUSTES'
        self.team.create('Criar calculadora.py')
        report = self.team.run(lambda _: True)
        self.assertIn('Estado: paused', report)
        review = next(s for s in self.executor.planner.current_plan.steps if s.role == 'reviewer')
        self.assertEqual(review.status, 'paused')
        self.assertIn('não aprovou', review.result)

    def test_rework_reopens_developer_qa_review_but_not_architect(self):
        self.agent.review_result = 'VEREDITO: AJUSTES'
        self.team.create('Criar calculadora.py')
        self.team.run(lambda _: True)
        self.assertIn('reabertos', self.team.rework())
        self.assertEqual(self.executor.planner.current_plan.status, 'pending')
        self.assertEqual(self.executor.planner.current_plan.steps[0].status, 'completed')
        self.assertTrue(all(s.status == 'pending' for s in self.executor.planner.current_plan.steps[1:]))
        self.agent.review_result = 'VEREDITO: APROVADO'
        self.assertIn('completed', self.team.run(lambda _: True))

    def test_qa_failure_can_rework_and_feed_developer(self):
        self.agent.qa_failed = True
        self.team.create('Criar calculadora.py')
        self.team.run(lambda _: True)
        qa = next(s for s in self.executor.planner.current_plan.steps if s.role == 'qa')
        self.assertEqual(qa.status, 'paused')
        self.assertIn('reabertos', self.team.rework())
        self.assertIn('Nenhuma ferramenta', self.executor.planner.current_plan.team_feedback)
        self.agent.qa_failed = False
        self.assertIn('completed', self.team.run(lambda _: True))
        self.assertTrue(self.team.status()['qa_verified'])

    def test_rework_rejects_workspace_switch(self):
        self.agent.review_result = 'VEREDITO: AJUSTES'
        self.team.create('Criar calculadora.py')
        self.team.run(lambda _: True)
        with tempfile.TemporaryDirectory() as other:
            self.agent.tools.set_workspace(other)
            with self.assertRaises(ValueError):
                self.team.rework()

    def test_plan_cannot_cross_project(self):
        self.team.create('Criar calculadora.py')
        with tempfile.TemporaryDirectory() as other:
            self.agent.tools.set_workspace(other)
            self.assertIn('pertence', self.team.run(lambda _: True))
        self.assertEqual(self.executor.planner.current_plan.steps[0].status, 'pending')

    def test_legacy_plan_loads_without_team_roles(self):
        old = {'id': '1', 'objective':'X', 'steps': [{'id': 1,'description': 'A'}],
               'created_at': '2026-01-01', 'workspace': str(self.root)}
        from core.planner import ExecutionPlan
        plan = ExecutionPlan.from_dict(old)
        self.assertFalse(plan.team_mode)
        self.assertEqual(plan.steps[0].role, 'general')

    def test_secrets_masked_in_handoffs(self):
        planner = Planner()
        plan = planner.create_plan('Teste', [{'description':'Etapa 1'}, {'description':'Etapa 2', 'dependencies':[1]}])
        planner.start_step(1)
        planner.complete_step(1, 'API_KEY=abc123-super-secret-token')
        handoff = handoff_context(plan, 2)
        self.assertNotIn('abc123-super-secret-token', handoff)

    def test_no_team_status_until_team_created(self):
        self.assertIn('Nenhum plano', self.team.status()['message'])
        with self.assertRaises(ValueError):
            self.team.run()


class RealAgentTeamTests(unittest.TestCase):
    def test_roles_restrict_llm_advertised_tools(self):
        """Real Agent.run + scripted responses without connecting remote LLM."""
        from core.agent import Agent
        from tools.registry import ToolRegistry
        from core.permission_manager import PermissionManager
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            class MockLLM:
                def __init__(self): self.tool_names = []
                def generate(self, messages, tools=None, **kwargs):
                    self.tool_names.append({t['function']['name'] for t in (tools or [])})
                    return {'content':'VEREDITO: APROVADO'}
            agent = Agent.__new__(Agent)
            agent.llm = MockLLM()
            agent.context = MagicMock()
            agent.context.get_messages.return_value = []
            agent.active_skill = None
            agent.tools = ToolRegistry()
            agent.tools.set_workspace(root)
            agent.permissions = PermissionManager()
            agent.system_prompt = 'sistema de teste'
            agent.max_plan_tool_calls = 10
            agent.max_plan_iterations = 10
            agent.plan_role = 'reviewer'
            agent.plan_allowed_tools = role_allowed_tools('reviewer')
            agent.run('Revisar projeto', plan_step=True)
            provided = agent.llm.tool_names[-1]
            self.assertIn('read_file', provided)
            self.assertNotIn('write_file', provided)
            self.assertNotIn('run_command', provided)
            self.assertFalse(any(t.startswith('mcp__') for t in provided))


if __name__ == '__main__':
    unittest.main()
