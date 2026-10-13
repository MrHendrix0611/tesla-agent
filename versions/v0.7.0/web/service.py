"""Local workbench façade over the existing Tesla engine.

All model/tool execution stays inside Agent/PlanExecutor; this module does not
bypass their workspace, paid-model or tool-permission rules.
"""
from __future__ import annotations

from collections import deque
from pathlib import Path
from threading import Event, RLock, Thread
from time import monotonic, time
from uuid import uuid4
import os
import json

from core.knowledge import redact

EXCLUDE = {'.env', '.git', '.tesla', '.venv', 'venv', '__pycache__', 'node_modules',
           'dist', 'build', 'logs', 'data', '.pytest_cache', '.next'}
EXCLUDE_SUFFIXES = {'.key', '.pem', '.p12', '.pfx', '.crt', '.pyc'}


def _private_path(path: Path) -> bool:
    return any(p in EXCLUDE or p.startswith('.env.') or p.startswith('secrets.')
               for p in path.parts) or path.suffix.lower() in EXCLUDE_SUFFIXES


class ApprovalBroker:
    """A single-use, bounded approval queue with deny-by-default timeouts."""

    def __init__(self, publish, *, timeout=300):
        self.publish = publish
        self.timeout = timeout
        self._lock = RLock()
        self.pending: dict[str, dict] = {}

    def ask(self, kind: str, details: dict, cancelled: Event | None = None) -> bool:
        request_id = uuid4().hex
        done = Event()
        with self._lock:
            self.pending[request_id] = {'id': request_id, 'kind': kind,
                                        'details': details, '_event': done, '_answer': None}
        self.publish('approval_requested', {'id': request_id, 'kind': kind,
                                            'details': details})
        deadline = monotonic() + self.timeout
        while monotonic() < deadline:
            if cancelled is not None and cancelled.is_set():
                break
            if done.wait(0.2):
                break
        with self._lock:
            request = self.pending.pop(request_id, None)
        accepted = bool(request and request['_answer'] is True and
                        not (cancelled and cancelled.is_set()))
        self.publish('approval_resolved', {'id': request_id, 'approved': accepted})
        return accepted

    def answer(self, request_id: str, approved: bool) -> bool:
        with self._lock:
            request = self.pending.get(request_id)
            if not request or request['_answer'] is not None:
                return False
            request['_answer'] = approved is True
            request['_event'].set()
            return True

    def list_pending(self) -> list[dict]:
        with self._lock:
            return [{k: v for k, v in x.items() if not k.startswith('_')}
                    for x in self.pending.values()]

    def deny_all(self):
        with self._lock:
            for request in self.pending.values():
                request['_answer'] = False
                request['_event'].set()


