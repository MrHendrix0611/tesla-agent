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
    print("🔥 TESLA AGENT V0.5.6")
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
            def confirm_plan_step(step):
                print(f"Etapa {step.id}: {step.description}")
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
                summary = agent.tools.set_repository(project_path)
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