from core.context import ContextManager
from core.skill_manager import SkillManager
from llm.router import LLMRouter


class Agent:

    def __init__(self):
        self.llm = LLMRouter()
        self.context = ContextManager()
        self.skills = SkillManager()

        self.active_skill = None

        self.system_prompt = """
Você é Hefesto, um agente de inteligência artificial
especializado em ajudar o usuário.

Responda de forma clara, objetiva e útil.
"""

    def set_skill(self, skill_name):
        if not self.skills.skill_exists(skill_name):
            raise ValueError(
                f"Skill não encontrada: {skill_name}"
            )

        self.active_skill = skill_name

    def clear_skill(self):
        self.active_skill = None

    def get_active_skill(self):
        return self.active_skill

    def run(self, user_input: str) -> str:

        self.context.add_user_message(user_input)

        system_prompt = self.system_prompt

        if self.active_skill:
            skill_instructions = self.skills.load_skill(
                self.active_skill
            )

            system_prompt += f"""

Você está utilizando a seguinte Skill:

{skill_instructions}
"""

        messages = [
            {
                "role": "system",
                "content": system_prompt
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