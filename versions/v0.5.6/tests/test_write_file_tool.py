import tempfile
import unittest
from pathlib import Path
from tools.registry import ToolRegistry
from core.permission_manager import PermissionManager

class WriteFileToolTests(unittest.TestCase):
    def test_tool_advertised_and_requires_confirmation(self):
        registry = ToolRegistry()
        names = [t["function"]["name"] for t in registry.get_tool_definitions()]
        self.assertIn("write_file", names)
        self.assertEqual(PermissionManager().get_status("write_file"), "confirmation_required")

    def test_write_file_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "teste.py"
            result = ToolRegistry().execute("write_file", {"path": str(target), "content": 'print("Olá, Tesla!")\n'})
            self.assertIn("Arquivo criado", result)
            self.assertEqual(target.read_text(encoding="utf-8"), 'print("Olá, Tesla!")\n')

if __name__ == "__main__":
    unittest.main()
