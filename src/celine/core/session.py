from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from typing import Any

from celine.config import CELINE_HOME

DB_PATH = CELINE_HOME / "celine.db"


class SessionManager:
    def __init__(self) -> None:
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        CELINE_HOME.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(DB_PATH) as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
            # Check existing messages table columns
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    role TEXT,
                    content TEXT,
                    tool_calls TEXT,
                    tool_call_id TEXT,
                    name TEXT,
                    created_at TEXT
                )
                """
            )
            db.commit()

    def get_or_create_active_session(self) -> str:
        with sqlite3.connect(DB_PATH) as db:
            cur = db.execute("SELECT id FROM sessions ORDER BY updated_at DESC LIMIT 1")
            row = cur.fetchone()
            if row:
                return row[0]

        # Create new default session
        new_id = f"session_{uuid.uuid4().hex[:8]}"
        now = datetime.now().isoformat()
        with sqlite3.connect(DB_PATH) as db:
            db.execute(
                "INSERT INTO sessions(id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (new_id, "Conversa Inicial", now, now),
            )
            db.commit()
        return new_id

    def create_session(self, title: str = "Nova Conversa") -> str:
        new_id = f"session_{uuid.uuid4().hex[:8]}"
        now = datetime.now().isoformat()
        with sqlite3.connect(DB_PATH) as db:
            db.execute(
                "INSERT INTO sessions(id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (new_id, title, now, now),
            )
            db.commit()
        return new_id

    def list_sessions(self) -> list[dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as db:
            cur = db.execute(
                """
                SELECT s.id, s.title, s.created_at, s.updated_at, COUNT(m.id) as message_count
                FROM sessions s
                LEFT JOIN chat_history m ON s.id = m.session_id
                GROUP BY s.id
                ORDER BY s.updated_at DESC
                """
            )
            rows = cur.fetchall()
            return [
                {
                    "id": r[0],
                    "title": r[1],
                    "created_at": r[2],
                    "updated_at": r[3],
                    "messages": r[4],
                }
                for r in rows
            ]

    def save_message(
        self,
        session_id: str,
        role: str,
        content: str | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        tool_call_id: str | None = None,
        name: str | None = None,
    ) -> None:
        now = datetime.now().isoformat()
        tc_json = json.dumps(tool_calls) if tool_calls else None

        with sqlite3.connect(DB_PATH) as db:
            db.execute(
                """
                INSERT INTO chat_history(session_id, role, content, tool_calls, tool_call_id, name, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, role, content or "", tc_json, tool_call_id, name, now),
            )
            db.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))
            db.commit()

    def get_messages(self, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as db:
            cur = db.execute(
                """
                SELECT role, content, tool_calls, tool_call_id, name
                FROM chat_history
                WHERE session_id = ?
                ORDER BY id DESC LIMIT ?
                """,
                (session_id, limit),
            )
            rows = cur.fetchall()

        messages: list[dict[str, Any]] = []
        for r in reversed(rows):
            role, content, tool_calls_raw, tool_call_id, name = r
            msg: dict[str, Any] = {"role": role, "content": content or ""}
            if tool_calls_raw:
                try:
                    msg["tool_calls"] = json.loads(tool_calls_raw)
                except Exception:
                    pass
            if tool_call_id:
                msg["tool_call_id"] = tool_call_id
            if name:
                msg["name"] = name
            messages.append(msg)

        return messages

    def clear_session(self, session_id: str) -> None:
        with sqlite3.connect(DB_PATH) as db:
            db.execute("DELETE FROM chat_history WHERE session_id = ?", (session_id,))
            db.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (datetime.now().isoformat(), session_id))
            db.commit()

    def delete_session(self, session_id: str) -> bool:
        with sqlite3.connect(DB_PATH) as db:
            db.execute("DELETE FROM chat_history WHERE session_id = ?", (session_id,))
            cur = db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            db.commit()
            return cur.rowcount > 0

    def rename_session(self, session_id: str, new_title: str) -> None:
        with sqlite3.connect(DB_PATH) as db:
            db.execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                (new_title, datetime.now().isoformat(), session_id),
            )
            db.commit()


session_manager = SessionManager()
