from core.agent import Agent


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
    print('\n[Hefesto] Autorização para modelo pago')
    print(f"Provider: {request['provider']} | Modelo: {request['model']}")
    print(f"Tarefa: {request['task']}")
    print(f"Custo estimado*: US$ {request['estimated_usd']:.6f}")
    print(f"Orçamento local restante: US$ {request['remaining_usd']:.6f}")
    print('* Estimativa, não cobrança garantida. Verifique o limite na API.')
    return input('Autorizar ESTA chamada? Digite SIM: ').strip().upper() == 'SIM'


def main():

    print("=" * 50)
    print("🔥 HEFESTO AGENT V0.5.3")
    print("=" * 50)

    agent = Agent()
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
            print("Hefesto encerrado.")
            break

        if user_input.lower() == "/usage":
            import json
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
            print(f"Hefesto: {response}")
            print()

        except Exception as error:

            print()
            print(f"Erro: {error}")
            print()


if __name__ == "__main__":
    main()