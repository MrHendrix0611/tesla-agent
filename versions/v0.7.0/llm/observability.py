"""Privacy-conscious local structured audit events and reporting."""
import json
import logging
import os
import threading
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SENSITIVE = ('api_key', 'authorization', 'token', 'password', 'secret', 'messages', 'prompt', 'content', 'arguments')

class AuditLog:
    def __init__(self, path=None):
        self.path = Path(path or os.getenv('AUDIT_LOG_PATH', 'data/router_audit.jsonl'))
        self.lock = threading.Lock()

    def record(self, event, **fields):
        safe = {'timestamp': datetime.now(timezone.utc).isoformat(), 'event': event}
        for key, value in fields.items():
            if any(secret in key.lower() for secret in SENSITIVE):
                continue
            if value is None or isinstance(value, (str, int, float, bool)):
                safe[key] = value
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open('a', encoding='utf-8') as handle:
                handle.write(json.dumps(safe, ensure_ascii=False) + '\n')
        return safe

    def recent(self, limit=20):
        if not self.path.exists():
            return []
        from collections import deque
        with self.lock:
            with self.path.open(encoding='utf-8') as handle:
                lines = deque(handle, maxlen=max(1, min(int(limit), 500)))
        events = []
        for line in lines:
            try:
                events.append(json.loads(line))
            except (ValueError, TypeError):
                continue
        return events

def usage_report(tracker):
    summary = tracker.summary()
    events = tracker.events()
    successes = [e for e in events if e.get('status') == 'ok']
    failures = [e for e in events if e.get('status') == 'error']
    summary['total_successes'] = len(successes)
    summary['total_failures'] = len(failures)
    summary['errors_by_provider'] = dict(Counter(e.get('provider', 'unknown') for e in failures))
    summary['token_accounting'] = 'Tokens fornecidos pelas APIs quando disponíveis; zero não significa consumo zero.'
    summary['cost_accounting'] = 'Custos estimados localmente; consulte a fatura do provedor.'
    return summary

def new_request_id():
    return uuid.uuid4().hex[:12]
