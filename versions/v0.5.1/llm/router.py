import os
import logging
from dotenv import load_dotenv
from openai import APIConnectionError, APITimeoutError, RateLimitError, InternalServerError, APIStatusError
from llm.base import LLMProvider
from llm.providers.openrouter import OpenRouterProvider
from llm.providers.ollama import OllamaProvider
from llm.providers.groq import GroqProvider
from llm.providers.gemini import GeminiProvider

load_dotenv()
log = logging.getLogger('hefesto.router')
FACTORIES = {'groq': GroqProvider, 'gemini': GeminiProvider, 'openrouter': OpenRouterProvider, 'ollama': OllamaProvider}
KEYS = {'groq': 'GROQ_API_KEY', 'gemini': 'GEMINI_API_KEY', 'openrouter': 'OPENROUTER_API_KEY'}
RETRYABLE = (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError)

class LLMRouter:
    def __init__(self):
        selected = os.getenv('LLM_PROVIDER', 'auto').strip().lower()
        if selected == 'auto':
            names = [n.strip().lower() for n in os.getenv('LLM_FALLBACK_ORDER', 'groq,gemini,openrouter').split(',') if n.strip()]
            if os.getenv('ENABLE_OLLAMA_FALLBACK', 'false').lower() == 'true': names.append('ollama')
            names = list(dict.fromkeys(names))
            names = [n for n in names if n == 'ollama' or os.getenv(KEYS.get(n, ''), '').strip()]
        else:
            names = [selected]
        if not names: raise ValueError('Nenhum provider configurado. Configure as chaves no .env.')
        unknown = [n for n in names if n not in FACTORIES]
        if unknown: raise ValueError(f'Providers desconhecidos: {unknown}')
        self.providers = [(name, FACTORIES[name]()) for name in names]
        self.provider = self.providers[0][1]  # compatibilidade com a V0.5

    def generate(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        failures = []
        for name, provider in self.providers:
            try:
                log.info('Tentando provider %s, modelo %s', name, getattr(provider, 'model', '?'))
                result = provider.generate(messages, tools)
                log.info('Resposta de %s', name)
                return result
            except RETRYABLE as exc:
                failures.append(f'{name}: {type(exc).__name__}')
                log.warning('Falha recuperável em %s: %s', name, type(exc).__name__)
            except APIStatusError as exc:
                if exc.status_code in (408, 409, 425, 429) or exc.status_code >= 500:
                    failures.append(f'{name}: HTTP {exc.status_code}')
                    log.warning('Falha HTTP %s em %s', exc.status_code, name)
                else:
                    raise  # autenticação, modelo inválido, payload/tools incompatíveis: corrigir em vez de ocultar
        raise RuntimeError('Todos os providers falharam: ' + '; '.join(failures))
