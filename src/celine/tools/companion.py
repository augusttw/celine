from __future__ import annotations

from typing import Any

from celine.tools.registry import tool
from celine.core.approvals import approval_manager, approval_payload
from celine_companion import handle_pulse, handle_relationship
from celine_companion.presence import handle_presence


@tool(
    name="celine_relationship",
    description=(
        "Reads or manages Celine's private relationship journal. Mutating actions require explicit user consent."
    ),
)
def celine_relationship(
    action: str,
    collection: str = "moments",
    text: str = "",
    query: str = "",
    item_id: str = "",
    significance: str = "normal",
    tags: list[str] | None = None,
    date: str = "",
    field: str = "",
    value: str = "",
    format: str = "json",
    limit: int = 10,
    consent: bool = False,
) -> str:
    mutating = {"create", "update", "remove", "set_state", "add_moment", "remove_moment"}
    if action in mutating and not consent:
        return "Consent required: ask the user whether this exact information should be stored, changed, or removed."
    args: dict[str, Any] = {
        "action": action,
        "collection": collection,
        "text": text,
        "query": query,
        "item_id": item_id,
        "significance": significance,
        "tags": tags or [],
        "field": field,
        "value": value,
        "format": format,
        "limit": limit,
        "provenance": "explicit-user-consent" if consent else "read-only",
    }
    if date:
        args["date"] = date
    return handle_relationship(args)


@tool(
    name="celine_pulse",
    description="Reads or configures opt-in check-ins with quiet hours, cooldown, snooze, and daily limits.",
)
def celine_pulse(
    action: str = "status",
    enabled: bool | None = None,
    desktop_notifications: bool | None = None,
    cadence_hours: int | None = None,
    quiet_hours_start: int | None = None,
    quiet_hours_end: int | None = None,
    cooldown_hours: int | None = None,
    max_daily: int | None = None,
    preferred_topics: list[str] | None = None,
    hours: int = 24,
    topic: str = "",
    consent: bool = False,
) -> str:
    if action in {"configure", "snooze", "record_checkin"} and not consent:
        return "Consent required: check-in settings and records change only after an explicit user request."
    args: dict[str, Any] = {"action": action}
    optional = {
        "enabled": enabled,
        "desktop_notifications": desktop_notifications,
        "cadence_hours": cadence_hours,
        "quiet_hours_start": quiet_hours_start,
        "quiet_hours_end": quiet_hours_end,
        "cooldown_hours": cooldown_hours,
        "max_daily": max_daily,
        "preferred_topics": preferred_topics,
    }
    args.update({key: value for key, value in optional.items() if value is not None})
    if action == "snooze":
        args["hours"] = hours
    if action == "record_checkin":
        args["topic"] = topic
    return handle_pulse(args)


@tool(
    name="celine_presence",
    description="Checks Celine's local presence or sends an explicitly requested desktop notification.",
)
def celine_presence(
    action: str = "status",
    title: str = "Celine",
    message: str = "",
    origin: str = "manual",
    consent: bool = False,
) -> str:
    if action == "notify" and not consent:
        return "Consent required: desktop notifications are visible external effects."
    if action == "notify":
        blocked = approval_manager.authorize(
            "desktop_notification",
            approval_payload("celine_presence", {"title": title, "message": message, "origin": origin}),
            "a desktop notification is a visible external effect",
        )
        if blocked:
            return blocked
    return handle_presence({"action": action, "title": title, "message": message, "origin": origin})
