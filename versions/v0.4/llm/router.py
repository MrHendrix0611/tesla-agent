import os

from dotenv import load_dotenv

from llm.base import LLMProvider
from llm.providers.openrouter import OpenRouterProvider
from llm.providers.ollama import OllamaProvider


load_dotenv()


class LLMRouter:

    def __init__(self):

        provider_name = os.getenv(
            "LLM_PROVIDER",
            "openrouter"
        ).lower()

        if provider_name == "openrouter":

            self.provider: LLMProvider = OpenRouterProvider()

        elif provider_name == "ollama":

            self.provider: LLMProvider = OllamaProvider()

        else:

            raise ValueError(
                f"Provider não suportado: {provider_name}"
            )

    def generate(self, messages: list[dict]) -> str:

        return self.provider.generate(messages)