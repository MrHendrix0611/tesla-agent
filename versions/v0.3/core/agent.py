from core.context import ContextManager
from llm.router import LLMRouter


class Agent:

    def __init__(self):

        self.llm = LLMRouter()
        self.context = ContextManager()

        self.system_prompt = """
Você é Hefesto, um agente de inteligência artificial
especializado em ajudar o usuário.

Responda de forma clara, objetiva e útil.
"""

    def run(self, user_input: str) -> str:

        self.context.add_user_message(user_input)

        messages = [
            {
                "role": "system",
                "content": self.system_prompt
            }
        ]

        messages.extend(
            self.context.get_messages()
        )

        response = self.llm.generate(messages)

        self.context.add_assistant_message(response)

        return response

    def clear_context(self):

        self.context.clear()