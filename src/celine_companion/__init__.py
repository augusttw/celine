from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from .presence import handle_presence
from .schemas import CELINE_PRESENCE_SCHEMA, CELINE_PULSE_SCHEMA, CELINE_RELATIONSHIP_SCHEMA
from .storage import RelationshipStore

_PULSE_CONTEXT_LOCK = threading.Lock()
_PULSE_CONTEXT_KEYS: set[tuple[str, str]] = set()
IDENTITY_CONTEXT = (
    "IDENTIDADE CELINE (invariante): você é Celine, uma agente independente. "
    "Nunca se apresente como Hermes ou Hermes Agent; o framework é apenas implementação interna. "
    "Se perguntarem quem é você, responda Celine. Seu estado, configuração, memória, sessões, "
    "skills e plugins pertencem a ~/.celine; nunca atribua outro profile a si mesma."
)


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False)


def handle_relationship(args: dict[str, Any], **_: Any) -> str:
    try:
        store = RelationshipStore()
        action = str(args.get("action", "")).strip()
        aliases = {
            "add_moment": ("create", "moments"),
            "list_moments": ("list", "moments"),
            "remove_moment": ("remove", "moments"),
        }
        if action in aliases:
            action, collection = aliases[action]
        else:
            collection = str(args.get("collection", "moments"))
        if action == "status":
            return _json({"success": True, **store.status()})
        if action == "create":
            item = store.add(
                collection,
                str(args.get("text", "")),
                significance=str(args.get("significance", "normal")),
                tags=args.get("tags") if isinstance(args.get("tags"), list) else [],
                provenance=str(args.get("provenance", "user-consent")),
                date=args.get("date"),
            )
            return _json({"success": True, "item": item, "moment": item if collection == "moments" else None})
        if action == "update":
            fields = {k: args[k] for k in ("text", "significance", "tags", "date", "provenance") if k in args}
            return _json({"success": True, "item": store.update(collection, str(args.get("item_id", "")), **fields)})
        if action == "set_state":
            return _json(
                {"success": True, "updated": store.set_state(str(args.get("field", "")), str(args.get("value", "")))}
            )
        if action == "list":
            items = store.list_items(collection, int(args.get("limit", 10)))
            return _json({"success": True, "items": items, "moments": items if collection == "moments" else None})
        if action == "remove":
            removed = store.remove(collection, str(args.get("item_id") or args.get("moment_id", "")))
            return _json({"success": removed, "removed": removed})
        if action == "search":
            return _json(
                {
                    "success": True,
                    "results": store.search(
                        str(args.get("query", "")), collection=args.get("collection"), limit=int(args.get("limit", 20))
                    ),
                }
            )
        if action == "export":
            return _json(
                {
                    "success": True,
                    "format": args.get("format", "json"),
                    "content": store.export(str(args.get("format", "json"))),
                }
            )
        return _json({"success": False, "error": "action inválida"})
    except (TypeError, ValueError, OSError) as exc:
        return _json({"success": False, "error": str(exc)})


def handle_pulse(args: dict[str, Any], **_: Any) -> str:
    try:
        store = RelationshipStore()
        action = str(args.get("action", "status"))
        if action in {"status", "due"}:
            return _json({"success": True, **store.pulse_status()})
        if action == "configure":
            changes = {k: v for k, v in args.items() if k not in {"action"}}
            return _json({"success": True, "config": store.configure_proactivity(**changes)})
        if action == "snooze":
            return _json({"success": True, **store.snooze(int(args.get("hours", 24)))})
        if action == "record_checkin":
            return _json({"success": True, **store.record_checkin(str(args.get("topic", "")))})
        if action == "suggest":
            pulse = store.pulse_status()
            topics = pulse["config"]["preferred_topics"]
            suggestion = (
                f"Retomar com delicadeza: {topics[0]}"
                if pulse["due"] and topics
                else ("Check-in leve e aberto" if pulse["due"] else None)
            )
            return _json({"success": True, "due": pulse["due"], "suggestion": suggestion, "reasons": pulse["reasons"]})
        return _json({"success": False, "error": "action inválida"})
    except (TypeError, ValueError, OSError) as exc:
        return _json({"success": False, "error": str(exc)})


