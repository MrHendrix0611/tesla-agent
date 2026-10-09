from core.agent import Agent


def main():

    print("=" * 50)
    print("🔥 HEFESTO AGENT V0.3")
    print("=" * 50)
    print("Digite 'sair' para encerrar.")
    print()

    agent = Agent()

    while True:

        user_input = input("Você: ")

        if user_input.lower() in ["sair", "exit", "quit"]:
            print("Hefesto encerrado.")
            break

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