from llm.router import LLMRouter


class Agent:

    def __init__(self):
        self.llm = LLMRouter()

    def run(self, user_input: str) -> str:

        prompt = f"""
Você é Hefesto, um agente de inteligência artificial
especializado em ajudar o usuário.

Responda de forma clara, objetiva e útil.

Usuário:
{user_input}
"""

        return self.llm.generate(prompt)
