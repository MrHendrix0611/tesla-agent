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


def main():

    print("=" * 50)
    print("🔥 HEFESTO AGENT V0.4")
    print("=" * 50)

    agent = Agent()

    print()
    print("Comandos:")
    print("/skills        → listar Skills")
    print("/skill <nome>  → ativar uma Skill")
    print("/skill off     → desativar Skill")
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