import unittest
from unittest.mock import patch
from llm.router import LLMRouter

class FakeProvider:
    def __init__(self, result=None, error=None): self.result, self.error = result, error
    def generate(self, messages, tools=None):
        if self.error: raise self.error
        return self.result

class TestSmartRouter(unittest.TestCase):
    def test_returns_first_success(self):
        r = LLMRouter.__new__(LLMRouter)
        r.providers = [('a', FakeProvider({'content':'ok','tool_calls':[]}))]
        self.assertEqual(r.generate([{'role':'user','content':'oi'}])['content'], 'ok')
    def test_does_not_hide_invalid_request(self):
        r = LLMRouter.__new__(LLMRouter)
        r.providers = [('a', FakeProvider(error=ValueError('invalid'))), ('b', FakeProvider({'content':'ok'}))]
        with self.assertRaises(ValueError): r.generate([])

if __name__ == '__main__': unittest.main()
