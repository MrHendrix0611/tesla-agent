from core.agent import Agent
from core.executor import PlanExecutor
import json


def show_skills(agent):

    skills = agent.skills.list_skills()

    print()
    print("Skills disponíveis:")

    for skill in skills:
        marker = ""

        if skill == agent.get_active_skill():
            marker = " ← ativa"

        print(f"- {skill}{marker}")

    print()


def confirm_paid_call(request):
    """Require explicit affirmative confirmation for each paid API call."""
    print('\n[Tesla] Autorização para modelo pago')
    print(f"Provider: {request['provider']} | Modelo: {request['model']}")
    print(f"Tarefa: {request['task']}")
    print(f"Custo estimado*: US$ {request['estimated_usd']:.6f}")
    print(f"Orçamento local restante: US$ {request['remaining_usd']:.6f}")
    print('* Estimativa, não cobrança garantida. Verifique o limite na API.')
    return input('Autorizar ESTA chamada? Digite SIM: ').strip().upper() == 'SIM'


def main():

    print("=" * 50)
    print("🔥 TESLA AGENT V0.5.9")
    print("=" * 50)

    agent = Agent()
    plans = PlanExecutor(agent)
    agent.llm.paid_approval_callback = confirm_paid_call

    print()
    print("Comandos:")
    print("/skills        → listar Skills")
    print("/skill <nome>  → ativar uma Skill")
    print("/skill off     → desativar Skill")
    print("/tools         → listar Tools")
    print("/usage         → consumo local")
    print("/router        → última decisão")
    print("/paid          → modo de autorização e orçamento")
    print("/stats         → relatório de consumo e erros")
    print("/audit         → últimas decisões e falhas do roteador")
    print("/project <caminho> → selecionar repositório")
    print("/map           → mapa do repositório")
    print("/find <texto>  → pesquisar código")
    print("/symbols [termo] → localizar símbolos")
    print("/plan create <objetivo> → gerar plano com IA")
    print("/plan         → mostrar plano atual")
    print("/steps        → listar etapas")
    print("/resume       → executar etapas autorizadas")
    print("/retry <id>   → repetir etapa com falha")
    print("/cancel       → cancelar plano")
    print("/workspace    → mostrar pasta de trabalho ativa")
    print("/diff <arquivo> → mostrar última alteração do Tesla")
    print("/rollback <arquivo> → desfazer última alteração do Tesla")
    print("/test [módulo|all|discover] → executar unittest real")
    print("/diagnose     → status local sem exibir chaves")
    print("/index        → atualizar índice local do projeto (RAG)")
    print("/recall <tema> → buscar no código e na memória do projeto")
    print("/remember <nota> → salvar decisão explicitamente no projeto")
    print("/memories     → listar memórias salvas do projeto")
    print("/forget <id>  → remover uma nota pelo identificador")
    print("/context      → estatísticas do histórico compacto da sessão")
    print("/clearcontext → limpar histórico temporário da sessão")
    print("/mcp         → listar servidores MCP configurados")
    print("/mcp config  → mostrar local do arquivo de configuração")
    print("/mcp connect <nome> → conectar servidor (aprovação obrigatória)")
    print("/mcp tools <nome> → listar ferramentas do servidor")
    print("/mcp disconnect <nome> → encerrar conexão")
    print("/mcp call <servidor> <ferramenta> <json> → invocar com aprovação")
    print("/sair          → encerrar")
    print()

    while True:

        user_input = input("Você: ").strip()

        if not user_input:
            continue

        if user_input.lower() in [
            "/sair",
            "sair",
            "exit",
            "quit"
        ]:
            print("Tesla encerrado.")
            break

        if user_input.lower() == '/context':
            print(json.dumps(agent.context.status(), ensure_ascii=False, indent=2))
            continue

        if user_input.lower() == '/clearcontext':
            agent.context.clear()
            print('Contexto temporário limpo. Notas e índice de projeto foram preservados.')
            continue

        if user_input.lower() in ('/index', '/memories') or user_input.lower().startswith((
                '/remember ', '/forget ', '/recall ')):
            if not agent.tools.workspace_selected:
                print('Selecione primeiro o projeto com /project <caminho>.')
                continue
            try:
                command = user_input.split(maxsplit=1)[0].lower()
                argument = user_input[len(command):].strip()
                if command == '/index':
                    print(json.dumps(agent.tools.get_knowledge().refresh(), ensure_ascii=False, indent=2))
                elif command == '/memories':
                    print(json.dumps(agent.tools.get_project_memory().list(), ensure_ascii=False, indent=2))
                elif command == '/remember':
                    print(json.dumps(agent.tools.get_project_memory().add(argument), ensure_ascii=False, indent=2))
                elif command == '/forget':
                    print('Memória removida.' if agent.tools.get_project_memory().forget(argument)
                          else 'Nota não encontrada.')
                elif command == '/recall':
                    print(json.dumps({
                        'notes': agent.tools.get_project_memory().recall(argument),
                        'sources': agent.tools.get_knowledge().search(argument)
                    }, ensure_ascii=False, indent=2))
            except (ValueError, OSError, PermissionError) as error:
                print(f'Erro na memória/indexação: {error}')
            continue

        if user_input.lower() == '/mcp' or user_input.lower().startswith('/mcp '):
            if not agent.tools.workspace_selected:
                print('Selecione primeiro um projeto com /project <caminho>.')
                continue
            try:
                parts = user_input.split(maxsplit=3)
                action = parts[1].lower() if len(parts) > 1 else 'list'
                manager = agent.tools.mcp
                if action == 'list':
                    print(json.dumps(manager.status(), ensure_ascii=False, indent=2))
                elif action == 'config':
                    print('Arquivo de configuração:', manager.config_path)
                    print('Edite manualmente a configuração. Nunca coloque chaves literais no arquivo; prefira ${VARIAVEL}.')
                elif action == 'connect' and len(parts) == 3:
                    name = parts[2]
                    config = manager.configured().get(name)
                    if config is None:
                        raise ValueError('Servidor não configurado: ' + name)
                    print('Executável configurado:', str((config.get('command') or [''])[0]))
                    print('Quantidade de argumentos adicionais:', max(0, len(config.get('command') or []) - 1))
                    print('Servidor MCP externo pode acessar dados e executar operações com suas permissões.')
                    if input('Autoriza INICIAR este processo? Digite SIM: ').strip().upper() == 'SIM':
                        print('Ferramentas:', json.dumps(manager.connect(name), ensure_ascii=False))
                    else:
                        print('Conexão não autorizada.')
                elif action == 'disconnect' and len(parts) == 3:
                    print('Desconectado.' if manager.disconnect(parts[2]) else 'Servidor não conectado.')
                elif action == 'tools' and len(parts) == 3:
                    connection = manager.connections.get(parts[2])
                    if connection is None:
                        raise ValueError('Servidor não conectado')
                    print(json.dumps(list(connection.tool_schemas), ensure_ascii=False, indent=2))
                elif action == 'call' and len(parts) == 4:
                    details = parts[3].split(maxsplit=1)
                    if len(details) != 2:
                        raise ValueError('Uso: /mcp call <servidor> <ferramenta> <json>')
                    name, raw = details
                    args = json.loads(raw)
                    if not isinstance(args, dict):
                        raise ValueError('Argumentos devem ser um objeto JSON')
                    alias = next((a for a,(server,tool) in manager.aliases.items()
                                  if server == parts[2] and tool == name), None)
                    if not alias:
                        raise ValueError('Ferramenta não encontrada ou servidor desconectado')
                    if agent.confirm_tool(alias, args):
                        print(agent.tools.execute(alias, args))
                    else:
                        print('Chamada MCP não autorizada.')
                else:
                    print('Uso: /mcp [config|connect <nome>|tools <nome>|disconnect <nome>|call <servidor> <ferramenta> <json>]')
            except (ValueError, OSError, RuntimeError, json.JSONDecodeError) as error:
                print('Erro MCP:', str(error)[:350])
            continue

        if user_input.lower() == "/workspace":
            print("Diretório:", agent.tools.get_workspace())
            print("Projeto selecionado explicitamente:",
                  'SIM' if agent.tools.workspace_selected else 'NÃO — use /project <caminho>')
            continue

        if user_input.lower() == "/diagnose":
            status = {
                "workspace": str(agent.tools.get_workspace()),
                "provider_selecionado": str(agent.llm.last_decision or "Nenhuma chamada nesta sessão"),
                "plano": plans.planner.current_plan.status if plans.planner.current_plan else "nenhum",
                "ferramentas": len(agent.tools.get_tool_definitions()),
                "contexto": agent.context.status(),
                "knowledge": (agent.tools.get_knowledge().stats()
                              if agent.tools.workspace_selected else "projeto não selecionado"),
                "ciclo_agente_ultimo": {
                    "tentativas": agent.last_run_evidence.get("attempted_tools", 0),
                    "sucessos": len(agent.last_run_evidence.get("tools", [])),
                    "falhas": len(agent.last_run_evidence.get("tool_errors", [])),
                }
            }
            print(json.dumps(status, ensure_ascii=False, indent=2))
            continue

        if user_input.lower().startswith("/diff "):
            try:
                path = user_input[6:].strip().strip('"')
                print(json.dumps(agent.tools.execute("diff_file", {"path": path}), ensure_ascii=False, indent=2))
            except (OSError, ValueError, PermissionError) as error:
                print(f"Erro: {error}")
            continue

        if user_input.lower().startswith("/rollback "):
            if not agent.tools.workspace_selected:
                print('Selecione primeiro o projeto com /project <caminho>.')
                continue
            try:
                path = user_input[10:].strip().strip('"')
                arguments = {"path": path}
                if agent.confirm_tool("rollback_file", arguments):
                    print(agent.tools.execute("rollback_file", arguments))
                else:
                    print("Rollback não autorizado.")
            except (OSError, ValueError, PermissionError, RuntimeError) as error:
                print(f"Erro: {error}")
            continue

        if user_input.lower() == "/test" or user_input.lower().startswith("/test "):
            if not agent.tools.workspace_selected:
                print('Selecione primeiro o projeto com /project <caminho>.')
                continue
            try:
                target = user_input[5:].strip() or "all"
                arguments = {"target": target}
                if agent.confirm_tool("run_tests", arguments):
                    print(agent.tools.execute("run_tests", arguments))
                else:
                    print("Testes não autorizados.")
            except (OSError, ValueError, PermissionError, RuntimeError) as error:
                print(f"Erro: {error}")
            continue

        if user_input.lower() == "/plan" or user_input.lower() == "/steps":
            print(json.dumps(plans.planner.summary(), ensure_ascii=False, indent=2))
            continue

        if user_input.lower().startswith("/plan create "):
            try:
                plan = plans.generate(user_input[len("/plan create "):].strip())
                print(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2))
                print("Revise o plano e use /resume para executar.")
            except Exception as error:
                print(f"Erro no planejamento: {error}")
            continue

        if user_input.lower() == "/resume":
            if not agent.tools.workspace_selected:
                print('Selecione o projeto com /project <caminho> antes de /resume.')
                continue
            def confirm_plan_step(step):
                print(f"Etapa {step.id}: {step.description}")
                print('Destino do plano:', plans.planner.current_plan.workspace)
                return input("Executar esta etapa? Digite SIM: ").strip().upper() == "SIM"
            print(plans.run(confirm_plan_step))
            continue

        if user_input.lower().startswith("/retry "):
            try:
                plans.retry(int(user_input.split()[1]))
                print("Etapa desbloqueada. Use /resume.")
            except (ValueError, IndexError) as error:
                print(f"Erro: {error}")
            continue

        if user_input.lower() == "/cancel":
            try:
                plans.planner.cancel_plan()
                plans.persist()
                print("Plano cancelado.")
            except ValueError as error:
                print(f"Erro: {error}")
            continue

        if user_input.lower().startswith("/project "):
            try:
                project_path = user_input[len("/project "):].strip().strip('"')
                previous_root = str(agent.tools.get_workspace()) if agent.tools.workspace_selected else None
                summary = agent.tools.set_repository(project_path)
                if previous_root != str(agent.tools.get_workspace()):
                    agent.context.clear()  # do not carry old-project conversation into new project
                print(f"Projeto selecionado: {summary['root']} ({summary['files_indexed']} arquivos)")
            except (OSError, ValueError) as error:
                print(f"Erro ao selecionar projeto: {error}")
            continue

        if user_input.lower() == "/map":
            print(json.dumps(agent.tools.get_repository().summary(), ensure_ascii=False, indent=2))
            continue

        if user_input.lower().startswith("/find "):
            try:
                print(json.dumps(agent.tools.get_repository().search(user_input[6:].strip()), ensure_ascii=False, indent=2))
            except ValueError as error: print(error)
            continue

        if user_input.lower() == "/symbols" or user_input.lower().startswith("/symbols "):
            print(json.dumps(agent.tools.get_repository().symbols(user_input[8:].strip()), ensure_ascii=False, indent=2))
            continue

        if user_input.lower() == "/stats":
            from llm.observability import usage_report
            print(json.dumps(usage_report(agent.llm.usage), indent=2, ensure_ascii=False))
            continue

        if user_input.lower() == "/audit":
            print(json.dumps(agent.llm.audit.recent(20), indent=2, ensure_ascii=False))
            continue

        if user_input.lower() == "/usage":
            print(json.dumps(agent.llm.usage.summary(), indent=2, ensure_ascii=False))
            continue

        if user_input.lower() == "/router":
            print(agent.llm.last_decision or "Nenhuma seleção realizada ainda.")
            continue

        if user_input.lower() == "/paid":
            budget = agent.llm.budget
            print(f"Modo: {budget.mode()} | Orçamento restante estimado: US$ {budget.remaining():.6f}")
            print("Altere PAID_USAGE_MODE no .env e reinicie para mudar o modo.")
            continue

        if user_input.lower() == "/tools":
            tools = agent.tools.list_tools()
            print()
            print("Tools disponíveis")

            for tool in tools:
                print(f"- {tool}")

            print()

            continue

        if user_input.lower() == "/skills":

            show_skills(agent)
            continue

        if user_input.lower().startswith("/skill"):

            parts = user_input.split(maxsplit=1)

            if len(parts) == 1:

                active = agent.get_active_skill()

                if active:
                    print(
                        f"Skill ativa: {active}"
                    )
                else:
                    print(
                        "Nenhuma Skill ativa."
                    )

                continue

            skill_name = parts[1].strip()

            if skill_name.lower() == "off":

                agent.clear_skill()

                print(
                    "Skill desativada."
                )

                continue

            try:

                agent.set_skill(skill_name)

                print(
                    f"Skill '{skill_name}' ativada."
                )

            except ValueError as error:

                print(error)

            continue

        if user_input.startswith('/'):
            print('Comando desconhecido. Verifique a grafia e consulte os comandos acima.')
            continue

        try:
            response = agent.run(user_input)

            print()
            print(f"Tesla: {response}")
            print()

        except Exception as error:

            print()
            print(f"Erro: {error}")
            print()


if __name__ == "__main__":
    main()