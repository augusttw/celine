from __future__ import annotations

import json
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

        # Extract structured information from history
        touched_files: set[str] = set()
        executed_commands: list[str] = []
        user_intents: list[str] = []
        assistant_notes: list[str] = []

        for msg in history_to_compact:
            role = msg.get("role", "")
            content = (msg.get("content") or "").strip()

            if role == "user" and content:
                # Capture the core intent
                clean_intent = " ".join(content.split())
                user_intents.append(clean_intent[:180])

            elif role == "assistant":
                # Check tool calls
                if "tool_calls" in msg and isinstance(msg["tool_calls"], list):
                    for call in msg["tool_calls"]:
                        fn = call.get("function", {})
                        fn_name = fn.get("name", "")
                        raw_args = fn.get("arguments", "")
                        try:
                            args = json.loads(raw_args) if isinstance(raw_args, str) and raw_args.strip() else (raw_args if isinstance(raw_args, dict) else {})
                        except Exception:
                            args = {}

                        if fn_name in {"read_file", "edit_file", "write_file"} and "path" in args:
                            touched_files.add(str(args["path"]))
                        elif fn_name == "bash" and "command" in args:
                            cmd_snippet = str(args["command"]).strip()
                            if cmd_snippet and len(executed_commands) < 15:
                                executed_commands.append(cmd_snippet[:100])
                if content:
                    assistant_notes.append(content[:160].replace("\n", " "))

            elif role == "tool":
                # Check if tool output contained an error
                if "Erro" in content or "error" in content.lower() or "[Código de saída:" in content:
                    first_line = content.splitlines()[0] if content else ""
                    if first_line:
                        assistant_notes.append(f"[Aviso ferramenta]: {first_line[:120]}")

        summary_lines = ["[Resumo estruturado de contexto anterior compilado automaticamente]:"]

        if user_intents:
            summary_lines.append("\n**Objetivos do usuário abordados:**")
            for intent in user_intents[-6:]:
                summary_lines.append(f"- {intent}")

        if touched_files:
            summary_lines.append("\n**Arquivos inspecionados / alterados:**")
            for f in sorted(touched_files)[:12]:
                summary_lines.append(f"- `{f}`")

        if executed_commands:
            summary_lines.append("\n**Comandos shell executados:**")
            for cmd in executed_commands[-8:]:
                summary_lines.append(f"- `{cmd}`")

        if assistant_notes:
            summary_lines.append("\n**Notas de progresso:**")
            for note in assistant_notes[-6:]:
                summary_lines.append(f"- {note}")

        summary_msg = {"role": "system", "content": "\n".join(summary_lines)}

        new_messages = []
        if system_msg:
            new_messages.append(system_msg)
        new_messages.append(summary_msg)
        new_messages.extend(recent_history)

        return new_messages
