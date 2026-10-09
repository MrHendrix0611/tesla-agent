import json
import tempfile
import unittest
from pathlib import Path
from llm.observability import AuditLog, usage_report
from llm.intelligence import UsageTracker

class ObservabilityTests(unittest.TestCase):
    def test_audit_redacts_sensitive_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            audit = AuditLog(Path(folder) / 'audit.jsonl')
            audit.record('test', provider='groq', api_key='sensitive', prompt='private', model='test-model')
            event = audit.recent()[0]
            self.assertEqual(event['provider'], 'groq')
            self.assertNotIn('api_key', event)
            self.assertNotIn('prompt', event)

    def test_report_counts_failures(self):
        with tempfile.TemporaryDirectory() as folder:
            tracker = UsageTracker(Path(folder) / 'usage.jsonl')
            tracker.record(provider='groq', status='error', error='RateLimitError')
            tracker.record(provider='gemini', status='ok', input_tokens=7, output_tokens=3)
            report = usage_report(tracker)
            self.assertEqual(report['total_failures'], 1)
            self.assertEqual(report['total_successes'], 1)
            self.assertEqual(report['errors_by_provider']['groq'], 1)

if __name__ == '__main__':
    unittest.main()
