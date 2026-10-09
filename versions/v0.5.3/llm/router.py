import logging
import os
from dotenv import load_dotenv
from openai import APIConnectionError, APITimeoutError, RateLimitError, InternalServerError, APIStatusError
from llm.providers.openrouter import OpenRouterProvider
from llm.providers.ollama import OllamaProvider
from llm.providers.groq import GroqProvider
from llm.providers.gemini import GeminiProvider
from llm.intelligence import ModelSelector, ProviderHealth, UsageTracker, BudgetGuard, QuotaManager, flag, number

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
            if flag('ENABLE_OLLAMA_FALLBACK'):
                names.append('ollama')
            names = list(dict.fromkeys(names))
        else:
            names = [selected]
        unknown = [n for n in names if n not in FACTORIES]
        if unknown:
            raise ValueError(f'Providers desconhecidos: {unknown}')
        names = [n for n in names if n == 'ollama' or os.getenv(KEYS[n], '').strip()]
        if not names:
            raise ValueError('Nenhum provider configurado. Configure as chaves no .env.')
        self.providers = [(name, FACTORIES[name]()) for name in names]
        self.provider = self.providers[0][1]
        self.auto = selected == 'auto'
        self.selector = ModelSelector()
        self.health = ProviderHealth()
        self.usage = UsageTracker()
        self.budget = BudgetGuard(self.usage)
        self.quotas = QuotaManager(self.usage)
        self.last_decision = None
        self.paid_approval_callback = None  # CLI installs an interactive callback.


    def _is_free(self, name, provider):
        if name in ('groq', 'gemini', 'ollama'):
            # Groq/Gemini can be billed depending on the account; only run under explicit free-tier assumption.
            return True
        model = provider.model.lower()
        return model == 'openrouter/free' or model.endswith(':free')

    def _estimated_cost(self, name, provider, messages):
        # Conservative preflight estimation; explicit USD/M-token rates required for paid models.
        prefix = name.upper()
        in_rate = number(prefix + '_INPUT_USD_PER_M', 0)
        out_rate = number(prefix + '_OUTPUT_USD_PER_M', 0)
        if not in_rate or not out_rate:
            return None
        approx_input = max(1000, sum(len(str(m.get('content') or '')) for m in messages) // 3)
        reserved_output = int(number('PAID_RESERVED_OUTPUT_TOKENS', 4096))
        return (approx_input * in_rate + reserved_output * out_rate) / 1_000_000

    def generate(self, messages: list[dict], tools: list[dict] | None = None, task_hint=None) -> dict:
        task = self.selector.classify(messages, task_hint)
        candidates = list(self.providers)
        if self.auto:
            candidates.sort(key=lambda pair: self.selector.score(pair[0], task, self._is_free(*pair)), reverse=True)
        failures = []
        for name, provider in candidates:
            if not self.health.available(name) or not self.quotas.available(name):
                failures.append(f'{name}: cooldown ou limite local')
                continue
            free = self._is_free(name, provider)
            estimated = 0.0 if free else self._estimated_cost(name, provider, messages)
            if not free:
                if estimated is None or not self.budget.paid_allowed(estimated):
                    failures.append(f'{name}: modelo pago bloqueado (modo/orçamento/preço)')
                    continue
                if self.budget.mode() == 'ask':
                    if not callable(self.paid_approval_callback):
                        failures.append(f'{name}: aprovação interativa indisponível; chamada bloqueada')
                        continue
                    remaining = self.budget.remaining()
                    request = {'provider': name, 'model': provider.model, 'task': task,
                               'estimated_usd': estimated, 'remaining_usd': remaining}
                    try:
                        approved = self.paid_approval_callback(request) is True
                    except (EOFError, KeyboardInterrupt):
                        approved = False
                    if not approved:
                        failures.append(f'{name}: uso pago não autorizado')
                        continue
            try:
                log.info('Tarefa=%s, provider=%s, modelo=%s', task, name, provider.model)
                result = provider.generate(messages, tools)
                self.health.success(name)
                tokens_in = int(result.get('input_tokens') or 0)
                tokens_out = int(result.get('output_tokens') or 0)
                cost = 0.0 if free else (tokens_in * number(name.upper()+'_INPUT_USD_PER_M', 0) + tokens_out * number(name.upper()+'_OUTPUT_USD_PER_M', 0)) / 1_000_000
                self.usage.record(provider=name, model=provider.model, task=task, status='ok', free=free, input_tokens=tokens_in, output_tokens=tokens_out, cost_usd=cost)
                self.last_decision = {'provider': name, 'model': provider.model, 'task': task, 'free': free}
                return result
            except RETRYABLE as exc:
                self.health.fail(name, isinstance(exc, RateLimitError))
                failures.append(f'{name}: {type(exc).__name__}')
                self.usage.record(provider=name, model=provider.model, task=task, status='error', error=type(exc).__name__, cost_usd=0)
            except APIStatusError as exc:
                if exc.status_code in (408, 409, 425, 429) or exc.status_code >= 500:
                    self.health.fail(name, exc.status_code == 429)
                    failures.append(f'{name}: HTTP {exc.status_code}')
                    self.usage.record(provider=name, model=provider.model, task=task, status='error', error=f'HTTP {exc.status_code}', cost_usd=0)
                else:
                    raise
        raise RuntimeError('Nenhum modelo disponível: ' + '; '.join(failures))
