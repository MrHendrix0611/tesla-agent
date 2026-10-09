"""Task-aware routing, health, quotas and local usage accounting."""
import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path


def flag(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in ('1', 'true', 'yes', 'sim')


def number(name, default):
    try:
        return max(0.0, float(os.getenv(name, default)))
    except (TypeError, ValueError):
        return float(default)


class ModelSelector:
    KEYWORDS = {
        'coding': ('python', 'javascript', 'código', 'codigo', 'program', 'bug', 'erro', 'refator', 'função', 'funcao', 'api', 'script', 'classe', 'git', 'sql'),
        'architecture': ('arquitetura', 'escalab', 'infraestrutura', 'microsserv', 'design pattern', 'adr', 'requisitos'),
        'analysis': ('analis', 'planilha', 'dados', 'csv', 'excel', 'estatíst', 'estatist', 'relatório', 'relatorio'),
    }

    def classify(self, messages, task_hint=None):
        if task_hint in self.KEYWORDS or task_hint == 'general':
            return task_hint
        # Prefer the latest user request; never classify based on the system prompt.
        last = next((str(m.get('content') or '') for m in reversed(messages) if m.get('role') == 'user'), '')
        lowered = last.lower()
        counts = {category: sum(word in lowered for word in words) for category, words in self.KEYWORDS.items()}
        category = max(counts, key=counts.get)
        return category if counts[category] else 'general'

    def score(self, name, task, free=True):
        preference = {
            'coding': {'groq': 90, 'gemini': 85, 'openrouter': 80},
            'architecture': {'gemini': 95, 'groq': 85, 'openrouter': 80},
            'analysis': {'gemini': 95, 'groq': 85, 'openrouter': 80},
            'general': {'groq': 95, 'gemini': 90, 'openrouter': 85},
        }
        return preference.get(task, preference['general']).get(name, 50) + (10 if free else -100)


class ProviderHealth:
    def __init__(self):
        self.until = {}
        self.failures = {}

    def available(self, name):
        return time.monotonic() >= self.until.get(name, 0)

    def fail(self, name, rate_limited=False):
        n = self.failures.get(name, 0) + 1
        self.failures[name] = n
        base = number('RATE_LIMIT_COOLDOWN_SECONDS', 120) if rate_limited else number('PROVIDER_COOLDOWN_SECONDS', 15)
        self.until[name] = time.monotonic() + min(base * (2 ** min(n - 1, 4)), 3600)

    def success(self, name):
        self.failures.pop(name, None)
        self.until.pop(name, None)


class UsageTracker:
    def __init__(self, path=None):
        self.path = Path(path or os.getenv('USAGE_LOG_PATH', 'data/usage.jsonl'))
        self.lock = threading.Lock()

    def record(self, **event):
        event['timestamp'] = datetime.now(timezone.utc).isoformat()
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(event, ensure_ascii=False) + '\n')

    def events(self):
        if not self.path.exists():
            return []
        with self.lock:
            with self.path.open(encoding='utf-8') as stream:
                result = []
                for line in stream:
                    try:
                        result.append(json.loads(line))
                    except (ValueError, TypeError):
                        continue
                return result

    def summary(self):
        now = datetime.now(timezone.utc)
        events = self.events()
        today = [e for e in events if e.get('timestamp', '')[:10] == now.date().isoformat()]
        month = [e for e in events if e.get('timestamp', '')[:7] == now.strftime('%Y-%m')]
        return {'today_calls': len(today), 'month_calls': len(month),
                'month_paid_usd': round(sum(float(e.get('cost_usd') or 0) for e in month), 6),
                'month_input_tokens': sum(int(e.get('input_tokens') or 0) for e in month),
                'month_output_tokens': sum(int(e.get('output_tokens') or 0) for e in month),
                'by_provider': {name: sum(e.get('provider') == name for e in month) for name in sorted(set(e.get('provider') for e in month))}}


class BudgetGuard:
    def __init__(self, tracker):
        self.tracker = tracker

    def paid_allowed(self, estimated_cost):
        if not flag('PAID_FALLBACK_ENABLED'):
            return False
        ceiling = number('MONTHLY_PAID_BUDGET_USD', 0)
        return ceiling > 0 and estimated_cost > 0 and self.tracker.summary()['month_paid_usd'] + estimated_cost <= ceiling


class QuotaManager:
    def __init__(self, tracker):
        self.tracker = tracker

    def available(self, name):
        # Only enforce explicit local per-provider ceilings; provider quotas vary by account/model.
        cap = int(number('MAX_DAILY_' + name.upper() + '_CALLS', 0))
        if not cap:
            return True
        today = datetime.now(timezone.utc).date().isoformat()
        return sum(e.get('provider') == name and e.get('timestamp', '').startswith(today) for e in self.tracker.events()) < cap
