from __future__ import annotations

import re
import sqlite3
import threading
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from celine.config import CELINE_HOME, assert_celine_boundary

MEMORIES_DIR = CELINE_HOME / "memories"
USER_MD_PATH = MEMORIES_DIR / "USER.md"
MEMORY_MD_PATH = MEMORIES_DIR / "MEMORY.md"
DB_PATH = CELINE_HOME / "state.db"
_MEMORY_LOCK = threading.RLock()
_SECRET_PATTERNS = (
    re.compile(r"(?i)(?:api[_ -]?key|access[_ -]?token|refresh[_ -]?token|password|senha|secret|credential|authorization)\s*[:=]\s*\S+"),
    re.compile(r"(?i)\b(?:ghp_|gho_|ghu_|ghs_|ghr_|github_pat_|sk-)[A-Za-z0-9_\-]{12,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


def _validate_memory_text(value: str, *, field: str = "memória") -> str:
    clean = " ".join(value.split()).strip()
    if not clean:
        raise ValueError(f"{field} vazia.")
    if len(clean) > 1000:
        raise ValueError(f"{field} excede 1000 caracteres.")
    if any(pattern.search(clean) for pattern in _SECRET_PATTERNS):
        raise ValueError("Conteúdo com aparência de segredo não pode ser armazenado.")
    return clean


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    db = sqlite3.connect(DB_PATH, timeout=15)
    try:
        db.execute("PRAGMA busy_timeout = 15000")
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _atomic_private_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if os.name == "posix":
            temporary.chmod(0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class MemoryManager:
    def __init__(self) -> None:
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        assert_celine_boundary(CELINE_HOME)
        CELINE_HOME.mkdir(parents=True, exist_ok=True)
        MEMORIES_DIR.mkdir(parents=True, exist_ok=True)

        with _connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT DEFAULT 'general',
                    content TEXT UNIQUE,
                    created_at TEXT
                )
                """
            )
            # Automatic schema migration: ensure category column exists
            cur = db.execute("PRAGMA table_info(memories)")
            columns = [row[1] for row in cur.fetchall()]
            if "category" not in columns:
                try:
                    db.execute("ALTER TABLE memories ADD COLUMN category TEXT DEFAULT 'general'")
                except Exception:
                    pass

            db.execute(
                """
                CREATE TABLE IF NOT EXISTS user_profile (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT
                )
                """
            )

        # Seed USER.md if missing.
        if not USER_MD_PATH.exists():
            _atomic_private_text(USER_MD_PATH, "# User profile\n\nNo saved preferences yet.\n")

        # Seed MEMORY.md if missing
        if not MEMORY_MD_PATH.exists():
            _atomic_private_text(MEMORY_MD_PATH, "# Celine memories\n\n")

    def add_memory(self, content: str, category: str = "general") -> bool:
        content = _validate_memory_text(content)
        category = _validate_memory_text(category, field="categoria")[:80]

        with _MEMORY_LOCK, _connect() as db:
            try:
                db.execute(
                    "INSERT INTO memories(category, content, created_at) VALUES (?, ?, ?)",
                    (category, content, datetime.now().isoformat()),
                )
            except sqlite3.IntegrityError:
                # Already exists
                pass

        # Also append to MEMORY.md
        self._sync_to_memory_md()
        return True

    def get_memories(self, limit: int = 30) -> list[str]:
        with _connect() as db:
            cur = db.execute("SELECT content FROM memories ORDER BY id DESC LIMIT ?", (limit,))
            rows = [r[0] for r in cur.fetchall()]
        return rows

    def search_memories(self, query: str, limit: int = 20) -> list[str]:
        clean_query = query.strip()
        if not clean_query:
            return self.get_memories(limit=limit)

        terms = [t for t in clean_query.split() if len(t) > 1]
        with _MEMORY_LOCK, _connect() as db:
            # 1. Direct match
            cur = db.execute(
                "SELECT content FROM memories WHERE content LIKE ? ORDER BY id DESC LIMIT ?",
                (f"%{clean_query}%", limit),
            )
            rows = [r[0] for r in cur.fetchall()]
            if rows:
                return rows

            # 2. Multi-term match (all terms)
            if len(terms) > 1:
                where_clauses = " AND ".join("content LIKE ?" for _ in terms)
                params: list[Any] = [f"%{t}%" for t in terms]
                params.append(limit)
                cur = db.execute(
                    f"SELECT content FROM memories WHERE {where_clauses} ORDER BY id DESC LIMIT ?",
                    tuple(params),
                )
                rows = [r[0] for r in cur.fetchall()]
                if rows:
                    return rows

            # 3. Any-term match (union fallback)
            if terms:
                where_clauses = " OR ".join("content LIKE ?" for _ in terms)
                params = [f"%{t}%" for t in terms]
                params.append(limit)
                cur = db.execute(
                    f"SELECT content FROM memories WHERE {where_clauses} ORDER BY id DESC LIMIT ?",
                    tuple(params),
                )
                rows = [r[0] for r in cur.fetchall()]
                return rows

        return []

    def delete_memory(self, query: str) -> int:
        with _MEMORY_LOCK, _connect() as db:
            cur = db.execute("DELETE FROM memories WHERE content LIKE ?", (f"%{query}%",))
            deleted = cur.rowcount
        self._sync_to_memory_md()
        return deleted

    def get_user_profile(self) -> str:
        if USER_MD_PATH.exists():
            return USER_MD_PATH.read_text(encoding="utf-8").strip()
        return ""

    def update_user_profile(self, text: str) -> None:
        clean = _validate_memory_text(text, field="perfil")
        with _MEMORY_LOCK:
            _atomic_private_text(USER_MD_PATH, clean + "\n")

    def append_to_user_profile(self, fact: str) -> None:
        fact_clean = _validate_memory_text(fact, field="fato")
        current = self.get_user_profile()
        if fact_clean not in current:
            new_profile = f"{current}\n- {fact_clean}".strip()
            self.update_user_profile(new_profile)

    def _sync_to_memory_md(self) -> None:
        memories = self.get_memories(100)
        lines = ["# Celine memories\n"]
        for m in reversed(memories):
            lines.append(f"- {m}")
        lines.append("")
        _atomic_private_text(MEMORY_MD_PATH, "\n".join(lines))


memory_manager = MemoryManager()
