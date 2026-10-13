"""Bounded chat context with an explicit, compact recap of older USER turns.

Unlike project memory, this summary is temporary and exists only in RAM.
"""
from core.knowledge import redact


class ContextManager:
    def __init__(self, max_messages=14, max_chars=14000, summary_chars=1600):
        self.messages = []
        self.summary = ''
        self.max_messages = max_messages
        self.max_chars = max_chars
        self.summary_chars = summary_chars

    def _append(self, role, content):
        content = str(content)
        if len(content) > self.max_chars:
            content = content[:self.max_chars - 50] + '\n[entrada longa truncada]'
        self.messages.append({'role': role, 'content': content})
        while (len(self.messages) > self.max_messages or
               sum(len(m['content']) for m in self.messages) > self.max_chars):
            oldest = self.messages.pop(0)
            # Preserve only a brief reminder of earlier user requests, not
            # assistant conclusions that might have been unverified.
            if oldest['role'] == 'user':
                snippet = redact(oldest['content'].replace('\n', ' '))[:180]
                self.summary = (self.summary + '\n- ' + snippet)[-self.summary_chars:]

    def add_user_message(self, content: str):
        self._append('user', content)

    def add_assistant_message(self, content: str):
        self._append('assistant', content)

    def get_messages(self):
        result = []
        if self.summary:
            result.append({'role': 'system', 'content':
                           'RESUMO PARCIAL DE PEDIDOS ANTERIORES DO USUÁRIO (não são fatos verificados):\n'
                           + self.summary})
        return result + self.messages.copy()

    def status(self):
        return {'recent_messages': len(self.messages), 'recent_chars': sum(
                len(m['content']) for m in self.messages), 'summary_chars': len(self.summary)}

    def clear(self):
        self.messages.clear()
        self.summary = ''
