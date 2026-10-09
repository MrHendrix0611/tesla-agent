import tempfile
import unittest
from pathlib import Path
from core.planner import Planner
from core.plan_store import PlanStore
from core.executor import PlanExecutor


class FakeLLM:
    def generate(self, messages, **kwargs):
        return {'content': '{"steps":[{"description":"Analisar projeto","dependencies":[]},{"description":"Criar código","dependencies":[1]}]}'}


class FakeAgent:
    def __init__(self, fail=False, evidence=True):
        self.llm = FakeLLM()
        self.fail = fail
        self.evidence = evidence
        self.calls = []
        self.last_run_evidence = {}

    def run(self, prompt, plan_step=False):
        self.calls.append((prompt, plan_step))
        if self.fail:
            raise RuntimeError('Falha controlada')
        self.last_run_evidence = {'finished': True, 'tools': ['read_file', 'write_file', 'run_command'] if self.evidence else [], 'tool_errors': [], 'denied': []}
        return 'Operação realizada'


class PlanningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'plan.json'

    def make(self, agent=None):
        return PlanExecutor(agent or FakeAgent(), PlanStore(self.path))

    def test_generate_and_execute(self):
        e = self.make()
        e.generate('Criar aplicação')
        self.assertEqual(len(e.planner.current_plan.steps), 2)
        result = e.run(lambda step: True)
        self.assertIn('completed', result)
        self.assertEqual(len(e.agent.calls), 2)
        self.assertTrue(all(flag for _, flag in e.agent.calls))

    def test_permissions_pause(self):
        e = self.make()
        e.generate('Projeto')
        e.run(lambda s: False)
        self.assertEqual(e.planner.get_step(1).status, 'pending')
        self.assertEqual(len(e.agent.calls), 0)

    def test_dependencies(self):
        p = Planner()
        p.create_plan('Objetivo', [{'description': 'A', 'dependencies': []}, {'description': 'B', 'dependencies': [1]}])
        with self.assertRaises(ValueError):
            p.start_step(2)
        p.start_step(1)
        p.complete_step(1, 'OK')
        self.assertEqual(p.next_step().id, 2)

    def test_invalid_cycle(self):
        with self.assertRaises(ValueError):
            Planner().create_plan('X', [{'description': 'X', 'dependencies': [1]}])

    def test_failure_retry(self):
        agent = FakeAgent(fail=True)
        e = self.make(agent)
        e.generate('Projeto')
        e.run(lambda s: True)
        self.assertEqual(e.planner.current_plan.status, 'failed')
        agent.fail = False
        e.retry(1)
        self.assertEqual(e.planner.get_step(1).status, 'pending')
        e.run(lambda s: True)
        self.assertEqual(e.planner.current_plan.status, 'completed')

    def test_no_tool_evidence_for_action(self):
        e = self.make(FakeAgent(evidence=False))
        e.create('Código', [{'description': 'Criar arquivo', 'dependencies': []}])
        e.run(lambda s: True)
        self.assertEqual(e.planner.get_step(1).status, 'failed')

    def test_interrupted_step_recovers_failed(self):
        e = self.make()
        e.create('X', [{'description':'A'}])
        e.planner.start_step(1)
        e.persist()
        reloaded = self.make()
        self.assertEqual(reloaded.planner.get_step(1).status, 'paused')

    def test_cancel(self):
        e = self.make()
        e.create('X', [{'description': 'A'}])
        e.planner.cancel_plan()
        e.persist()
        self.assertIn('cancelled', self.make().run())

if __name__ == '__main__':
    unittest.main()
