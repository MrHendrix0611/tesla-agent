"""Checkpoint JSON atômico; não persiste prompts brutos ou segredos."""
import json
import os
from pathlib import Path
from core.planner import ExecutionPlan

class PlanStore:
    def __init__(self, path=None):
        self.path = Path(path or os.getenv("TESLA_PLAN_FILE", ".tesla/plan.json"))

    def save(self, plan):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def load(self):
        if not self.path.exists():
            return None
        plan = ExecutionPlan.from_dict(json.loads(self.path.read_text(encoding="utf-8")))
        # Recuperação conservadora: interrompido nunca é considerado concluído.
        for step in plan.steps:
            if step.status == "running":
                step.status = "paused"
                step.result = "Execução interrompida; confirme efeitos antes de continuar"
        if plan.status == "running":
            plan.status = "paused"
        return plan
