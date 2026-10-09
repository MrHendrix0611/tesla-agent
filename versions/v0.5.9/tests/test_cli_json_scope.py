"""Regression for the local `import json` shadowing bug in CLI main()."""
import ast
from pathlib import Path
import unittest


class JsonScopeTests(unittest.TestCase):
    def test_main_uses_module_level_json_without_local_binding(self):
        source = Path(__file__).resolve().parents[1] / 'cli' / 'main.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        imports = [n for n in tree.body if isinstance(n, ast.Import)]
        self.assertTrue(any(a.name == 'json' for node in imports for a in node.names))
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
        self.assertFalse(any(isinstance(n, (ast.Import, ast.ImportFrom)) and (
            (isinstance(n, ast.Import) and any(a.name == 'json' for a in n.names)) or
            (isinstance(n, ast.ImportFrom) and n.module == 'json')
        ) for n in ast.walk(main)))


if __name__ == '__main__':
    unittest.main()
