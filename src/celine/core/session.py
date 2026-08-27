from __future__ import annotations

import json
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from celine.config import CELINE_HOME

DB_PATH = CELINE_HOME / "state.db"
_STOP_WORDS = {
    "isso", "essa", "esse", "aquela", "aquele", "sobre", "para", "com", "como", "quando",
    "that", "this", "with", "from", "about", "what", "when",
}


@contextmanager
def _connect(path: Path = DB_PATH) -> Iterator[sqlite3.Connection]:
    db = sqlite3.connect(path, timeout=15)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA busy_timeout = 15000")
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


class SessionManager:
    """Canonical session store backed by ``~/.celine/state.db``."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or DB_PATH
        self._ensure_schema()

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        with _connect(self.db_path) as db:
            yield db

    def _ensure_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY, source TEXT NOT NULL, started_at REAL NOT NULL,
                    ended_at REAL, end_reason TEXT, title TEXT, title_source TEXT,
                    last_activity_at REAL, message_count INTEGER DEFAULT 0,
                    tool_call_count INTEGER DEFAULT 0, cwd TEXT, profile_name TEXT,
                    archived INTEGER NOT NULL DEFAULT 0, pinned INTEGER NOT NULL DEFAULT 0,
                    hidden INTEGER NOT NULL DEFAULT 0
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    role TEXT NOT NULL, content TEXT, tool_call_id TEXT, tool_calls TEXT,
                    tool_name TEXT, timestamp REAL NOT NULL, observed INTEGER DEFAULT 0,
                    active INTEGER NOT NULL DEFAULT 1, compacted INTEGER NOT NULL DEFAULT 0
                )"""
            )
            db.execute("CREATE INDEX IF NOT EXISTS idx_celine_messages_session ON messages(session_id, id)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_celine_sessions_activity ON sessions(last_activity_at DESC)")

    @staticmethod
    def _unique_title(db: sqlite3.Connection, requested: str, session_id: str | None = None) -> str:
        base = " ".join(requested.split()).strip()[:120] or "New conversation"
        title = base
        suffix = 2
        while db.execute(
            "SELECT 1 FROM sessions WHERE title = ? AND (? IS NULL OR id != ?)",
            (title, session_id, session_id),
        ).fetchone():
            title = f"{base[:110]} ({suffix})"
            suffix += 1
        return title

    def get_or_create_active_session(self) -> str:
        with self._db() as db:
            row = db.execute(
                """SELECT id FROM sessions
                   WHERE source = 'celine-native' AND ended_at IS NULL AND archived = 0
                   ORDER BY COALESCE(last_activity_at, started_at) DESC LIMIT 1"""
            ).fetchone()
            if row:
                return str(row["id"])
        return self.create_session("Celine")

    def create_session(self, title: str = "New conversation") -> str:
        session_id = f"celine_{uuid.uuid4().hex[:12]}"
        now = time.time()
        with self._db() as db:
            clean_title = self._unique_title(db, title)
            db.execute(
                """INSERT INTO sessions
                   (id, source, started_at, last_activity_at, title, title_source, cwd, profile_name,
                    message_count, tool_call_count, archived, pinned, hidden)
                   VALUES (?, 'celine-native', ?, ?, ?, 'user', ?, 'celine', 0, 0, 0, 0, 0)""",
                (session_id, now, now, clean_title, str(Path.cwd())),
            )
        return session_id

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._db() as db:
            rows = db.execute(
                """SELECT id, title, started_at, last_activity_at, message_count
                   FROM sessions WHERE hidden = 0
                   ORDER BY COALESCE(last_activity_at, started_at) DESC"""
            ).fetchall()
        return [
            {
                "id": str(row["id"]), "title": str(row["title"] or "Conversation"),
                "created_at": float(row["started_at"] or 0),
                "updated_at": float(row["last_activity_at"] or row["started_at"] or 0),
                "messages": int(row["message_count"] or 0),
            }
            for row in rows
        ]

    def save_message(
        self, session_id: str, role: str, content: str | None = None,
        tool_calls: list[dict[str, Any]] | None = None, tool_call_id: str | None = None,
        name: str | None = None,
    ) -> None:
        if role not in {"system", "user", "assistant", "tool"}:
            raise ValueError(f"Invalid message role: {role}")
        now = time.time()
        encoded_calls = json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None
        with self._db() as db:
            if not db.execute("SELECT 1 FROM sessions WHERE id = ?", (session_id,)).fetchone():
                raise ValueError(f"Session not found: {session_id}")
            db.execute(
                """INSERT INTO messages
                   (session_id, role, content, tool_calls, tool_call_id, tool_name,
                    timestamp, observed, active, compacted)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0, 1, 0)""",
                (session_id, role, content or "", encoded_calls, tool_call_id, name, now),
            )
            tool_count = len(tool_calls or []) if role == "assistant" else 0
            db.execute(
                """UPDATE sessions SET last_activity_at = ?,
                   message_count = COALESCE(message_count, 0) + 1,
                   tool_call_count = COALESCE(tool_call_count, 0) + ? WHERE id = ?""",
                (now, tool_count, session_id),
            )

    def get_messages(self, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self._db() as db:
            rows = db.execute(
                """SELECT role, content, tool_calls, tool_call_id, tool_name FROM messages
                   WHERE session_id = ? AND active = 1 ORDER BY id DESC LIMIT ?""",
                (session_id, max(1, min(int(limit), 500))),
            ).fetchall()
        messages: list[dict[str, Any]] = []
        for row in reversed(rows):
            message: dict[str, Any] = {"role": row["role"], "content": row["content"] or ""}
            if row["tool_calls"]:
                try:
                    message["tool_calls"] = json.loads(row["tool_calls"])
                except (TypeError, json.JSONDecodeError):
                    pass
            if row["tool_call_id"]:
                message["tool_call_id"] = row["tool_call_id"]
            if row["tool_name"]:
                message["name"] = row["tool_name"]
            messages.append(message)
        return messages

    def search_context(self, query: str, active_session_id: str, limit: int = 6) -> list[dict[str, str]]:
        terms = list(dict.fromkeys(
            term.casefold() for term in re.findall(r"[\wÀ-ÿ]{4,}", query)
            if term.casefold() not in _STOP_WORDS
        ))[:12]
        if not terms:
            return []
        with self._db() as db:
            rows = db.execute(
                """SELECT m.session_id, m.role, m.content, m.timestamp, s.title
                   FROM messages m JOIN sessions s ON s.id = m.session_id
                   WHERE m.session_id != ? AND m.role IN ('user', 'assistant')
                     AND m.active = 1 AND COALESCE(m.content, '') != ''
                   ORDER BY m.timestamp DESC LIMIT 1200""",
                (active_session_id,),
            ).fetchall()
        now = time.time()
        matches: list[tuple[float, sqlite3.Row]] = []
        for row in rows:
            content = " ".join(str(row["content"] or "").split())
            lowered = content.casefold()
            hits = sum(min(lowered.count(term), 3) for term in terms)
            if not hits:
                continue
            exact_bonus = 3 if query.casefold() in lowered else 0
            age_days = max(0.0, (now - float(row["timestamp"] or now)) / 86400)
            matches.append((hits + exact_bonus + 1 / (1 + age_days / 30), row))
        matches.sort(key=lambda item: (item[0], float(item[1]["timestamp"] or 0)), reverse=True)
        return [
            {
                "session_id": str(row["session_id"]), "title": str(row["title"] or "Previous conversation"),
                "role": str(row["role"]), "content": " ".join(str(row["content"]).split())[:600],
            }
            for _, row in matches[: max(1, min(int(limit), 20))]
        ]

    def clear_session(self, session_id: str) -> None:
        with self._db() as db:
            db.execute("UPDATE messages SET active = 0 WHERE session_id = ?", (session_id,))
            db.execute(
                "UPDATE sessions SET last_activity_at = ?, message_count = 0, tool_call_count = 0 WHERE id = ?",
                (time.time(), session_id),
            )

    def delete_session(self, session_id: str) -> bool:
        with self._db() as db:
            cursor = db.execute(
                "UPDATE sessions SET archived = 1, ended_at = ?, end_reason = 'user_deleted' WHERE id = ?",
                (time.time(), session_id),
            )
            return cursor.rowcount > 0

    def rename_session(self, session_id: str, new_title: str) -> None:
        with self._db() as db:
            clean_title = self._unique_title(db, new_title, session_id)
            db.execute(
                "UPDATE sessions SET title = ?, last_activity_at = ?, title_source = 'user' WHERE id = ?",
                (clean_title, time.time(), session_id),
            )


session_manager = SessionManager()
