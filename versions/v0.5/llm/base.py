from abc import ABC, abstractmethod


class LLMProvider(ABC):

    @abstractmethod
    def generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None
    ) -> dict:
        pass