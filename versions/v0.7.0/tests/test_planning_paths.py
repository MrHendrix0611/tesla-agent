import tempfile
import unittest
from pathlib import Path
from core.executor import PlanExecutor
from core.plan_store import PlanStore

class BadPathAgent:
    def __init__(self):
        self.last_run_evidence = {}
        self.prompts = []
    def run(self, prompt, plan_step=False):
        self.prompts.append(prompt)
        self.last_run_evidence = {
            "finished": True, "interrupted": False,
            "tools": [], "attempted_tools": 2, "denied": [],
            "tool_errors": ["Arquivo não encontrado: /retry/calculator.py"]
        }
        return "Não consegui inspecionar"

class PathResumeTests(unittest.TestCase):
    def test_invalid_path_pauses_instead_of_fail(self):
        with tempfile.TemporaryDirectory() as d:
            a = BadPathAgent()
            e = PlanExecutor(a, PlanStore(Path(d) / "plan.json"))
            e.create("Inspecionar projeto", [{"description": "Inspecionar arquivos", "dependencies": []}])
            result = e.run(lambda _: True)
            self.assertIn("pausada", result)
            self.assertEqual(e.planner.get_step(1).status, "paused")
            self.assertIn("NÃO diretórios", a.prompts[0])
            self.assertIn("/retry/calculator.py", a.prompts[0])
            e.retry(1)
            self.assertEqual(e.planner.get_step(1).status, "pending")

if __name__ == '__main__': unittest.main()
