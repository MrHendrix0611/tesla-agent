"""Regression tests for the V0.7.0 stabilization. No external API calls."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from core.multiagent import parse_review_verdict
from core.plan_store import PlanStore
from core.planner import ExecutionPlan, Planner
from web.service import TeslaService


class RouterStub:
    def __init__(self):
        self.providers = [('groq', type('Provider', (), {'model': 'offline'})())]
        self.auto = True
        self.last_decision = None
        self.paid_approval_callback = None
        self.usage = type('Usage', (), {'summary': lambda s: {'today_calls': 0}})()

    def generate(self, messages, tools=None, task_hint=None):
        return {'content': 'offline', 'tool_calls': []}


class StabilizationTests(TestCase):
    def test_reviewer_markdown_and_contradictions(self):
        self.assertEqual(parse_review_verdict('Relatório aprovado\n**VEREDITO: APROVADO**'), 'APROVADO')
        self.assertEqual(parse_review_verdict('### VEREDITO: AJUSTES'), 'AJUSTES')
        self.assertEqual(parse_review_verdict('Tudo certo, aprovado!'), 'INCONCLUSIVO')
        self.assertEqual(parse_review_verdict('VEREDITO: APROVADO\nVEREDITO: AJUSTES'), 'INCONCLUSIVO')

    def test_plan_store_exclusive_prevents_competing_writer(self):
        with TemporaryDirectory() as temp:
            store = PlanStore(Path(temp) / '.tesla' / 'plan.json')
            other = PlanStore(store.path)
            with store.exclusive():
                with self.assertRaises(RuntimeError):
                    with other.exclusive():
                        pass
            with other.exclusive():
                pass

    def test_workspace_restored_and_shared_plan_readable(self):
        with TemporaryDirectory() as temp:
            from core.agent import Agent
            root = Path(temp) / 'project'
            root.mkdir()
            settings = Path(temp) / 'preferences.json'
            with patch('core.agent.LLMRouter', RouterStub):
                first = TeslaService(agent=Agent(), settings_path=settings)
                first.select_project(str(root))
                plan = first.executor.create('Testar estado compartilhado', [
                    {'description': 'Inspecionar código', 'dependencies': []}
                ])
                plan.team_mode = True
                first.executor.persist()
                second = TeslaService(agent=Agent(), settings_path=settings)
                self.assertEqual(second.project, str(root.resolve()))
                self.assertEqual(second.executor.planner.current_plan.objective,
                                 'Testar estado compartilhado')
                self.assertEqual(second.team.status()['status'], 'pending')

    def test_chat_interrupted_not_completed(self):
        from core.agent import Agent
        with TemporaryDirectory() as temp:
            with patch('core.agent.LLMRouter', RouterStub):
                service = TeslaService(agent=Agent())
                service.select_project(temp)
                def interrupted(_):
                    service.agent.last_run_evidence = {'interrupted': True}
                    return 'Execução incompleta'
                service.agent.run = interrupted
                job = service.chat('Faça algo')
                import time
                for _ in range(100):
                    if service.active_job is None:
                        break
                    time.sleep(.01)
                self.assertEqual(service.jobs[job['id']]['status'], 'incomplete')

    def test_logo_static_contains_no_wordmark(self):
        path = Path(__file__).resolve().parents[1] / 'web' / 'static' / 'tesla-mark.png'
        self.assertTrue(path.is_file())
        self.assertEqual(path.read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
