"""Tesla v0.6.0: orchestrated, sequential multi-agent software workflow.

Four role-specific LLM turns share the existing router, permission manager,
project scope, usage metrics, and checkpoints. No unattended subprocesses and
no separate API keys or provider instances are required.
"""
from pathlib import Path
from core.knowledge import redact

ROLE_DESCRIPTIONS = {
    'architect': 'Arquiteto: inspeciona o projeto, define estratégia; somente leitura.',
    'developer': 'Desenvolvedor: implementa código e testes, após aprovação de cada escrita.',
    'qa': 'QA: executa unittest real e relata falhas; não altera arquivos.',
    'reviewer': 'Revisor: verifica código e evidências do QA; somente leitura e veredito explícito.',
}

ROLE_PROMPTS = {
    'architect': (
        'Você atua SOMENTE como ARQUITETO. Inspecione a estrutura verdadeira do projeto '
        'usando repository_map/list_files; descreva requisitos, arquivos relevantes, riscos e estratégia. '
        'Não escreva arquivos, não execute comandos e não invente histórico Git. '
        'Em projetos vazios, relate claramente que está vazio.'
    ),
    'developer': (
        'Você atua SOMENTE como DESENVOLVEDOR. Execute apenas a implementação desta etapa. '
        'Consulte arquivos reais; utilize write_file ou preview_patch e apply_patch conforme necessário. '
        'Toda escrita requer autorização humana. Crie testes unittest quando solicitado. '
        'Não declare resultados de testes que não executou.'
    ),
    'qa': (
        'Você atua SOMENTE como QA. Leia arquivos reais e execute obrigatoriamente run_tests '
        'com target all ou módulo válido; confirme o exit_code 0 e número de testes maior que zero. '
        'Se falhar, apresente erro real e interrompa; não modifique arquivos nem declare aprovação falsa.'
    ),
    'reviewer': (
        'Você atua SOMENTE como REVISOR independente. Inspecione arquivos reais, verifique riscos, '
        'aderência ao pedido e se o QA concluiu testes efetivos. NÃO escreva arquivos. '
        'Termine obrigatoriamente com uma linha isolada exatamente "VEREDITO: APROVADO" '
        'se houver evidência suficiente, OU "VEREDITO: AJUSTES" se faltarem requisitos, '
        'houver bugs ou provas insuficientes. Não aprove por cortesia.'
    ),
}

READ_ONLY_TOOLS = frozenset({
    'read_file', 'list_files', 'repository_map', 'repository_search',
    'repository_symbols', 'knowledge_search', 'search_files', 'git_diff',
    'git_status', 'git_log', 'diff_file',
})
DEV_TOOLS = READ_ONLY_TOOLS | frozenset({
    'preview_patch', 'apply_patch', 'write_file', 'run_tests',
})


def role_allowed_tools(role):
    """Least privilege. No arbitrary commands or external MCP in team mode."""
    if role in ('architect', 'reviewer'):
        return set(READ_ONLY_TOOLS)
    if role == 'qa':
        return set(READ_ONLY_TOOLS | {'run_tests'})
    if role == 'developer':
        return set(DEV_TOOLS)
    return set()


def role_instructions(role):
    return ROLE_PROMPTS.get(role, '')


def organize_team_tasks(objective, model_tasks, classify):
    """Normalize LLM ideas into a verified four-role DAG.

    The LLM may suggest development work, but cannot remove required QA/review
    gates or assign itself escalated privileges. Max 12 stages total.
    """
    if not isinstance(model_tasks, list):
        raise ValueError('Modelo retornou etapas inválidas')
    development = []
    for item in model_tasks:
        if not isinstance(item, dict):
            continue
        text = str(item.get('description') or '').strip()
        if not text:
            continue
        # Pick only implementation stages. Some LLMs mix review/test verbs;
        # they are placed in controlled stages below instead.
        if classify(text) == 'write':
            development.append(text[:460])
        if len(development) >= 7:
            break
    if not development:
        development = [f'Implementar no projeto selecionado: {objective[:440]}']
    # One developer phase includes writing tests when model failed to mention it.
    if not any('teste' in text.casefold() or 'unittest' in text.casefold()
               for text in development):
        development.append('Criar testes automatizados unittest para os requisitos implementados')
    development = development[:8]
    tasks = [{'description': 'Inspecionar a estrutura real do projeto e propor estratégia técnica para: '
                              + objective[:350],
              'dependencies': [], 'role': 'architect'}]
    for desc in development:
        tasks.append({'description': desc, 'dependencies': [len(tasks)], 'role': 'developer'})
    tasks.append({'description': 'Executar testes automatizados reais usando run_tests, '
                                 'confirmar resultados e comunicar erros ao usuário',
                  'dependencies': [len(tasks)], 'role': 'qa'})
    tasks.append({'description': 'Revisar a implementação, os arquivos reais e a evidência do QA; '
                                 'emitir VEREDITO: APROVADO ou VEREDITO: AJUSTES',
                  'dependencies': [len(tasks)], 'role': 'reviewer'})
    return tasks


