import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from llm.intelligence import BudgetGuard, UsageTracker

class PaidModesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.guard = BudgetGuard(UsageTracker(self.tmp.name + '/usage.jsonl'))
    def tearDown(self):
        self.tmp.cleanup()
    def test_default_never(self):
        with patch.dict(os.environ, {'PAID_USAGE_MODE': 'never', 'MONTHLY_PAID_BUDGET_USD': '2'}):
            self.assertFalse(self.guard.paid_allowed(0.01))
    def test_ask_with_budget(self):
        with patch.dict(os.environ, {'PAID_USAGE_MODE': 'ask', 'MONTHLY_PAID_BUDGET_USD': '2'}):
            self.assertTrue(self.guard.paid_allowed(0.01))
            self.assertFalse(self.guard.paid_allowed(3))
    def test_invalid_mode_fails_closed(self):
        with patch.dict(os.environ, {'PAID_USAGE_MODE': 'anything', 'MONTHLY_PAID_BUDGET_USD': '2'}):
            self.assertFalse(self.guard.paid_allowed(0.01))
    def test_legacy_flag(self):
        with patch.dict(os.environ, {'PAID_FALLBACK_ENABLED': 'true', 'MONTHLY_PAID_BUDGET_USD': '2'}, clear=True):
            self.assertEqual(self.guard.mode(), 'auto')
    def test_ask_denied_no_api_call(self):
        from llm.router import LLMRouter
        with patch.dict(os.environ, {'PAID_USAGE_MODE':'ask','MONTHLY_PAID_BUDGET_USD':'2',
                                      'OPENROUTER_INPUT_USD_PER_M':'1', 'OPENROUTER_OUTPUT_USD_PER_M':'1'}):
            router = LLMRouter.__new__(LLMRouter)
            router.providers = [('openrouter', MagicMock(model='paid-model'))]
            router.auto = True
            from llm.intelligence import ModelSelector, ProviderHealth, QuotaManager
            router.selector = ModelSelector(); router.health = ProviderHealth()
            router.usage = self.guard.tracker; router.budget = self.guard
            router.quotas = QuotaManager(router.usage)
            router.last_decision = None
            from llm.observability import AuditLog
            router.audit = AuditLog(self.tmp.name + "/audit.jsonl")
            router.paid_approval_callback = lambda request: False
            with self.assertRaises(RuntimeError):
                router.generate([{'role':'user','content':'oi'}])
            router.providers[0][1].generate.assert_not_called()
    def test_ask_approved_calls_api(self):
        from llm.router import LLMRouter
        from llm.intelligence import ModelSelector, ProviderHealth, QuotaManager
        with patch.dict(os.environ, {'PAID_USAGE_MODE':'ask','MONTHLY_PAID_BUDGET_USD':'2',
                                      'OPENROUTER_INPUT_USD_PER_M':'1', 'OPENROUTER_OUTPUT_USD_PER_M':'1'}):
            router = LLMRouter.__new__(LLMRouter)
            mock = MagicMock(model='paid-model')
            mock.generate.return_value = {'content':'ok','input_tokens':100,'output_tokens':100}
            router.providers=[('openrouter',mock)]; router.auto=True
            router.selector=ModelSelector(); router.health=ProviderHealth()
            router.usage=self.guard.tracker; router.budget=self.guard
            router.quotas=QuotaManager(router.usage); router.last_decision=None
            from llm.observability import AuditLog
            router.audit = AuditLog(self.tmp.name + "/audit.jsonl")
            router.paid_approval_callback=lambda request: True
            self.assertEqual(router.generate([{'role':'user','content':'oi'}])['content'],'ok')
            mock.generate.assert_called_once()
