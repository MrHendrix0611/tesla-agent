import os
import tempfile
import unittest
from unittest.mock import patch
from llm.intelligence import ModelSelector, ProviderHealth, UsageTracker, BudgetGuard, QuotaManager
from llm.router import LLMRouter

class Dummy:
    def __init__(self, model, fail=False):
        self.model = model
        self.fail = fail
        self.calls = 0
    def generate(self, messages, tools=None):
        self.calls += 1
        if self.fail:
            from openai import APITimeoutError
            raise APITimeoutError(request=__import__('httpx').Request('POST', 'https://example.com'))
        return {'content': 'ok', 'tool_calls': [], 'input_tokens': 10, 'output_tokens': 20}

class Tests(unittest.TestCase):
    def test_classification(self):
        self.assertEqual(ModelSelector().classify([{'role':'user','content':'corrija bug python'}]), 'coding')
        self.assertEqual(ModelSelector().classify([{'role':'user','content':'arquitetura escalável'}]), 'architecture')
    def test_usage_and_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracker = UsageTracker(tmp+'/usage.jsonl')
            tracker.record(provider='openrouter', cost_usd=1.25, input_tokens=10, output_tokens=20)
            self.assertEqual(tracker.summary()['month_paid_usd'], 1.25)
            with patch.dict(os.environ, {'PAID_FALLBACK_ENABLED':'true','PAID_USAGE_MODE':'auto','MONTHLY_PAID_BUDGET_USD':'2'}):
                self.assertTrue(BudgetGuard(tracker).paid_allowed(.5))
                self.assertFalse(BudgetGuard(tracker).paid_allowed(1))
    def test_selection_and_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {'USAGE_LOG_PATH':tmp+'/usage.jsonl'}):
                r = LLMRouter.__new__(LLMRouter)
                r.providers = [('groq',Dummy('free',True)),('gemini',Dummy('free'))]
                r.auto = True
                r.selector = ModelSelector(); r.health = ProviderHealth()
                r.usage = UsageTracker(); r.quotas = QuotaManager(r.usage)
                r.budget = BudgetGuard(r.usage); r.last_decision = None
                from llm.observability import AuditLog
                r.audit = AuditLog(tmp + "/audit.jsonl")
                result = r.generate([{'role':'user','content':'corrija bug python'}])
                self.assertEqual(result['content'], 'ok')
                self.assertEqual(r.last_decision['provider'], 'gemini')
                self.assertEqual(r.usage.summary()['today_calls'], 2)
    def test_paid_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {'USAGE_LOG_PATH':tmp+'/usage.jsonl','PAID_FALLBACK_ENABLED':'false'}):
                r = LLMRouter.__new__(LLMRouter)
                paid = Dummy('some-paid-model')
                r.providers=[('openrouter',paid)]; r.auto=True
                r.selector=ModelSelector(); r.health=ProviderHealth(); r.usage=UsageTracker()
                r.quotas=QuotaManager(r.usage); r.budget=BudgetGuard(r.usage); r.last_decision=None
                from llm.observability import AuditLog
                r.audit = AuditLog(tmp + "/audit.jsonl")
                with self.assertRaises(RuntimeError): r.generate([{'role':'user','content':'oi'}])
                self.assertEqual(paid.calls,0)

if __name__ == '__main__': unittest.main()
