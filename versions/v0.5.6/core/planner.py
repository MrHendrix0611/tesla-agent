"""Planos validados, dependências e estados de execução."""
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from uuid import uuid4

FINAL = {"completed", "failed", "cancelled"}

@dataclass
class PlanStep:
    id: int
    description: str
    dependencies: list[int] = field(default_factory=list)
    status: str = "pending"
    result: str = ""
    attempts: int = 0
    tool_calls: int = 0
    attempted_tool_calls: int = 0

@dataclass
class ExecutionPlan:
    id: str
    objective: str
    steps: list[PlanStep]
    created_at: str
    status: str = "pending"
    revisions: int = 0

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(id=data["id"], objective=data["objective"],
                   steps=[PlanStep(**s) for s in data["steps"]],
                   created_at=data["created_at"], status=data.get("status", "pending"),
                   revisions=data.get("revisions", 0))

class Planner:
    def __init__(self, plan=None):
        self.current_plan = plan

    def create_plan(self, objective, tasks):
        if not isinstance(objective, str) or not objective.strip():
            raise ValueError("Objetivo inválido")
        if not isinstance(tasks, list) or not 1 <= len(tasks) <= 12:
            raise ValueError("Plano deve conter de 1 a 12 etapas")
        steps = []
        for index, task in enumerate(tasks, 1):
            if not isinstance(task, dict):
                raise ValueError("Etapa inválida")
            desc = task.get("description")
            deps = task.get("dependencies", [])
            if not isinstance(desc, str) or not desc.strip() or len(desc) > 600:
                raise ValueError("Descrição inválida")
            if not isinstance(deps, list) or len(set(map(str, deps))) != len(deps):
                raise ValueError("Dependências duplicadas/inválidas")
            if any(type(d) is not int or d < 1 or d >= index for d in deps):
                raise ValueError("Dependências só podem referenciar etapas anteriores")
            steps.append(PlanStep(index, desc.strip(), deps))
        self.current_plan = ExecutionPlan(str(uuid4()), objective.strip(), steps,
                                          datetime.now(timezone.utc).isoformat())
        return self.current_plan

    def get_step(self, step_id):
        if not self.current_plan:
            raise ValueError("Nenhum plano ativo")
        for step in self.current_plan.steps:
            if step.id == step_id:
                return step
        raise ValueError("Etapa não encontrada")

    def next_step(self):
        plan = self.current_plan
        if not plan or plan.status in FINAL or any(s.status == "running" for s in plan.steps):
            return None
        for step in plan.steps:
            if step.status != "pending":
                continue
            deps = [self.get_step(d).status for d in step.dependencies]
            if any(s in ("failed", "blocked", "cancelled") for s in deps):
                step.status = "blocked"
            elif all(s == "completed" for s in deps):
                return step
        self.refresh_status()
        return None

    def start_step(self, step_id):
        step = self.get_step(step_id)
        if self.next_step() is not step or step.status != "pending":
            raise ValueError("Etapa indisponível ou dependências não concluídas")
        step.status = "running"
        step.attempts += 1
        self.current_plan.status = "running"

    def complete_step(self, step_id, result, tool_calls=0):
        step = self.get_step(step_id)
        if step.status != "running":
            raise ValueError("Etapa não está em execução")
        step.status = "completed"
        step.result = str(result)[:6000]
        step.tool_calls += tool_calls
        self.refresh_status()

    def fail_step(self, step_id, error, tool_calls=0):
        step = self.get_step(step_id)
        if step.status != "running":
            raise ValueError("Etapa não está em execução")
        step.status = "failed"
        step.result = str(error)[:6000]
        step.tool_calls += tool_calls
        self.refresh_status()

    def pause_step(self, step_id, reason, tool_calls=0, attempted=0):
        step = self.get_step(step_id)
        if step.status != "running":
            raise ValueError("Etapa não está em execução")
        step.status = "paused"
        step.result = str(reason)[:6000]
        step.tool_calls += tool_calls
        step.attempted_tool_calls += attempted
        self.current_plan.status = "paused"

    def retry_step(self, step_id):
        plan = self.current_plan
        if not plan or plan.status == "cancelled":
            raise ValueError("Plano cancelado ou ausente")
        step = self.get_step(step_id)
        if step.status not in ("failed", "paused"):
            raise ValueError("Apenas etapas com falha ou pausadas podem ser repetidas")
        step.status = "pending"
        step.result = ""
        for child in plan.steps:
            if child.status == "blocked" and step_id in child.dependencies:
                child.status = "pending"
        plan.revisions += 1
        self.refresh_status()

    def refresh_status(self):
        plan = self.current_plan
        if not plan or plan.status == "cancelled":
            return
        states = [s.status for s in plan.steps]
        if all(s == "completed" for s in states):
            plan.status = "completed"
        elif any(s == "running" for s in states):
            plan.status = "running"
        elif any(s == "failed" for s in states):
            plan.status = "failed"
        elif any(s == "paused" for s in states):
            plan.status = "paused"
        elif any(s == "pending" for s in states):
            plan.status = "pending"
        else:
            plan.status = "failed"

    def cancel_plan(self):
        if not self.current_plan:
            raise ValueError("Nenhum plano")
        if self.current_plan.status == "completed":
            raise ValueError("Plano já concluído")
        self.current_plan.status = "cancelled"

    def summary(self):
        return self.current_plan.to_dict() if self.current_plan else {"message": "Nenhum plano"}
