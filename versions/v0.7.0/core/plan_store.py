"""Checkpoint JSON atômico; não persiste prompts brutos ou segredos."""
import json
import os
from contextlib import contextmanager
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

    @contextmanager
    def exclusive(self):
        """Cross-process nonblocking lock for plan writes and execution.

        Atomic lock acquisition works across terminal/web Python processes on
        Windows and POSIX. Stale locks require explicit operator recovery; no
        unsafe age-based lock stealing while an LLM may still be working.
        """
        lock_path = self.path.parent / 'execution.lock'
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        fp = open(lock_path, 'a+b')
        try:
            fp.seek(0)
            if fp.read(1) == b'':
                fp.write(b'0')
                fp.flush()
            fp.seek(0)
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(fp.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (OSError, BlockingIOError) as exc:
                raise RuntimeError('Plano em execução em outra interface. Aguarde ou cancele na origem.') from exc
            try:
                yield
            finally:
                fp.seek(0)
                if os.name == 'nt':
                    msvcrt.locking(fp.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(fp.fileno(), fcntl.LOCK_UN)
        finally:
            fp.close()
