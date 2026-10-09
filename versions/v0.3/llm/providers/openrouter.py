import os

from dotenv import load_dotenv
from openai import OpenAI

from llm.base import LLMProvider


load_dotenv()


class OpenRouterProvider(LLMProvider):

    def __init__(self):

        api_key = os.getenv("OPENROUTER_API_KEY")

        if not api_key:
            raise ValueError(
                "OPENROUTER_API_KEY não encontrada no arquivo .env"
            )

        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )

        self.model = "openrouter/free"

    def generate(self, messages: list[dict]) -> str:

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )

        return response.choices[0].message.content