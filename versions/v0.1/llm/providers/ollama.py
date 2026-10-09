import requests

from llm.base import LLM


class OllamaProvider(LLM):

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434"
    ):
        self.model = model
        self.base_url = base_url

    def chat(self, messages: list[dict]) -> str:

        response = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": messages,
                "stream": False
            },
            timeout=120
        )

        response.raise_for_status()

        data = response.json()

        return data["message"]["content"]