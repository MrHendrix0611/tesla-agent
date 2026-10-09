import tempfile
import unittest
from pathlib import Path
from core.executor import PlanExecutor
from core.plan_store import PlanStore

class InterruptedAgent:
    def __init__(self):
        self.last_run_evidence = {}
    def run(self, prompt, plan_step=False):
        self.last_run_evidence = {'finished': False, 'interrupted': True, 'tools': ['write_file'], 'attempted_tools': 2, 'denied': [], 'tool_errors': []}
        return 'Limite atingido'

class PausedPlanTests(unittest.TestCase):
    def test_interrupted_step_is_paused_and_retryable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'plan.json'
            e = PlanExecutor(InterruptedAgent(), PlanStore(path))
            e.create('Criar app', [{'description':'Criar arquivos', 'dependencies':[]}])
            e.run(lambda step: True)
            step=e.planner.get_step(1)
            self.assertEqual(step.status, 'paused')
            self.assertEqual(step.tool_calls,1)
            self.assertEqual(step.attempted_tool_calls,2)
            reloaded=PlanExecutor(InterruptedAgent(),PlanStore(path))
            self.assertEqual(reloaded.planner.get_step(1).status,'paused')
            reloaded.retry(1)
            self.assertEqual(reloaded.planner.get_step(1).status,'pending')
