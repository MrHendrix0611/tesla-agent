"""Real local MCP server E2E tests: no network, no tokens, no SDK."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

from core.permission_manager import PermissionManager
from tools.mcp import MCPManager, MCPError
from tools.registry import ToolRegistry


DEMO = Path(__file__).resolve().parent.parent / 'examples' / 'mcp_echo_server.py'


class MCPIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.conf_dir = self.root / '.tesla'
        self.conf_dir.mkdir()
        self.conf_file = self.conf_dir / 'mcp_servers.json'
        self.conf_file.write_text(json.dumps({'servers': {'demo': {
            'command': [sys.executable, '-u', str(DEMO)]
        }}}), encoding='utf-8')
        self.manager = MCPManager(self.root, timeout=5)
        self.addCleanup(self.manager.disconnect_all)

    def test_does_not_auto_start(self):
        self.assertFalse(self.manager.connections)
        self.assertEqual(self.manager.status(), [{'name': 'demo', 'connected': False, 'tools': 0}])

    def test_initialize_discover_and_execute(self):
        self.assertEqual(self.manager.connect('demo'), ['sum_numbers'])
        self.assertEqual(self.manager.status()[0]['tools'], 1)
        result = self.manager.invoke('mcp__demo__sum_numbers', {'a': 3, 'b': 4})
        self.assertEqual(json.loads(result)['content'][0]['text'], '7')

    def test_unknown_tool_cannot_be_called(self):
        self.manager.connect('demo')
        with self.assertRaises(ValueError):
            self.manager.invoke('mcp__demo__not_found', {})

    def test_disconnect_removes_tools(self):
        self.manager.connect('demo')
        self.assertTrue(self.manager.disconnect('demo'))
        self.assertEqual(self.manager.definitions(), [])
        with self.assertRaises(ValueError):
            self.manager.invoke('mcp__demo__sum_numbers', {'a': 1, 'b': 2})

    def test_invalid_server_config_fails_closed(self):
        self.conf_file.write_text('{"servers":{"bad name":{"command":["echo"]}}}', encoding='utf-8')
        with self.assertRaises(MCPError):
            self.manager.configured()

    def test_nonexistent_or_unconfigured_server_is_not_started(self):
        with self.assertRaises(ValueError):
            self.manager.connect('unknown')

    def test_mcp_calls_always_require_confirmation(self):
        self.assertEqual(PermissionManager().get_status('mcp__demo__sum_numbers'),
                         'confirmation_required')
        self.assertEqual(PermissionManager().get_status('mcp__unknown__something'),
                         'confirmation_required')

    def test_registry_scopes_tools_to_project_and_disconnects_on_switch(self):
        registry = ToolRegistry()
        registry.set_workspace(self.root)
        with self.assertRaises(ValueError):
            registry.execute('mcp__demo__sum_numbers', {'a': 1, 'b': 2})
        registry.mcp.connect('demo')
        defs = registry.get_tool_definitions()
        self.assertIn('mcp__demo__sum_numbers', [d['function']['name'] for d in defs])
        result = registry.execute('mcp__demo__sum_numbers', {'a': 8, 'b': 5})
        self.assertEqual(json.loads(result)['content'][0]['text'], '13')
        other = self.root / 'other'
        other.mkdir()
        registry.set_workspace(other)
        self.assertEqual(registry.mcp.definitions(), [])
        self.assertEqual(registry.get_workspace(), other.resolve())

    def test_mcp_argument_limits(self):
        self.manager.connect('demo')
        with self.assertRaises(ValueError):
            self.manager.invoke('mcp__demo__sum_numbers', {'a': 'x'*33000})

    def test_server_rpc_error_is_not_success(self):
        self.manager.connect('demo')
        with self.assertRaises(MCPError):
            self.manager.invoke('mcp__demo__sum_numbers', {'a': 'abc', 'b': 2})


if __name__ == '__main__':
    unittest.main()
