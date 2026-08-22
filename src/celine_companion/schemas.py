from __future__ import annotations

COLLECTION_ENUM = ["moments", "milestones", "important_dates", "interaction_preferences", "active_threads"]

CELINE_RELATIONSHIP_SCHEMA = {
    "name": "celine_relationship",
    "description": (
        "Memória relacional privada, versionada e auditável. Escritas exigem consentimento; nunca armazene segredos."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "status",
                    "create",
                    "update",
                    "list",
                    "remove",
                    "search",
                    "export",
                    "set_state",
                    "add_moment",
                    "list_moments",
                    "remove_moment",
                ],
            },
            "collection": {"type": "string", "enum": COLLECTION_ENUM},
            "item_id": {"type": "string"},
            "moment_id": {"type": "string"},
            "text": {"type": "string", "maxLength": 1000},
            "query": {"type": "string", "maxLength": 200},
            "significance": {"type": "string", "enum": ["small", "normal", "important"], "default": "normal"},
            "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
            "date": {"type": "string", "description": "Data ISO para datas importantes."},
            "provenance": {"type": "string", "maxLength": 80},
            "field": {
                "type": "string",
                "enum": ["shared_focus", "connection_note", "check_in_style", "expressive_mood"],
            },
            "value": {"type": "string", "maxLength": 300},
            "format": {"type": "string", "enum": ["json", "markdown"], "default": "json"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10},
        },
        "required": ["action"],
        "additionalProperties": False,
    },
}

CELINE_PULSE_SCHEMA = {
    "name": "celine_pulse",
    "description": (
        "Controla check-ins opt-in. Nunca envia por conta própria; record_checkin só após um check-in efetivo."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["status", "configure", "due", "snooze", "record_checkin", "suggest"]},
            "enabled": {"type": "boolean"},
            "desktop_notifications": {"type": "boolean"},
            "cadence_hours": {"type": "integer", "minimum": 1, "maximum": 720},
            "quiet_hours_start": {"type": "integer", "minimum": 0, "maximum": 23},
            "quiet_hours_end": {"type": "integer", "minimum": 0, "maximum": 23},
            "cooldown_hours": {"type": "integer", "minimum": 1, "maximum": 720},
            "max_daily": {"type": "integer", "minimum": 0, "maximum": 10},
            "preferred_topics": {"type": "array", "items": {"type": "string"}, "maxItems": 12},
            "hours": {"type": "integer", "minimum": 1, "maximum": 720},
            "topic": {"type": "string", "maxLength": 80},
        },
        "required": ["action"],
        "additionalProperties": False,
    },
}

CELINE_PRESENCE_SCHEMA = {
    "name": "celine_presence",
    "description": (
        "Consulta a presença desktop/gateway da Celine ou envia uma notificação desktop explicitamente solicitada. "
        "Nunca revela tokens e nunca configura canais automaticamente."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["status", "notify"]},
            "origin": {"type": "string", "enum": ["manual", "proactive"], "default": "manual"},
            "title": {"type": "string", "maxLength": 80},
            "message": {"type": "string", "maxLength": 500},
        },
        "required": ["action"],
        "additionalProperties": False,
    },
}
