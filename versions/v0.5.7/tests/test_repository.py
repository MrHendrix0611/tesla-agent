import tempfile
import unittest
from pathlib import Path
from tools.repository import RepositoryIntelligence
from tools.registry import ToolRegistry

class RepositoryTests(unittest.TestCase):
    def test_map_search_symbols_and_exclusions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'main.py').write_text('def hello():\n    return "world"\n')
            (root/'.env').write_text('SECRET=supersecret')
            (root/'.gitignore').write_text('ignored.py\n')
            (root/'ignored.py').write_text('def hidden(): pass')
            (root/'node_modules').mkdir()
            (root/'node_modules'/'x.py').write_text('def vendor(): pass')
            r=RepositoryIntelligence(root)
            self.assertEqual(r.summary()['files_indexed'],1)
            self.assertEqual(r.search('world')[0]['line'],2)
            self.assertEqual(r.symbols('hello')[0]['name'],'hello')
            self.assertEqual(r.search('supersecret'),[])
            registry=ToolRegistry(); registry.set_repository(str(root))
            self.assertEqual(registry.execute('repository_symbols',{'query':'hello'})[0]['name'],'hello')

    def test_invalid_path(self):
        with self.assertRaises(FileNotFoundError): RepositoryIntelligence('/unlikely-tesla-repo-12345')

if __name__=='__main__': unittest.main()
