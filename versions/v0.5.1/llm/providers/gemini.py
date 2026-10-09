import os
from openai import OpenAI
from llm.base import LLMProvider

class GeminiProvider(LLMProvider):
    def __init__(self):
        key = os.getenv('GEMINI_API_KEY')
        if not key: raise ValueError('GEMINI_API_KEY não configurada')
        self.model = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
        self.client = OpenAI(api_key=key, base_url='https://generativelanguage.googleapis.com/v1beta/openai/', timeout=60.0, max_retries=0)

    def generate(self, messages, tools=None):
        kwargs = {'model': self.model, 'messages': messages}
        if tools: kwargs['tools'] = tools
        r = self.client.chat.completions.create(**kwargs)
        m = r.choices[0].message
        return {'content': m.content or '', 'tool_calls': [
            {'id': c.id, 'name': c.function.name, 'arguments': c.function.arguments}
            for c in (m.tool_calls or [])]}
