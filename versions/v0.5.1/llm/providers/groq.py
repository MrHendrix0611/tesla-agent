import os
from openai import OpenAI
from llm.base import LLMProvider

class GroqProvider(LLMProvider):
    def __init__(self):
        key = os.getenv('GROQ_API_KEY')
        if not key: raise ValueError('GROQ_API_KEY não configurada')
        self.model = os.getenv('GROQ_MODEL', 'openai/gpt-oss-20b')
        self.client = OpenAI(api_key=key, base_url='https://api.groq.com/openai/v1', timeout=45.0, max_retries=0)

    def generate(self, messages, tools=None):
        kwargs = {'model': self.model, 'messages': messages}
        if tools: kwargs['tools'] = tools
        r = self.client.chat.completions.create(**kwargs)
        m = r.choices[0].message
        return {'content': m.content or '', 'tool_calls': [
            {'id': c.id, 'name': c.function.name, 'arguments': c.function.arguments}
            for c in (m.tool_calls or [])]}
