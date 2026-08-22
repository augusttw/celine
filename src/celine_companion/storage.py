from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import uuid
from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2
COLLECTIONS = ("moments", "milestones", "important_dates", "interaction_preferences", "active_threads")
LIMITS = {
    "moments": 250,
    "milestones": 100,
    "important_dates": 100,
    "interaction_preferences": 100,
    "active_threads": 100,
}
_ALLOWED_FIELDS = {"shared_focus", "connection_note", "check_in_style", "expressive_mood"}
_ALLOWED_SIGNIFICANCE = {"small", "normal", "important"}
_SECRET_PATTERNS = (
    re.compile(
        r"(?i)(?:api[_ -]?key|access[_ -]?token|refresh[_ -]?token|token|secret|credential|password|senha|"
        r"private[_ -]?key|authorization)\s*[:=]\s*\S+"
    ),
    re.compile(r"(?i)authorization\s*:\s*(?:bearer|basic)\s+\S+"),
    re.compile(r"(?i)\b(?:ghp_|gho_|ghu_|ghs_|ghr_|github_pat_|sk-)[A-Za-z0-9_\-]{12,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)
_LOCK = threading.RLock()


def _now(dt: datetime | None = None) -> str:
    return (dt or datetime.now(UTC)).astimezone(UTC).isoformat()


def _clean(value: Any, *, maximum: int, name: str, required: bool = True) -> str:
    result = " ".join(str(value).split()).strip()
    if required and not result:
        raise ValueError(f"{name} é obrigatório.")
    if len(result) > maximum:
        raise ValueError(f"{name} excede o limite de {maximum} caracteres.")
    if result and any(pattern.search(result) for pattern in _SECRET_PATTERNS):
        raise ValueError("Conteúdo com aparência de segredo não pode ser armazenado.")
    return result


def _default_state() -> dict[str, Any]:
    now = _now()
    return {
        "version": SCHEMA_VERSION,
        "created_at": now,
        "updated_at": now,
        "state": {
            "shared_focus": "",
            "connection_note": "Uma relação digital construída com atenção, autonomia e consentimento.",
            "check_in_style": "natural e sem interromper à toa",
            "expressive_mood": "presente e curiosa",
        },
        **{name: [] for name in COLLECTIONS},
        "proactivity": {
            "config": {
                "enabled": False,
                "cadence_hours": 24,
                "quiet_hours_start": 22,
                "quiet_hours_end": 8,
                "cooldown_hours": 12,
                "max_daily": 1,
                "preferred_topics": [],
                "desktop_notifications": False,
            },
            "state": {"last_checkin_at": None, "snoozed_until": None, "daily": {}},
        },
        "audit": [],
        "retention": {"policy": "oldest-first", "limits": deepcopy(LIMITS)},
    }


class RelationshipStore:
    """Versioned, private relationship journal with deterministic operations."""

    def __init__(self, home: Path | None = None) -> None:
        base = home or Path(os.environ.get("CELINE_HOME", Path.home() / ".celine"))
        self.directory = base.expanduser().resolve() / "celine-companion"
        self.path = self.directory / "relationship.json"

    def _ensure_directory(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            self.directory.chmod(0o700)

    @contextmanager
    def _process_lock(self):
        self._ensure_directory()
        lock_path = self.directory / ".relationship.lock"
        with lock_path.open("a+", encoding="utf-8") as handle:
            if os.name == "posix":
                lock_path.chmod(0o600)
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if os.name == "posix":
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _migrate(data: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        version = data.get("version", 1)
        if version == SCHEMA_VERSION:
            return data, False
        if version != 1 or not isinstance(data.get("state"), dict) or not isinstance(data.get("moments"), list):
            raise ValueError("Versão inválida no journal relacional.")
        migrated = _default_state()
        migrated["created_at"] = data.get("created_at", migrated["created_at"])
        for key, value in data["state"].items():
            if key in _ALLOWED_FIELDS and isinstance(value, str):
                migrated["state"][key] = _clean(value, maximum=300, name=f"state.{key}", required=False)
        for old in data["moments"][-LIMITS["moments"] :]:
            if not isinstance(old, dict):
                continue
            text = _clean(old.get("text", ""), maximum=1000, name="legacy.text")
            raw_tags = old.get("tags", []) if isinstance(old.get("tags", []), list) else []
            tags = list(dict.fromkeys(_clean(tag, maximum=40, name="legacy.tag").lower() for tag in raw_tags))
            if len(tags) > 8:
                tags = tags[:8]
            significance = old.get("significance", "normal")
            if significance not in _ALLOWED_SIGNIFICANCE:
                significance = "normal"
            raw_id = str(old.get("id", ""))
            item_id = raw_id if re.fullmatch(r"[A-Za-z0-9_-]{1,64}", raw_id) else uuid.uuid4().hex[:12]
            try:
                created = datetime.fromisoformat(str(old.get("created_at"))).astimezone(UTC).isoformat()
            except (TypeError, ValueError):
                created = _now()
            item = {
                "id": item_id,
                "text": text,
                "significance": significance,
                "tags": tags,
                "provenance": "migration:v1",
                "created_at": created,
                "updated_at": created,
            }
            migrated["moments"].append(item)
        migrated["audit"].append(
            {"action": "migrate", "target": "schema", "id": "v1-v2", "at": _now(), "provenance": "automatic"}
        )
        return migrated, True

    def _read_unlocked(self) -> dict[str, Any]:
        self._ensure_directory()
        if not self.path.exists():
            data = _default_state()
            self._write_unlocked(data)
            return data
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("O journal relacional está corrompido; restaure um backup antes de continuar.") from exc
        if not isinstance(raw, dict):
            raise ValueError("Formato inválido no journal relacional.")
        data, changed = self._migrate(raw)
        for key in COLLECTIONS:
            if not isinstance(data.get(key), list):
                raise ValueError(f"Coleção inválida: {key}.")
        if changed:
            self._write_unlocked(data)
        return data

    def _write_unlocked(self, data: dict[str, Any]) -> None:
        self._ensure_directory()
        data["updated_at"] = _now()
        fd, raw_tmp = tempfile.mkstemp(prefix=".relationship.", dir=self.directory)
        tmp = Path(raw_tmp)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(tmp, 0o600)
            os.replace(tmp, self.path)
            if os.name == "posix":
                self.path.chmod(0o600)
        finally:
            tmp.unlink(missing_ok=True)

    @staticmethod
    def _audit(data: dict[str, Any], action: str, target: str, item_id: str, provenance: str) -> None:
        data["audit"].append(
            {"action": action, "target": target, "id": item_id, "at": _now(), "provenance": provenance}
        )
        data["audit"] = data["audit"][-1000:]

    def status(self) -> dict[str, Any]:
        with _LOCK, self._process_lock():
            data = self._read_unlocked()
            return {
                "version": SCHEMA_VERSION,
                "state": deepcopy(data["state"]),
                "moment_count": len(data["moments"]),
                "counts": {k: len(data[k]) for k in COLLECTIONS},
                "recent_moments": deepcopy(list(reversed(data["moments"][-3:]))),
                "proactivity": deepcopy(data["proactivity"]),
                "retention": deepcopy(data["retention"]),
                "updated_at": data["updated_at"],
            }

    def add(
        self,
        collection: str,
        text: str,
        *,
        significance: str = "normal",
        tags: list[str] | None = None,
        provenance: str = "user-consent",
        date: str | None = None,
    ) -> dict[str, Any]:
        if collection not in COLLECTIONS:
            raise ValueError("collection inválida.")
        clean_text = _clean(text, maximum=1000, name="text")
        source = _clean(provenance, maximum=80, name="provenance")
        if significance not in _ALLOWED_SIGNIFICANCE:
            raise ValueError("significance inválida.")
        clean_tags = list(dict.fromkeys(_clean(t, maximum=40, name="tag").lower() for t in (tags or [])))
        if len(clean_tags) > 8:
            raise ValueError("no máximo 8 tags são permitidas.")
        if date:
            try:
                datetime.fromisoformat(date)
            except ValueError as exc:
                raise ValueError("date deve estar em formato ISO.") from exc
        now = _now()
        item = {
            "id": uuid.uuid4().hex[:12],
            "text": clean_text,
            "significance": significance,
            "tags": clean_tags,
            "provenance": source,
            "created_at": now,
            "updated_at": now,
        }
        if date:
            item["date"] = date
        with _LOCK, self._process_lock():
            data = self._read_unlocked()
            data[collection].append(item)
            pruned = max(0, len(data[collection]) - LIMITS[collection])
            data[collection] = data[collection][-LIMITS[collection] :]
            self._audit(data, "create", collection, item["id"], source)
            self._write_unlocked(data)
        return {**deepcopy(item), "pruned_count": pruned}

    def update(
        self,
        collection: str,
        item_id: str,
        *,
        text: str | None = None,
        significance: str | None = None,
        tags: list[str] | None = None,
        date: str | None = None,
        provenance: str = "user-request",
    ) -> dict[str, Any]:
        if collection not in COLLECTIONS:
            raise ValueError("collection inválida.")
        with _LOCK, self._process_lock():
            data = self._read_unlocked()
            item = next((x for x in data[collection] if x.get("id") == item_id), None)
            if item is None:
                raise ValueError("item não encontrado.")
            if text is not None:
                item["text"] = _clean(text, maximum=1000, name="text")
            if significance is not None:
                if significance not in _ALLOWED_SIGNIFICANCE:
                    raise ValueError("significance inválida.")
                item["significance"] = significance
            if tags is not None:
                clean_tags = list(dict.fromkeys(_clean(t, maximum=40, name="tag").lower() for t in tags))
                if len(clean_tags) > 8:
                    raise ValueError("no máximo 8 tags são permitidas.")
                item["tags"] = clean_tags
            if date is not None:
                try:
                    datetime.fromisoformat(date)
                except ValueError as exc:
                    raise ValueError("date deve estar em formato ISO.") from exc
                item["date"] = date
            item["updated_at"] = _now()
            item["provenance"] = _clean(provenance, maximum=80, name="provenance")
            self._audit(data, "update", collection, item_id, item["provenance"])
            self._write_unlocked(data)
            return deepcopy(item)

    def list_items(self, collection: str, limit: int = 10) -> list[dict[str, Any]]:
        if collection not in COLLECTIONS:
            raise ValueError("collection inválida.")
        bounded = max(1, min(int(limit), 100))
        with _LOCK, self._process_lock():
            return deepcopy(list(reversed(self._read_unlocked()[collection][-bounded:])))

    def remove(self, collection: str, item_id: str, provenance: str = "user-request") -> bool:
        if collection not in COLLECTIONS:
            raise ValueError("collection inválida.")
        target = _clean(item_id, maximum=64, name="item_id")
        with _LOCK, self._process_lock():
            data = self._read_unlocked()
            before = len(data[collection])
            data[collection] = [x for x in data[collection] if x.get("id") != target]
            removed = before != len(data[collection])
            if removed:
                self._audit(data, "delete", collection, target, provenance)
                self._write_unlocked(data)
            return removed

    def search(self, query: str, *, collection: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        needle = _clean(query, maximum=200, name="query").casefold()
        targets = (collection,) if collection else COLLECTIONS
        if any(x not in COLLECTIONS for x in targets):
            raise ValueError("collection inválida.")
        with _LOCK, self._process_lock():
            data = self._read_unlocked()
            found = []
            for name in targets:
                for item in data[name]:
                    hay = " ".join(
                        [str(item.get("text", "")), *map(str, item.get("tags", [])), str(item.get("date", ""))]
                    ).casefold()
                    if needle in hay:
                        found.append({"collection": name, **deepcopy(item)})
            found.sort(key=lambda x: (x.get("created_at", ""), x["collection"], x["id"]), reverse=True)
            return found[: max(1, min(int(limit), 100))]

    def export(self, format: str = "json") -> str:
        with _LOCK, self._process_lock():
            data = deepcopy(self._read_unlocked())
        if format == "json":
            return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
        if format != "markdown":
            raise ValueError("format deve ser json ou markdown.")
        lines = ["# Celine — memória relacional", "", f"Exportado em: {_now()}", ""]
        for name in COLLECTIONS:
            lines += [f"## {name.replace('_', ' ').title()}", ""]
            lines += [f"- **{x['created_at']}** — {x['text']} _(origem: {x['provenance']})_" for x in data[name]] or [
                "- Nenhum registro."
            ]
            lines.append("")
        return "\n".join(lines)

    def set_state(self, field: str, value: str) -> dict[str, str]:
        if field not in _ALLOWED_FIELDS:
            raise ValueError(f"field deve ser um de: {', '.join(sorted(_ALLOWED_FIELDS))}")
        clean = _clean(value, maximum=300, name="value", required=False)
        with _LOCK, self._process_lock():
            data = self._read_unlocked()
            data["state"][field] = clean
            self._audit(data, "update", "state", field, "user-request")
            self._write_unlocked(data)
        return {"field": field, "value": clean}

    def configure_proactivity(self, **changes: Any) -> dict[str, Any]:
        allowed = {
            "enabled",
            "cadence_hours",
            "quiet_hours_start",
            "quiet_hours_end",
            "cooldown_hours",
            "max_daily",
            "preferred_topics",
            "desktop_notifications",
        }
        if set(changes) - allowed:
            raise ValueError("campo de proatividade inválido.")
        with _LOCK, self._process_lock():
            data = self._read_unlocked()
            cfg = data["proactivity"]["config"]
            for key, value in changes.items():
                if key in {"enabled", "desktop_notifications"}:
                    if not isinstance(value, bool):
                        raise ValueError(f"{key} deve ser booleano.")
                elif key == "preferred_topics":
                    if not isinstance(value, list) or len(value) > 12:
                        raise ValueError("preferred_topics deve ser lista de até 12 itens.")
                    value = [_clean(x, maximum=60, name="topic") for x in value]
                else:
                    value = int(value)
                    bounds = {
                        "cadence_hours": (1, 720),
                        "cooldown_hours": (1, 720),
                        "max_daily": (0, 10),
                        "quiet_hours_start": (0, 23),
                        "quiet_hours_end": (0, 23),
                    }[key]
                    if not bounds[0] <= value <= bounds[1]:
                        raise ValueError(f"{key} fora do intervalo permitido.")
                cfg[key] = value
            self._audit(data, "configure", "proactivity", "config", "user-request")
            self._write_unlocked(data)
            return deepcopy(cfg)

    def pulse_status(self, now: datetime | None = None) -> dict[str, Any]:
        current = now.astimezone() if now else datetime.now().astimezone()
        with _LOCK, self._process_lock():
            data = self._read_unlocked()
            cfg = deepcopy(data["proactivity"]["config"])
            state = deepcopy(data["proactivity"]["state"])
        reasons = []
        if not cfg["enabled"]:
            reasons.append("disabled")
        hour = current.hour
        start, end = cfg["quiet_hours_start"], cfg["quiet_hours_end"]
        quiet = (
            (start < end and start <= hour < end) or (start > end and (hour >= start or hour < end)) or (start == end)
        )
        if quiet:
            reasons.append("quiet_hours")
        if state["snoozed_until"] and current < datetime.fromisoformat(state["snoozed_until"]):
            reasons.append("snoozed")
        last = datetime.fromisoformat(state["last_checkin_at"]) if state["last_checkin_at"] else None
        if last and current < last + timedelta(hours=max(cfg["cadence_hours"], cfg["cooldown_hours"])):
            reasons.append("cooldown")
        day = current.date().isoformat()
        if int(state["daily"].get(day, 0)) >= cfg["max_daily"]:
            reasons.append("daily_limit")
        return {"due": not reasons, "reasons": reasons, "config": cfg, "state": state}

    def snooze(self, hours: int, now: datetime | None = None) -> dict[str, Any]:
        hours = int(hours)
        if not 1 <= hours <= 720:
            raise ValueError("hours deve estar entre 1 e 720.")
        current = now.astimezone() if now else datetime.now().astimezone()
        until = current + timedelta(hours=hours)
        with _LOCK, self._process_lock():
            data = self._read_unlocked()
            data["proactivity"]["state"]["snoozed_until"] = _now(until)
            self._audit(data, "snooze", "proactivity", "state", "user-request")
            self._write_unlocked(data)
        return {"snoozed_until": _now(until)}

    def record_checkin(self, topic: str = "", now: datetime | None = None) -> dict[str, Any]:
        current = now.astimezone() if now else datetime.now().astimezone()
        clean_topic = _clean(topic, maximum=80, name="topic", required=False)
        day = current.date().isoformat()
        with _LOCK, self._process_lock():
            data = self._read_unlocked()
            state = data["proactivity"]["state"]
            state["last_checkin_at"] = _now(current)
            state["snoozed_until"] = None
            state["daily"][day] = int(state["daily"].get(day, 0)) + 1
            state["daily"] = {
                k: v for k, v in state["daily"].items() if k >= (current.date() - timedelta(days=31)).isoformat()
            }
            self._audit(data, "record_checkin", "proactivity", clean_topic or "checkin", "explicit")
            self._write_unlocked(data)
        return {"recorded_at": _now(current), "topic": clean_topic, "daily_count": state["daily"][day]}

    # v1 compatibility
    def add_moment(self, text: str, significance: str = "normal", tags: list[str] | None = None) -> dict[str, Any]:
        return self.add("moments", text, significance=significance, tags=tags)

    def list_moments(self, limit: int = 10) -> list[dict[str, Any]]:
        return self.list_items("moments", limit)

    def remove_moment(self, moment_id: str) -> bool:
        return self.remove("moments", moment_id)