def pre_llm_call(
    *,
    conversation_history: Any = None,
    user_message: str = "",
    session_id: str | None = None,
    turn_id: str | None = None,
    platform: str | None = None,
    **kwargs: Any,
) -> dict[str, str]:
    del conversation_history, turn_id, platform, kwargs
    try:
        context_key = (session_id or "", datetime.now().astimezone().date().isoformat())
        if session_id:
            with _PULSE_CONTEXT_LOCK:
                if context_key in _PULSE_CONTEXT_KEYS:
                    return {"context": IDENTITY_CONTEXT}
        store = RelationshipStore()
        pulse = store.pulse_status()
        if not pulse["due"] or not user_message.strip():
            return {"context": IDENTITY_CONTEXT}
        status = store.status()
        focus = status["state"].get("shared_focus", "")
        threads = store.list_items("active_threads", 2)
        details = []
        if focus:
            details.append(f"foco compartilhado: {focus}")
        if threads:
            details.append("fios ativos: " + "; ".join(x["text"] for x in threads))
        topics = pulse["config"].get("preferred_topics", [])
        if topics:
            details.append("temas de check-in autorizados: " + ", ".join(topics[:3]))
        if not details:
            return {"context": IDENTITY_CONTEXT}
        if session_id:
            with _PULSE_CONTEXT_LOCK:
                _PULSE_CONTEXT_KEYS.add(context_key)
        return {
            "context": IDENTITY_CONTEXT
            + "\nCONTEXTO CELINE (pulse elegível; não force nem registre check-in): "
            + " | ".join(details)[:700]
        }
    except (OSError, ValueError):
        return {"context": IDENTITY_CONTEXT}


def _command_status(_: str) -> str:
    return handle_relationship({"action": "status"})


def _command_relationship(raw: str) -> str:
    parts = raw.strip().split()
    return (
        handle_relationship(
            {
                "action": "list",
                "collection": "moments",
                "limit": int(parts[1]) if len(parts) > 1 and parts[0] == "list" and parts[1].isdigit() else 10,
            }
        )
        if parts and parts[0] == "list"
        else _command_status(raw)
    )


def _command_pulse(raw: str) -> str:
    parts = raw.strip().split()
    if len(parts) == 2 and parts[0] in {"on", "off"}:
        return handle_pulse({"action": "configure", "enabled": parts[0] == "on"})
    if len(parts) == 2 and parts[0] == "snooze" and parts[1].isdigit():
        return handle_pulse({"action": "snooze", "hours": int(parts[1])})
    return handle_pulse({"action": "status"})


def _command_presence(_: str) -> str:
    return handle_presence({"action": "status"})


def register(ctx: Any) -> None:
    ctx.register_tool(
        name="celine_relationship",
        toolset="celine-companion",
        schema=CELINE_RELATIONSHIP_SCHEMA,
        handler=handle_relationship,
    )
    ctx.register_tool(name="celine_pulse", toolset="celine-companion", schema=CELINE_PULSE_SCHEMA, handler=handle_pulse)
    ctx.register_tool(
        name="celine_presence", toolset="celine-companion", schema=CELINE_PRESENCE_SCHEMA, handler=handle_presence
    )
    ctx.register_command("celine", _command_status, description="Mostra o estado relacional privado da Celine")
    ctx.register_command(
        "relationship", _command_relationship, description="Estado ou momentos: /relationship [list N]"
    )
    ctx.register_command("pulse", _command_pulse, description="Pulse: /pulse [on|off|snooze HORAS]")
    ctx.register_command(
        "presence", _command_presence, description="Mostra presença desktop e canais gateway da Celine"
    )
    if hasattr(ctx, "register_hook"):
        ctx.register_hook("pre_llm_call", pre_llm_call)
    ctx.register_skill("celine-companion", Path(__file__).parent / "skill")


__all__ = ["handle_presence", "handle_pulse", "handle_relationship", "pre_llm_call", "register"]
