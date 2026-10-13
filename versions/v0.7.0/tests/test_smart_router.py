"""Legacy compatibility tests replaced by test_intelligence.py in V0.5.2."""
import unittest
from llm.intelligence import ModelSelector

class TestSmartRouterCompatibility(unittest.TestCase):
    def test_general_task(self):
        self.assertEqual(ModelSelector().classify([{'role': 'user', 'content': 'Olá'}]), 'general')
