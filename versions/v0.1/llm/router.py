from llm.base import LLMProvider
from llm.providers.openrouter import OpenRouterProvider


class LLMRouter:

    def __init__(self):
        self.provider: LLMProvider = OpenRouterProvider()

    def generate(self, prompt: str) -> str:
        return self.provider.generate(prompt)