class TeslaService:
    """One active project and at most one execution at a time.

    No provider configured? The dashboard still boots, exposes diagnostics and
    permits project selection; chat and planning return an actionable error.
    """

    def __init__(self, agent=None, *, approval_timeout=300, settings_path=None):
        self._restore_enabled = agent is None or settings_path is not None
        self._settings_path = (Path(settings_path) if settings_path else
             Path(os.environ.get('TESLA_WORKBENCH_SETTINGS', str(Path.home() / '.tesla-agent' / 'workbench.json'))))
        self._lock = RLock()
        self._events = deque(maxlen=1000)
        self._next_event_id = 0
        self.jobs: dict[str, dict] = {}
        self.active_job: str | None = None
        self.project: str | None = None
        self.agent = agent
        self.executor = None
        self.team = None
        self.init_error = None
        self.chat_history = deque(maxlen=120)
        self.approvals = ApprovalBroker(self._publish, timeout=approval_timeout)
        if self.agent is None:
            try:
                from core.agent import Agent
                self.agent = Agent()
            except Exception as exc:
                self.init_error = f'{type(exc).__name__}: {redact(str(exc))[:250]}'
        if self.agent is not None:
            from core.executor import PlanExecutor
            from core.multiagent import TeamOrchestrator
            self.executor = PlanExecutor(self.agent)
            self.agent.event_hook = self._publish
            self.executor.event_hook = self._publish
            self.team = TeamOrchestrator(self.executor)
            self.agent.confirm_tool = self._approve_tool
            self.agent.llm.paid_approval_callback = self._approve_paid
            # Keep the router's original list to support switching back to auto.
            self._available_providers = list(self.agent.llm.providers)
        else:
            self._available_providers = []
        if self._restore_enabled and self.agent is not None:
            self.restore_project()

    def restore_project(self):
        try:
            settings = json.loads(self._settings_path.read_text(encoding='utf-8'))
            previous = settings.get('last_project', '')
            if previous and Path(previous).is_dir():
                self.select_project(previous)
        except (OSError, ValueError, PermissionError, TypeError):
            pass  # Missing/invalid preferences never block startup.

    def _save_preferences(self):
        if not self._restore_enabled:
            return
        self._settings_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self._settings_path.with_suffix('.tmp')
        temp.write_text(json.dumps({'last_project': self.project}), encoding='utf-8')
        temp.replace(self._settings_path)

    def _publish(self, typ, data):
        with self._lock:
            self._next_event_id += 1
            event = {'id': self._next_event_id, 'type': typ,
                     'data': data, 'timestamp': round(time(), 3)}
            self._events.append(event)
            return event

    def events_after(self, index: int) -> list[dict]:
        with self._lock:
            return [dict(e) for e in self._events if e['id'] > index]

    def _require_engine(self):
        if self.agent is None:
            raise RuntimeError('Modelo indisponível: configure um provedor no .env e reinicie o dashboard. '
                               + str(self.init_error or ''))
        return self.agent

    def _require_project(self):
        if not self.project:
            raise ValueError('Selecione uma pasta de projeto antes de executar tarefas.')
        return self._require_engine()

    def _active_cancel(self):
        with self._lock:
            job = self.jobs.get(self.active_job) if self.active_job else None
            return job.get('_cancel') if job else None

    def _approve_tool(self, tool_name: str, arguments: dict) -> bool:
        details = {'tool': str(tool_name)[:80]}
        if tool_name == 'write_file':
            details['path'] = str(arguments.get('path', ''))[:350]
            details['preview'] = redact(str(arguments.get('content', '')))[:3500]
        elif tool_name == 'apply_patch':
            identifier = arguments.get('proposal_id', '')
            proposal = self.agent.tools.filesystem.workspace.pending.get(identifier, {})
            details['path'] = str(proposal.get('path', ''))[:350]
            details['preview'] = redact(str(proposal.get('diff', '')))[:3500]
        else:
            import json
            details['arguments'] = redact(json.dumps(arguments, ensure_ascii=False, default=str))[:1200]
        return self.approvals.ask('tool', details, self._active_cancel())

    def _approve_paid(self, request: dict) -> bool:
        safe = {key: request.get(key) for key in
                ('provider', 'model', 'task', 'estimated_usd', 'remaining_usd')}
        return self.approvals.ask('paid', safe, self._active_cancel())

    def select_project(self, path: str) -> dict:
        path = str(path or '').strip().strip('"')
        if not path or len(path) > 1000:
            raise ValueError('Informe o caminho de uma pasta existente.')
        try:
            root = Path(path).expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ValueError('Pasta do projeto não encontrada ou indisponível.') from exc
        if not root.is_dir():
            raise ValueError('Projeto precisa ser uma pasta existente.')
        with self._lock:
            if self.active_job:
                raise RuntimeError('Aguarde a execução atual terminar antes de trocar o projeto.')
            # Do not switch while a plan is pending in another project. Operator
            # must explicitly cancel/complete it in the original project.
            if self.executor and self.executor.planner.current_plan:
                plan = self.executor.planner.current_plan
                if plan.status not in ('completed', 'cancelled', 'failed') and plan.workspace:
                    if Path(plan.workspace).resolve() != root:
                        raise RuntimeError('Existe um plano ativo em outra pasta; cancele-o antes.')
            if self.agent:
                self.agent.tools.set_workspace(root, explicit=True)
                from core.plan_store import PlanStore
                from core.planner import Planner
                store = PlanStore(root / '.tesla' / 'plan.json')
                self.executor.store = store
                self.executor.planner = Planner(store.load())
            if self.project != str(root) and self.agent:
                self.agent.context.clear()
                self.chat_history.clear()
            self.project = str(root)
        try:
            self._save_preferences()
        except OSError:
            pass  # State restoration is best-effort and must not prevent selecting.
        self._publish('project_selected', {'path': self.project})
        return {'path': self.project}

    def model_status(self) -> dict:
        if not self.agent:
            return {'selected': None, 'available': [], 'decision': None}
        llm = self.agent.llm
        selected = 'auto' if llm.auto else llm.providers[0][0]
        return {'selected': selected,
                'available': ['auto'] + [item[0] for item in self._available_providers],
                'decision': llm.last_decision}

    def select_model(self, provider: str) -> dict:
        agent = self._require_engine()
        provider = provider.lower().strip()
        with self._lock:
            if self.active_job:
                raise RuntimeError('Não altere modelos durante uma execução.')
            if provider == 'auto':
                agent.llm.providers = list(self._available_providers)
                agent.llm.auto = True
            else:
                choices = [item for item in self._available_providers if item[0] == provider]
                if not choices:
                    raise ValueError('Provedor não configurado: ' + provider)
                agent.llm.providers = choices
                agent.llm.auto = False
        self._publish('model_selected', {'provider': provider})
        return self.model_status()

    def status(self) -> dict:
        with self._lock:
            jobs = [self._public_job(j) for j in self.jobs.values()]
        return {'version': '0.7.0', 'engine_ready': self.agent is not None,
                'engine_error': self.init_error, 'workspace': self.project,
                'active_job': self.active_job, 'jobs': jobs[-12:],
                'model': self.model_status(),
                'team': self.team.status() if self.team else {},
                'pending_approvals': self.approvals.list_pending(),
                'history': list(self.chat_history)}

    @staticmethod
    def _public_job(job):
        return {k: v for k, v in job.items() if not k.startswith('_')}

    def files(self, *, limit=200):
        self._require_project()
        root = Path(self.project)
        found = []
        # No symlink traversal, no hidden/private metadata. Bounded enumeration.
        for folder, dirs, filenames in os.walk(root, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in EXCLUDE and
                             not d.startswith('.env') and not Path(folder, d).is_symlink())
            for filename in sorted(filenames):
                candidate = Path(folder, filename)
                relative = candidate.relative_to(root)
                if candidate.is_symlink() or _private_path(relative):
                    continue
                found.append({'path': relative.as_posix(), 'size': candidate.stat().st_size})
                if len(found) >= limit:
                    return found
        return found

    def read_file(self, path: str):
        agent = self._require_project()
        if not path or len(path) > 750:
            raise ValueError('Caminho inválido')
        root = Path(self.project)
        candidate = root.joinpath(path)
        # Never dereference symlinks, including nested directory links.
        if candidate.is_symlink():
            raise PermissionError('Não é permitido acessar links simbólicos')
        try:
            target = candidate.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ValueError('Arquivo não encontrado') from exc
        try:
            relative = target.relative_to(root)
        except ValueError as exc:
            raise PermissionError('Arquivo fora do projeto') from exc
        if _private_path(relative) or target.is_symlink() or not target.is_file():
            raise PermissionError('Arquivo privado, link ou diretório não permitido')
        if target.stat().st_size > 200_000:
            raise ValueError('Arquivo muito grande para prévia')
        # Reuse CodingWorkspace gate, including blocking private files.
        agent.tools.filesystem.workspace.path(relative.as_posix(), allow_missing=False)
        content = target.read_text(encoding='utf-8-sig')
        return {'path': relative.as_posix(), 'content': redact(content)}

    def _job(self, kind: str, operation, description: str = '', *, on_accept=None) -> dict:
        self._require_project()
        with self._lock:
            if self.active_job is not None:
                raise RuntimeError('Já existe uma execução em andamento. Aguarde ou solicite cancelamento.')
            job_id = uuid4().hex
            job = {'id': job_id, 'kind': kind, 'description': description[:180],
                   'status': 'queued', 'result': '', 'error': '', '_cancel': Event()}
            self.jobs[job_id] = job
            self.active_job = job_id
            if callable(on_accept):
                on_accept()
            # Bound stored job logs and never retain raw prompts in event stream.
            if len(self.jobs) > 50:
                for key in list(self.jobs):
                    if key != job_id and self.jobs[key]['status'] not in ('running', 'queued'):
                        del self.jobs[key]
                        if len(self.jobs) <= 40:
                            break
        self._publish('job_queued', {'job': job_id, 'kind': kind})

        def execute():
            with self._lock:
                job['status'] = 'running'
            if self.agent is not None:
                self.agent.cancel_check = job['_cancel'].is_set
            self._publish('job_started', {'job': job_id, 'kind': kind})
            try:
                result = operation(job['_cancel'])
                job['result'] = redact(str(result))[:20000]
                evidence = getattr(self.agent, 'last_run_evidence', {}) if self.agent else {}
                if job['_cancel'].is_set():
                    job['status'] = 'cancelled'
                elif kind == 'chat' and (evidence or {}).get('interrupted'):
                    job['status'] = 'incomplete'
                elif kind == 'team_run' and self.team.status().get('status') != 'completed':
                    job['status'] = self.team.status().get('status', 'paused')
                else:
                    job['status'] = 'completed'
            except Exception as exc:
                job['status'] = 'cancelled' if job['_cancel'].is_set() else 'failed'
                job['error'] = redact(str(exc))[:900]
            finally:
                if self.agent is not None:
                    self.agent.cancel_check = None
                self._record_job(job)
                self._publish('job_finished', {'job': job_id, 'status': job['status']})
                with self._lock:
                    if self.active_job == job_id:
                        self.active_job = None

        Thread(target=execute, name='tesla-' + kind, daemon=True).start()
        return self._public_job(job)

    def chat(self, prompt: str):
        if not prompt or not prompt.strip() or len(prompt) > 12000:
            raise ValueError('Mensagem deve ter de 1 a 12000 caracteres')
        def operation(cancel):
            if cancel.is_set():
                return 'Cancelado antes da chamada.'
            answer = self.agent.run(prompt)
            self.chat_history.append({'role': 'assistant', 'content': redact(answer)[:8000]})
            return answer
        return self._job('chat', operation, prompt, on_accept=lambda:
                         self.chat_history.append({'role': 'user', 'content': redact(prompt)[:8000]}))

    def create_team(self, objective: str):
        if not objective or not objective.strip() or len(objective) > 7000:
            raise ValueError('Objetivo inválido')
        return self._job('team_plan', lambda cancel: self.team.create(objective).to_dict(), objective)

    def run_team(self):
        def operation(cancel):
            def approve_step(step):
                self._publish('team_step', {'id': step.id, 'role': step.role,
                                            'description': step.description[:250]})
                return self.approvals.ask('step',
                    {'id': step.id, 'role': step.role, 'description': step.description[:500],
                     'workspace': self.project}, cancel)
            return self.team.run(approve_step)
        return self._job('team_run', operation)

    def retry_team(self, step_id: int):
        with self._lock:
            if self.active_job:
                raise RuntimeError('Aguarde a execução terminar.')
            self.team.retry(step_id)
        self._publish('team_retry', {'step': step_id})
        return self.team.status()

    def cancel_team_plan(self):
        self._require_project()
        with self._lock:
            if self.active_job:
                raise RuntimeError('Aguarde a execução em andamento terminar; use Cancelar execução para solicitar a parada.')
            with self.executor.store.exclusive():
                self.executor.reload_if_stored()
                self.team._team()
                self.executor.planner.cancel_plan()
                self.executor.persist()
        self._publish('team_cancelled', {'workspace': self.project})
        return self.team.status()

    def rework_team(self):
        with self._lock:
            if self.active_job:
                raise RuntimeError('Aguarde a execução terminar.')
            result = self.team.rework()
        self._publish('team_rework', {'message': str(result)[:200]})
        return self.team.status()

    def test(self, target='all'):
        if len(target) > 100:
            raise ValueError('Destino de testes longo demais')
        def operation(cancel):
            if not self.approvals.ask('tool', {'tool': 'run_tests', 'arguments': {'target': target}}, cancel):
                raise PermissionError('Execução de testes não autorizada.')
            return self.agent.tools.execute('run_tests', {'target': target})
        return self._job('test', operation)

    def diff(self, path: str):
        self._require_project()
        if not path or len(path) > 750:
            raise ValueError('Caminho inválido')
        root = Path(self.project)
        relative = Path(path)
        resolved = (root / relative).resolve()
        try:
            rel = resolved.relative_to(root)
        except ValueError as exc:
            raise PermissionError('Arquivo fora do projeto') from exc
        if _private_path(rel):
            raise PermissionError('Arquivo protegido')
        return redact(str(self.agent.tools.execute('diff_file', {'path': rel.as_posix()})))

    def project_memory(self):
        self._require_project()
        return self.agent.tools.get_project_memory().list()

    def remember(self, text):
        self._require_project()
        if not text or len(text) > 2000:
            raise ValueError('Nota inválida')
        if self.active_job:
            raise RuntimeError('Aguarde a execução antes de salvar memórias')
        return self.agent.tools.get_project_memory().add(text)

    def recall(self, query):
        self._require_project()
        if not query or len(query) > 2000:
            raise ValueError('Consulta inválida')
        return {'notes': self.agent.tools.get_project_memory().recall(query),
                'sources': self.agent.tools.get_knowledge().search(query)}

    def tools_status(self):
        agent = self._require_project()
        return {'tools': agent.tools.list_tools(),
                'mcp': agent.tools.mcp.status(),
                'usage': agent.llm.usage.summary(),
                'last_evidence': agent.last_run_evidence}

    def request_cancel(self, job_id):
        with self._lock:
            job = self.jobs.get(job_id)
            if not job or job['status'] not in ('running', 'queued'):
                raise ValueError('Execução não encontrada ou já finalizada')
            job['_cancel'].set()
        self.approvals.deny_all()
        self._publish('cancel_requested', {'job': job_id})
        return {'cancel_requested': True, 'note': 'Cancelamento cooperativo; chamadas LLM em andamento não são interrompidas imediatamente.'}

    def team_report(self):
        self._require_project()
        return self.team.status()

    def _record_job(self, job):
        """Persist only sanitized operational metadata, never messages or tool payloads."""
        if not self.project:
            return
        entry = {'id': job['id'], 'kind': job['kind'], 'status': job['status'],
                 'timestamp': round(time(), 3),
                 'error': redact(str(job.get('error') or ''))[:160]}
        try:
            target = Path(self.project) / '.tesla' / 'web_jobs.jsonl'
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except OSError:
            pass  # Observability must never block work.

    def job_history(self):
        self._require_project()
        target = Path(self.project) / '.tesla' / 'web_jobs.jsonl'
        if not target.is_file():
            return []
        try:
            lines = target.read_text(encoding='utf-8').splitlines()[-80:]
            return [json.loads(line) for line in lines if line.strip()]
        except (OSError, ValueError):
            return []
