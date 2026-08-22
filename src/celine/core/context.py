from __future__ import annotations

from typing import Any


def estimate_tokens(messages: list[dict[str, Any]]) -> int:
    """Rough token estimator: ~4 characters per token."""
    total_chars = 0
    for msg in messages:
        content = msg.get("content") or ""
        total_chars += len(content)
        if "tool_calls" in msg and msg["tool_calls"]:
            total_chars += len(str(msg["tool_calls"]))
    return max(1, total_chars // 4)


class ContextManager:
    def __init__(self, limit: int = 40000, threshold: float = 0.85) -> None:
        self.limit = limit
        self.threshold = threshold

    def should_compact(self, messages: list[dict[str, Any]]) -> bool:
        est = estimate_tokens(messages)
        return est > (self.limit * self.threshold)

    def compact(self, messages: list[dict[str, Any]], preserve_last_n: int = 10) -> list[dict[str, Any]]:
        """Compact older messages while preserving system prompt and recent turns."""
        if len(messages) <= preserve_last_n + 1:
            return messages

        system_msg = messages[0] if messages and messages[0].get("role") == "system" else None
        history_to_compact = messages[1:-preserve_last_n] if system_msg else messages[:-preserve_last_n]
        recent_history = messages[-preserve_last_n:]

        # Create quick executive summary of older exchanges
        summary_lines = ["[Resumo automático de mensagens anteriores]:"]
        for msg in history_to_compact:
            role = msg.get("role", "")
            content = (msg.get("content") or "").strip()
            if role in {"user", "assistant"} and content:
                snippet = content[:120].replace("\n", " ")
                summary_lines.append(f"- {role.capitalize()}: {snippet}...")

        summary_msg = {"role": "system", "content": "\n".join(summary_lines)}

        new_messages = []
        if system_msg:
            new_messages.append(system_msg)
        new_messages.append(summary_msg)
        new_messages.extend(recent_history)

        return new_messages
