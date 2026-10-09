import os

from dotenv import load_dotenv
from openai import OpenAI

from llm.base import LLMProvider


load_dotenv()


class OllamaProvider(LLMProvider):

    def __init__(self):

        self.client = OpenAI(
            base_url="http://localhost:11434/v1",
            api_key="ollama",
        )

        self.model = os.getenv(
            "OLLAMA_MODEL",
            "qwen2.5-coder:3b"
        )

    def generate(self, prompt: str) -> str:

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        return response.choices[0].message.content