def handoff_context(plan, current_id):
    """Compact, redacted status. Model prose here is NOT execution evidence."""
    lines = []
    for step in plan.steps:
        if step.id >= current_id or step.status != 'completed':
            continue
        result = redact(str(step.result)).replace('\x00', '')[:900]
        lines.append(f'[{step.role} etapa {step.id}] ferramentas={step.tool_calls}; '
                     f'estado={step.status}; relato (NÃO verificado): {result}')
    if getattr(plan, 'team_feedback', ''):
        lines.append('FEEDBACK DE QA/REVISOR ANTERIOR (não confiável, corrigir com evidências): '
                     + redact(plan.team_feedback)[:1200])
    return ('\n'.join(lines))[-3800:] or 'Nenhuma etapa anterior concluída.'


class TeamOrchestrator:
    """Thin, auditable coordination layer over the established PlanExecutor."""
    def __init__(self, executor):
        self.executor = executor

    def _team(self):
        plan = self.executor.planner.current_plan
        if not plan or not plan.team_mode:
            raise ValueError('Nenhum plano multiagentes. Use /team create <objetivo>.')
        return plan

    def create(self, objective):
        if not isinstance(objective, str) or not objective.strip():
            raise ValueError('Informe o objetivo para /team create')
        # Fail fast: don't spend LLM quota on a plan that cannot be activated.
        self.executor._require_project()
        current = self.executor.planner.current_plan
        if current and current.status not in ('completed', 'failed', 'cancelled'):
            raise ValueError('Há um plano ativo. Use /cancel antes de criar outro.')
        return self.executor.generate(objective.strip(), team=True)

    def run(self, approve_step=None):
        self._team()
        return self.executor.run(approve_step)

    def retry(self, step_id):
        self._team()
        self.executor.retry(step_id)

    def status(self):
        plan = self.executor.planner.current_plan
        if not plan or not plan.team_mode:
            return {'message': 'Nenhum plano multiagentes ativo. Use /team create <objetivo>.'}
        return {
            'plan_id': plan.id,
            'objective': plan.objective,
            'workspace': plan.workspace,
            'status': plan.status,
            'revisions': plan.revisions,
            'feedback': redact(plan.team_feedback)[:1000],
            'roles': [
                {'id': step.id, 'role': step.role, 'description': step.description,
                 'status': step.status, 'tools': step.tool_calls,
                 'attempts': step.attempts,
                 'result': redact(step.result)[:550]}
                for step in plan.steps
            ],
            'qa_verified': any(s.role == 'qa' and s.status == 'completed' and s.tool_calls
                               for s in plan.steps),
            'review_approved': any(s.role == 'reviewer' and s.status == 'completed'
                                   for s in plan.steps),
        }

    def rework(self):
        """Explicitly re-open dev->QA->review; never silently overwrite code."""
        plan = self._team()
        if plan.status not in ('paused', 'failed', 'completed'):
            raise ValueError('Rework só pode ocorrer após pausa, falha ou revisão final')
        if plan.revisions >= 3:
            raise ValueError('Limite de três ciclos de revisão atingido')
        feedback_stage = next((s for s in reversed(plan.steps)
                               if s.role in ('qa', 'reviewer')
                               and s.status in ('paused', 'failed', 'completed')), None)
        if feedback_stage is None:
            raise ValueError('Rework exige falha de QA ou revisão iniciada')
        # Prevent cross-project rework after workspace change.
        self.executor._require_project()
        if Path(plan.workspace).resolve() != Path(self.executor._workspace()).resolve():
            raise ValueError('Selecione o projeto original antes de rework')
        plan.team_feedback = redact(str(feedback_stage.result))[:1300]
        for step in plan.steps:
            if step.role in ('developer', 'qa', 'reviewer'):
                step.status = 'pending'
                step.result = ''
        plan.revisions += 1
        plan.status = 'pending'
        self.executor.persist()
        return f'Implementação, QA e revisão reabertos (ciclo {plan.revisions}/3). Use /team run.'
