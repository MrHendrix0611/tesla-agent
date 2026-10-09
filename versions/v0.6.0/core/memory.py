"""Explicit, project-scoped decisions memory. Never save prompts automatically."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import re
from uuid import uuid4

from core.knowledge import _atomic_json, SECRET_LINE, words


class ProjectMemory:
    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError('Projeto inexistente')
        self.path = self.root / '.tesla' / 'memory.json'

    def _load(self) -> list[dict]:
        if self.path.parent.is_symlink():
            raise PermissionError('Diretório de memória não pode ser link simbólico')
        if not self.path.exists():
            return []
        if self.path.is_symlink():
            raise PermissionError('Memória não pode ser link simbólico')
        try:
            payload = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise ValueError('Arquivo de memória inválido; faça backup e verifique-o') from exc
        if (not isinstance(payload, dict) or payload.get('version') != 1 or
                not isinstance(payload.get('notes'), list)):
            raise ValueError('Formato de memória inválido')
        return payload['notes']

    def list(self) -> list[dict]:
        return self._load()

    def add(self, text: str) -> dict:
        if not isinstance(text, str):
            raise ValueError('Nota precisa ser texto')
        text = text.strip()
        if not 3 <= len(text) <= 1000:
            raise ValueError('Nota deve conter de 3 a 1000 caracteres')
        if SECRET_LINE.search(text) or re.search(r'(?i)\b(?:api[_-]?key|token|senha|password|segredo)\b', text):
            raise ValueError('Não salve chaves, senhas ou tokens na memória')
        notes = self._load()
        if len(notes) >= 100:
            raise ValueError('Limite de 100 memórias por projeto')
        note = {'id': uuid4().hex[:10], 'text': text,
                'created_at': datetime.now(timezone.utc).isoformat()}
        notes.append(note)
        _atomic_json(self.path, {'version': 1, 'notes': notes})
        return note

    def forget(self, note_id: str) -> bool:
        notes = self._load()
        kept = [note for note in notes if note['id'] != note_id]
        if len(kept) == len(notes):
            return False
        _atomic_json(self.path, {'version': 1, 'notes': kept})
        return True

    def recall(self, query: str, limit: int = 4) -> list[dict]:
        if not query.strip():
            return []
        query_words = set(words(query))
        if not query_words:
            return []
        scored = []
        for note in self._load():
            notes_words = set(words(note['text']))
            overlap = len(query_words & notes_words)
            if overlap:
                scored.append((overlap / max(len(query_words), 1), overlap, note))
        scored.sort(key=lambda row: (-row[0], -row[1], row[2]['id']))
        return [row[2] for row in scored[:max(1, min(int(limit), 10))]]
