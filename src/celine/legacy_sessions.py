from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


def _timestamp(value: Any) -> float:
    try:
        return datetime.fromisoformat(str(value)).timestamp()
    except (TypeError, ValueError):
        return datetime.now().timestamp()


def migrate_legacy_sessions(home: Path) -> tuple[int, int]:
    """Synchronize legacy ``celine.db`` data into canonical ``state.db``.

    The old database is retained as a backup. Existing canonical IDs are never
    overwritten. Message fingerprints make the migration safe to run repeatedly.
    """

    legacy_path = home / "celine.db"
    state_path = home / "state.db"
    if not legacy_path.is_file() or not state_path.is_file():
        return 0, 0

    legacy = sqlite3.connect(legacy_path)
    legacy.row_factory = sqlite3.Row
    state = sqlite3.connect(state_path)
    state.row_factory = sqlite3.Row
    sessions_added = 0
    messages_added = 0
    try:
        required = {row[1] for row in state.execute("PRAGMA table_info(sessions)")}
        if not {"id", "source", "started_at", "title"}.issubset(required):
            return 0, 0
        legacy_tables = {row[0] for row in legacy.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"sessions", "chat_history"}.issubset(legacy_tables):
            return 0, 0

        state.execute(
            """CREATE TABLE IF NOT EXISTS memories (
               id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT DEFAULT 'general',
               content TEXT UNIQUE, created_at TEXT)"""
        )
        legacy_memory_table = "memories" in legacy_tables
        if legacy_memory_table:
            for memory in legacy.execute("SELECT category, content, created_at FROM memories ORDER BY id"):
                state.execute(
                    "INSERT OR IGNORE INTO memories(category, content, created_at) VALUES (?, ?, ?)",
                    (memory["category"] or "general", memory["content"], memory["created_at"]),
                )

        for session in legacy.execute("SELECT id, title, created_at, updated_at FROM sessions ORDER BY created_at"):
            sid = str(session["id"] or "").strip()
            if not sid:
                continue
            exists = state.execute("SELECT 1 FROM sessions WHERE id = ?", (sid,)).fetchone()
            if not exists:
                started = _timestamp(session["created_at"])
                updated = _timestamp(session["updated_at"])
                title = str(session["title"] or "Imported conversation")
                if state.execute("SELECT 1 FROM sessions WHERE title = ?", (title,)).fetchone():
                    title = f"{title[:100]} · {sid[-6:]}"
                state.execute(
                    """INSERT INTO sessions
                       (id, source, started_at, last_activity_at, title, title_source,
                        cwd, profile_name, message_count, tool_call_count)
                       VALUES (?, 'celine-legacy', ?, ?, ?, 'migration', ?, 'celine', 0, 0)""",
                    (sid, started, updated, title, str(home)),
                )
                sessions_added += 1
            existing_messages = {
                (
                    str(row["role"]), str(row["content"] or ""), str(row["tool_call_id"] or ""),
                    str(row["tool_name"] or ""), round(float(row["timestamp"] or 0), 3),
                )
                for row in state.execute(
                    "SELECT role, content, tool_call_id, tool_name, timestamp FROM messages WHERE session_id = ?",
                    (sid,),
                )
            }
            tool_count = 0
            for message in legacy.execute(
                """SELECT role, content, tool_calls, tool_call_id, name, created_at
                   FROM chat_history WHERE session_id = ? ORDER BY id""",
                (sid,),
            ):
                role = str(message["role"] or "user")
                tool_calls = message["tool_calls"]
                if tool_calls:
                    try:
                        parsed = json.loads(tool_calls)
                        tool_count += len(parsed) if isinstance(parsed, list) else 1
                    except (TypeError, json.JSONDecodeError):
                        tool_calls = None
                if role == "tool":
                    tool_count += 1
                fingerprint = (
                    role, str(message["content"] or ""), str(message["tool_call_id"] or ""),
                    str(message["name"] or ""), round(_timestamp(message["created_at"]), 3),
                )
                if fingerprint in existing_messages:
                    continue
                state.execute(
                    """INSERT INTO messages
                       (session_id, role, content, tool_call_id, tool_calls, tool_name,
                        timestamp, observed, active, compacted)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 0, 1, 0)""",
                    (
                        sid,
                        role,
                        str(message["content"] or ""),
                        message["tool_call_id"],
                        tool_calls,
                        message["name"],
                        _timestamp(message["created_at"]),
                    ),
                )
                messages_added += 1
                existing_messages.add(fingerprint)
            count = state.execute("SELECT COUNT(*) FROM messages WHERE session_id = ?", (sid,)).fetchone()[0]
            state.execute(
                "UPDATE sessions SET message_count = ?, tool_call_count = ? WHERE id = ?",
                (count, tool_count, sid),
            )
        state.commit()
    finally:
        legacy.close()
        state.close()
    return sessions_added, messages_added
