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

    def generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None
    ) -> dict:

        kwargs = {
            "model": self.model,
            "messages": messages
        }

        if tools:
            kwargs["tools"] = tools

        response = self.client.chat.completions.create(
            **kwargs
        )

        message = response.choices[0].message

        tool_calls = []

        if message.tool_calls:

            for tool_call in message.tool_calls:

                tool_calls.append({
                    "id": tool_call.id,
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments
                })

        return {
            "content": message.content or "",
            "tool_calls": tool_calls
        }