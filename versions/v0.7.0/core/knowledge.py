"""Private, project-scoped lexical RAG. No embedding API, database or extra pip dependency.

Index is bounded, ignores secrets and excluded repository paths, tracks file changes,
and stores a small excerpt per chunk. Source text is always untrusted data to an LLM.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import json
import math
import os
import re
import tempfile

from tools.repository import RepositoryIntelligence

INDEX_VERSION = 1
SOURCE_SUFFIXES = {'.py', '.js', '.jsx', '.ts', '.tsx', '.html', '.css', '.cs',
                   '.php', '.java', '.go', '.rs', '.sql', '.md', '.txt', '.yaml',
                   '.yml', '.json', '.toml', '.sh', '.ps1'}
STOPWORDS = {'de', 'do', 'da', 'dos', 'das', 'a', 'o', 'os', 'as', 'um', 'uma', 'para',
             'com', 'em', 'no', 'na', 'que', 'como', 'qual', 'quais', 'onde', 'me',
             'the', 'and', 'for', 'with', 'from', 'this', 'that', 'what', 'where',
             'please', 'arquivo', 'arquivos', 'project', 'projeto', 'código', 'codigo',
             'funcao', 'função', 'classe', 'teste', 'testes', 'sobre', 'explique'}
SECRET_LINE = re.compile(
    r'(?i)\b(?:api[_-]?key|access[_-]?token|secret|password|passwd|private[_-]?key|authorization)\b'
    r'\s*(?:=|:|=>)\s*[\"\']?[^\s\"\']{5,}'
    r'|\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9]{12,}|AIza[A-Za-z0-9_-]{16,})\b'
)


def redact(text: str) -> str:
    """Defence-in-depth; never a guarantee that a project contains no credentials."""
    return '\n'.join('[REDACTED: possible credential]' if SECRET_LINE.search(line)
                     else line for line in text.split('\n'))


def words(text: str) -> list[str]:
    parts = re.findall(r'[\w]+', text.casefold(), re.UNICODE)
    return [word for word in parts if len(word) >= 2 and word not in STOPWORDS][:2000]


def _atomic_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Do not follow symlinks in the private metadata directory.
    if path.parent.is_symlink() or path.is_symlink():
        raise PermissionError('Diretório/arquivo de memória não pode ser link simbólico')
    fd, temp_name = tempfile.mkstemp(prefix='.tesla_', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(obj, handle, ensure_ascii=False, separators=(',', ':'))
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


class ProjectKnowledgeIndex:
    def __init__(self, root: str | Path, max_files: int = 800, max_chunks: int = 3500):
        self.root = Path(root).expanduser().resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError('Projeto inexistente')
        self.index_path = self.root / '.tesla' / 'knowledge_index.json'
        self.max_files = max_files
        self.max_chunks = max_chunks
        self.repository = RepositoryIntelligence(self.root, max_files=max_files, max_bytes=256_000)
        self.data = self._load()

    def _load(self) -> dict:
        if self.index_path.parent.is_symlink():
            raise PermissionError('Diretório de índice não pode ser link simbólico')
        if not self.index_path.exists():
            return {'version': INDEX_VERSION, 'root': str(self.root), 'files': {}}
        if self.index_path.is_symlink():
            raise PermissionError('Índice não pode ser link simbólico')
        try:
            raw = json.loads(self.index_path.read_text(encoding='utf-8'))
            if (raw.get('version') == INDEX_VERSION and raw.get('root') == str(self.root)
                    and isinstance(raw.get('files'), dict)):
                return raw
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        return {'version': INDEX_VERSION, 'root': str(self.root), 'files': {}}

    def _chunks(self, text: str) -> list[dict]:
        text = redact(text)
        lines = text.splitlines()
        output = []
        start = 0
        while start < len(lines) and len(output) < 45:
            end = min(len(lines), start + 45)
            # Bound both line-count and character-count; never truncate a file secretly.
            while end > start + 1 and len('\n'.join(lines[start:end])) > 2400:
                end -= 1
            snippet = '\n'.join(lines[start:end])[:2400]
            if snippet.strip():
                output.append({'start': start + 1, 'end': end, 'text': snippet})
            if end >= len(lines):
                break
            start = max(start + 1, end - 5)
        return output

    def refresh(self) -> dict:
        available = {}
        chunks_total = 0
        indexed = 0
        unchanged = 0
        for path in self.repository.files():
            if path.suffix.lower() not in SOURCE_SUFFIXES:
                continue
            relative = path.relative_to(self.root).as_posix()
            try:
                stat = path.stat()
                if not path.is_file() or path.is_symlink():
                    continue
                prior = self.data['files'].get(relative)
                if (prior is not None and prior.get('mtime_ns') == stat.st_mtime_ns
                        and prior.get('size') == stat.st_size):
                    entry = prior
                    unchanged += 1
                else:
                    body = path.read_text(encoding='utf-8-sig')
                    if '\x00' in body:
                        continue
                    entry = {'mtime_ns': stat.st_mtime_ns, 'size': stat.st_size,
                             'chunks': self._chunks(body)}
                if chunks_total + len(entry['chunks']) > self.max_chunks:
                    break
                available[relative] = entry
                chunks_total += len(entry['chunks'])
                indexed += 1
            except (UnicodeError, OSError):
                continue
        changed = available != self.data['files']
        if changed:
            self.data = {'version': INDEX_VERSION, 'root': str(self.root), 'files': available,
                         'indexed_at': datetime.now(timezone.utc).isoformat()}
            _atomic_json(self.index_path, self.data)
        return {'root': str(self.root), 'files': indexed, 'chunks': chunks_total,
                'reused_files': unchanged, 'changed': changed}

    def stats(self) -> dict:
        return {'root': str(self.root), 'files': len(self.data['files']),
                'chunks': sum(len(f.get('chunks', [])) for f in self.data['files'].values()),
                'index_file': str(self.index_path), 'embedding_provider': 'none (lexical)'}

    def search(self, query: str, limit: int = 5, *, refresh: bool = True) -> list[dict]:
        if not isinstance(query, str) or not query.strip() or len(query) > 4000:
            raise ValueError('Consulta deve conter entre 1 e 4000 caracteres')
        if refresh:
            self.refresh()
        tokens = words(query)
        if not tokens:
            return []
        query_terms = set(tokens)
        documents = []
        frequencies = Counter()
        for filename, info in self.data['files'].items():
            for chunk in info['chunks']:
                terms = words(chunk['text']) + words(filename)
                counter = Counter(terms)
                documents.append((filename, chunk, counter, len(terms)))
                frequencies.update(counter.keys())
        if not documents:
            return []
        avglen = sum(item[3] for item in documents) / len(documents)
        scores = []
        for filename, chunk, counter, size in documents:
            score = 0.0
            for term in query_terms:
                tf = counter[term]
                if not tf:
                    continue
                idf = math.log(1 + (len(documents) - frequencies[term] + 0.5)
                               / (frequencies[term] + 0.5))
                score += idf * tf * 2.2 / (tf + 1.2 * (.25 + .75 * size / max(avglen, 1)))
                if term in words(filename):
                    score += 1.2
            if score > 0:
                scores.append((score, filename, chunk))
        scores.sort(key=lambda item: (-item[0], item[1], item[2]['start']))
        limit = min(max(1, int(limit)), 10)
        return [{'file': filename, 'start_line': chunk['start'], 'end_line': chunk['end'],
                 'snippet': chunk['text'][:2200], 'score': round(score, 3)}
                for score, filename, chunk in scores[:limit]]
