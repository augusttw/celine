from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from celine.config import CELINE_HOME, assert_celine_boundary

MEMORIES_DIR = CELINE_HOME / "memories"
USER_MD_PATH = MEMORIES_DIR / "USER.md"
MEMORY_MD_PATH = MEMORIES_DIR / "MEMORY.md"
DB_PATH = CELINE_HOME / "celine.db"


class MemoryManager:
    def __init__(self) -> None:
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        assert_celine_boundary(CELINE_HOME)
        CELINE_HOME.mkdir(parents=True, exist_ok=True)
        MEMORIES_DIR.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(DB_PATH) as db:
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
            db.commit()

        # Seed USER.md if missing. Never import another profile implicitly.
        if not USER_MD_PATH.exists():
            default_user = (
                "Ambiente: Linux x86_64, terminal interativo.\n"
                "Preferências: Respostas diretas, código limpo e autenticidade.\n"
            )
            USER_MD_PATH.write_text(default_user, encoding="utf-8")

        # Seed MEMORY.md if missing
        if not MEMORY_MD_PATH.exists():
            MEMORY_MD_PATH.write_text("# Memórias da Celine\n\n", encoding="utf-8")

    def add_memory(self, content: str, category: str = "general") -> bool:
        content = content.strip()
        if not content:
            return False

        with sqlite3.connect(DB_PATH) as db:
            try:
                db.execute(
                    "INSERT INTO memories(category, content, created_at) VALUES (?, ?, ?)",
                    (category, content, datetime.now().isoformat()),
                )
                db.commit()
            except sqlite3.IntegrityError:
                # Already exists
                pass

        # Also append to MEMORY.md
        self._sync_to_memory_md()
        return True

    def get_memories(self, limit: int = 30) -> list[str]:
        with sqlite3.connect(DB_PATH) as db:
            cur = db.execute("SELECT content FROM memories ORDER BY id DESC LIMIT ?", (limit,))
            rows = [r[0] for r in cur.fetchall()]
        return rows

    def search_memories(self, query: str) -> list[str]:
        with sqlite3.connect(DB_PATH) as db:
            cur = db.execute(
                "SELECT content FROM memories WHERE content LIKE ? ORDER BY id DESC LIMIT 20",
                (f"%{query}%",),
            )
            return [r[0] for r in cur.fetchall()]

    def delete_memory(self, query: str) -> int:
        with sqlite3.connect(DB_PATH) as db:
            cur = db.execute("DELETE FROM memories WHERE content LIKE ?", (f"%{query}%",))
            deleted = cur.rowcount
            db.commit()
        self._sync_to_memory_md()
        return deleted

    def get_user_profile(self) -> str:
        if USER_MD_PATH.exists():
            return USER_MD_PATH.read_text(encoding="utf-8").strip()
        return ""

    def update_user_profile(self, text: str) -> None:
        USER_MD_PATH.write_text(text, encoding="utf-8")

    def append_to_user_profile(self, fact: str) -> None:
        current = self.get_user_profile()
        fact_clean = fact.strip()
        if fact_clean not in current:
            new_profile = f"{current}\n- {fact_clean}".strip()
            self.update_user_profile(new_profile)

    def _sync_to_memory_md(self) -> None:
        memories = self.get_memories(100)
        lines = ["# Memórias da Celine\n"]
        for m in reversed(memories):
            lines.append(f"- {m}")
        lines.append("")
        MEMORY_MD_PATH.write_text("\n".join(lines), encoding="utf-8")


memory_manager = MemoryManager()
