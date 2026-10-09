"""Safe, bounded, read-only repository intelligence for Tesla."""
from pathlib import Path
import fnmatch
import os
import re

EXCLUDED = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', 'dist', 'build', '.next', '.idea', '.vscode', 'coverage', '.pytest_cache', 'data'}
SECRET_NAMES = {'.env', '.npmrc', '.pypirc', 'id_rsa', 'id_ed25519', 'credentials.json', 'secrets.json'}
SECRET_SUFFIXES = ('.pem', '.key', '.p12', '.pfx', '.sqlite', '.db', '.zip', '.pdf', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.exe', '.dll', '.bin', '.pyc', '.lock')
LANGUAGES = {'.py':'Python', '.js':'JavaScript', '.jsx':'JavaScript', '.ts':'TypeScript', '.tsx':'TypeScript', '.php':'PHP', '.cs':'C#', '.java':'Java', '.go':'Go', '.rs':'Rust', '.html':'HTML', '.css':'CSS', '.sql':'SQL', '.sh':'Shell', '.ps1':'PowerShell'}
MARKERS = {'package.json':'Node.js', 'pyproject.toml':'Python project', 'requirements.txt':'Python dependencies', 'composer.json':'Composer/PHP', 'Cargo.toml':'Rust/Cargo', 'go.mod':'Go modules', 'pom.xml':'Maven', 'Dockerfile':'Docker', 'manage.py':'Django', 'angular.json':'Angular', 'next.config.js':'Next.js', 'next.config.mjs':'Next.js', 'vite.config.ts':'Vite', 'vite.config.js':'Vite'}

class RepositoryIntelligence:
    def __init__(self, root='.', max_files=1500, max_bytes=262144):
        self.root = Path(root).expanduser().resolve(strict=True)
        if not self.root.is_dir(): raise ValueError('Projeto precisa ser um diretório')
        self.max_files = max_files
        self.max_bytes = max_bytes
        self.patterns = self._load_ignore()

    def _load_ignore(self):
        ignore = self.root / '.gitignore'
        if not ignore.is_file(): return []
        return [s.strip() for s in ignore.read_text(encoding='utf-8',errors='replace').splitlines() if s.strip() and not s.lstrip().startswith('#') and not s.startswith('!')]

    def _excluded(self, relative, is_dir=False):
        p = Path(relative)
        if any(part in EXCLUDED for part in p.parts): return True
        if p.name.startswith('.') or p.name in SECRET_NAMES or p.name.startswith('.env.') or p.suffix.lower() in SECRET_SUFFIXES: return True
        value = p.as_posix()
        for pat in self.patterns:
            pat = pat.lstrip('/')
            if fnmatch.fnmatch(value, pat) or fnmatch.fnmatch(p.name,pat) or (pat.endswith('/') and (value.startswith(pat) or ('/'+pat) in value)):
                return True
        return False

    def files(self):
        result=[]
        for current, dirs, files in os.walk(self.root, followlinks=False):
            base=Path(current)
            dirs[:] = sorted(d for d in dirs if not (base/d).is_symlink() and not self._excluded((base/d).relative_to(self.root), True))
            for name in sorted(files):
                p=base/name
                if p.is_symlink() or self._excluded(p.relative_to(self.root)): continue
                try:
                    if not p.is_file() or p.stat().st_size > self.max_bytes: continue
                except OSError: continue
                result.append(p)
                if len(result)>=self.max_files: return result
        return result

    def summary(self):
        files=self.files(); languages={}; technologies=set(); listing=[]
        for p in files:
            rel=p.relative_to(self.root).as_posix(); listing.append(rel)
            if p.suffix.lower() in LANGUAGES:
                lang=LANGUAGES[p.suffix.lower()]; languages[lang]=languages.get(lang,0)+1
            if p.name in MARKERS: technologies.add(MARKERS[p.name])
        # Manifest presence only; no dependency file content is transmitted.
        return {'root':str(self.root),'files_indexed':len(files),'truncated':len(files)>=self.max_files,'languages':dict(sorted(languages.items(),key=lambda x:-x[1])),'technologies':sorted(technologies),'files':listing[:200], 'files_list_truncated':len(listing)>200}

    def search(self, query, limit=20):
        if not query or len(query)>160: raise ValueError('Consulta inválida (1 a 160 caracteres)')
        results=[]
        for p in self.files():
            try:
                with p.open('r',encoding='utf-8') as stream:
                    for n,line in enumerate(stream,1):
                        if n>3000: break
                        if query.casefold() in line.casefold():
                            results.append({'file':p.relative_to(self.root).as_posix(),'line':n,'preview':line.strip()[:180]})
                            if len(results)>=limit: return results
            except (UnicodeError, OSError): continue
        return results

    def symbols(self, query='', limit=50):
        patterns=[re.compile(r'^\s*(?:async\s+)?(?:def|class)\s+([A-Za-z_]\w*)'),re.compile(r'^\s*(?:export\s+)?(?:async\s+)?(?:function|class|interface|type)\s+([A-Za-z_$][\w$]*)'),re.compile(r'^\s*(?:public|private|protected|static|async|export|abstract|internal|sealed|partial|\s)*\s*(?:class|interface|struct)\s+([A-Za-z_]\w*)')]
        results=[]
        for p in self.files():
            if p.suffix.lower() not in {'.py','.js','.jsx','.ts','.tsx','.cs','.java','.php'}: continue
            try:
                with p.open('r',encoding='utf-8') as stream:
                    for n,line in enumerate(stream,1):
                        if n>3000: break
                        for pattern in patterns:
                            match=pattern.search(line)
                            if match and query.casefold() in match.group(1).casefold():
                                results.append({'name':match.group(1),'file':p.relative_to(self.root).as_posix(),'line':n})
                                if len(results)>=limit: return results
                                break
            except (UnicodeError,OSError): continue
        return results
