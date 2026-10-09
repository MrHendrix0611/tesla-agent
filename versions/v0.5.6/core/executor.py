"""Execução sequencial de tarefas, com confirmação de etapas e checkpoints."""
import json
import os
from pathlib import Path
from core.planner import Planner
from core.plan_store import PlanStore

class PlanExecutor:
    def __init__(self, agent, store=None):
        self.agent = agent
        self.store = store or PlanStore()
        self.planner = Planner(self.store.load())
        self.max_steps_per_resume = 8

    def persist(self):
        if self.planner.current_plan:
            self.store.save(self.planner.current_plan)

    def create(self, objective, tasks):
        current = self.planner.current_plan
        if current and current.status not in ("completed", "failed", "cancelled"):
            raise ValueError("Há plano ativo; use /cancel antes de criar outro")
        plan = self.planner.create_plan(objective, tasks)
        self.persist()
        return plan

    def generate(self, objective):
        """Solicita um plano JSON à LLM; não executa ações durante planejamento."""
        if not objective.strip():
            raise ValueError("Informe o objetivo")
        prompt = ("Gere somente JSON válido, sem markdown. Esquema: "
                  "{\"steps\":[{\"description\":\"ação objetiva verificável\",\"dependencies\":[]}]} "
                  "até 8 etapas, ids implícitos 1..N, dependências inteiras anteriores. "
                  "Cada etapa deve ter um único resultado verificável; não combine criação, implementação e testes na mesma etapa. "
                  "Use somente o mínimo de etapas necessárias. Inclua inspeção, implementação e testes quando pertinente. "
                  "Não diga que executou tarefas. Objetivo: " + objective[:3000])
        result = self.agent.llm.generate([{"role": "system", "content": "Você é planejador de software. Responda apenas JSON válido."},
                                          {"role": "user", "content": prompt}])
        raw = result.get("content", "")
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            import re
            match = re.search(r"```(?:json)?\s*(.*?)```", raw, re.S)
            if not match:
                raise ValueError("Modelo não retornou JSON válido; tente /plan create novamente")
            data = json.loads(match.group(1))
        if not isinstance(data, dict):
            raise ValueError("Plano inválido")
        return self.create(objective, data.get("steps"))

    def run(self, confirm_step=None):
        plan = self.planner.current_plan
        if not plan:
            return "Nenhum plano. Use /plan create <objetivo>."
        if plan.status in ("cancelled", "completed"):
            return f"Plano está {plan.status}."
        if plan.status in ("failed", "paused"):
            return "Plano interrompido. Revise /steps e use /retry <id> para liberar a etapa; depois /resume."
        notes = []
        for _ in range(self.max_steps_per_resume):
            step = self.planner.next_step()
            if step is None:
                break
            if confirm_step and not confirm_step(step):
                notes.append(f"Etapa {step.id} não autorizada; plano pausado.")
                break
            self.planner.start_step(step.id)
            self.persist()
            root = Path.cwd().resolve()
            # Informação do diretório real enviada a cada etapa; o modelo
            # não deve confundir comandos (/retry) com diretórios.
            known_files = []
            for filename in ("calculator.py", "test_calculator.py"):
                candidate = root / filename
                if candidate.is_file():
                    known_files.append(str(candidate))
            known = ", ".join(known_files) if known_files else "nenhum dos arquivos padrão encontrado"
            instruction = (f"PLANO {plan.id}, ETAPA {step.id}/{len(plan.steps)}: {step.description}\n"
                           f"Objetivo geral (contexto, NÃO EXECUTAR AGORA): {plan.objective}\n"
                           f"DIRETÓRIO REAL DO PROJETO: {root}\n"
                           f"ARQUIVOS CONFIRMADOS NESTE DIRETÓRIO: {known}\n"
                           "IMPORTANTE: /retry, /resume e /plan são comandos da CLI, NÃO diretórios. "
                           "Nunca use /retry/calculator.py, /retry/test_calculator.py ou caminhos inventados. "
                           "Use paths absolutos retornados acima para read_file/write_file, "
                           "ou um nome relativo simples que seja resolvido na raiz. "
                           "Se uma leitura falhar por caminho inexistente, consulte list_files('.') e corrija o caminho. "
                           "Priorize caminhos absolutos do Windows (C:\\...) ou nomes relativos de arquivos. "
                           "Nunca use /C/Users/... como caminho Windows. "
                           "Para testar Python no Windows, prefira py -m unittest, sem pytest, sem && e sem cd. "
                           "run_command só recebe o argumento command (não recebe cwd). "
                           "Se a etapa é apenas criar estrutura, não execute testes ou implemente outras etapas. "
                           "Execute APENAS esta etapa. Antes de escrever ou sobrescrever, leia os arquivos atuais e preserve o trabalho existente. Se a etapa já estiver pronta, comprove com leitura ou execução. "
                           "nunca declare testes executados sem run_command. "
                           "No final diga o que foi executado e o que não foi verificado. "
                           "Não execute etapas posteriores.")
            try:
                response = self.agent.run(instruction, plan_step=True)
                evidence = self.agent.last_run_evidence
                if evidence.get("interrupted") or not evidence.get("finished", False):
                    self.planner.pause_step(step.id, "Limite de iterações/ferramentas atingido. Confira os arquivos antes de retomar.",
                                            len(evidence.get("tools", [])), evidence.get("attempted_tools", 0))
                    notes.append(f"Etapa {step.id}: pausada ({evidence.get('attempted_tools', 0)} tentativas de ferramenta). Use /retry {step.id} após revisar os arquivos.")
                    self.persist()
                    break
                if evidence.get("denied"):
                    self.planner.pause_step(step.id, "Operação não autorizada; nenhuma conclusão presumida.",
                                            len(evidence.get("tools", [])), evidence.get("attempted_tools", 0))
                    notes.append(f"Etapa {step.id}: pausada por ausência de autorização.")
                    self.persist()
                    break
                if evidence.get("tool_errors"):
                    # Um caminho inválido não deve transformar o plano inteiro em
                    # falha irrecuperável; preserve as etapas já concluídas.
                    errors = str(evidence["tool_errors"])[:500]
                    if ("Arquivo não encontrado" in errors or
                            "Diretório não encontrado" in errors):
                        self.planner.pause_step(step.id,
                                                "Caminho de arquivo inválido: " + errors,
                                                len(evidence.get("tools", [])),
                                                evidence.get("attempted_tools", 0))
                        notes.append(f"Etapa {step.id}: pausada por caminho inválido. "
                                     f"Corrija o caminho e use /retry {step.id}, depois /resume.")
                        self.persist()
                        break
                    raise RuntimeError("Falha de ferramenta: " + errors)
                # Etapas que requerem ações reais não são concluídas sem chamadas a ferramentas.
                action_words = ("crie ", "criar ", "implemente", "modifique", "corrija", "execute", "teste ", "testar ", "salve ")
                action = step.description.lower()
                used = evidence.get("tools", [])
                if any(word in action for word in action_words) and not used:
                    raise RuntimeError("Não houve execução de ferramentas; não é possível validar a etapa")
                if any(word in action for word in ("crie ", "criar ", "implemente", "modifique", "corrija", "salve ")) and not any(t in used for t in ("write_file", "read_file", "run_command")):
                    raise RuntimeError("Etapa sem verificação de escrita ou estado atual")
                if any(word in action for word in ("execute", "teste ", "testar ")) and "run_command" not in used:
                    raise RuntimeError("Etapa de execução sem run_command comprovado")
                self.planner.complete_step(step.id, response, len(evidence.get("tools", [])))
                notes.append(f"Etapa {step.id}: concluída ({len(evidence.get('tools', []))} ferramentas).")
            except Exception as exc:
                evidence = getattr(self.agent, "last_run_evidence", {})
                self.planner.fail_step(step.id, str(exc), len(evidence.get("tools", [])))
                notes.append(f"Etapa {step.id}: falhou: {exc}")
                self.persist()
                break
            self.persist()
        return "\n".join(notes) + "\nEstado: " + self.planner.current_plan.status

    def retry(self, step_id):
        self.planner.retry_step(step_id)
        self.persist()
