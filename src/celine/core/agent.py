from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator

from celine.config import CelineConfig
from celine.core.context import ContextManager
from celine.core.persona import persona_manager
from celine.core.session import SessionManager
from celine.providers.base import BaseProvider
from celine.providers.router import ProviderRouter
from celine.tools.registry import registry


@dataclass
class AgentEvent:
    type: str
    content: str = ""
    tool_name: str = ""
    tool_args: str = ""
    tool_result: str = ""
    error: str = ""


class CelineAgent:
    """Self-contained Celine agent loop; it never imports or launches Hermes."""

    def __init__(self, config: CelineConfig, session_manager: SessionManager | None = None) -> None:
        self.config = config
        self.session_manager = session_manager or SessionManager()
        self.context_manager = ContextManager(
            limit=config.agent.context_limit,
            threshold=config.agent.compaction_threshold,
        )
        self.active_session_id = self.session_manager.get_or_create_active_session()
        self._provider: BaseProvider = ProviderRouter.get_provider(config)

    def switch_model(self, model_name: str) -> None:
        self.config.model.default = model_name
        self._provider = ProviderRouter.get_provider(self.config)

    def switch_provider(self, provider_name: str, base_url: str | None = None) -> None:
        previous = (self.config.model.provider, self.config.model.base_url, self._provider)
        try:
            self.config.model.provider = provider_name
            if base_url:
                self.config.model.base_url = base_url
            self._provider = ProviderRouter.get_provider(self.config)
        except Exception:
            self.config.model.provider, self.config.model.base_url, self._provider = previous
            raise

    def run_turn_stream(self, user_input: str) -> Iterator[AgentEvent]:
        self.session_manager.save_message(self.active_session_id, "user", user_input)
        system_prompt = persona_manager.build_system_prompt()
        history = self.session_manager.get_messages(self.active_session_id, limit=40)
        messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}, *history]
        if self.context_manager.should_compact(messages):
            messages = self.context_manager.compact(messages)

        for _ in range(self.config.agent.max_turns):
            assistant_text = ""
            tool_calls: dict[int, dict[str, str]] = {}
            try:
                for chunk in self._provider.stream_chat(
                    messages=messages,
                    tools=registry.get_schemas(),
                    model=self.config.model.default,
                    temperature=self.config.model.temperature,
                ):
                    if chunk.text:
                        assistant_text += chunk.text
                        yield AgentEvent(type="text_delta", content=chunk.text)
                    if chunk.thinking:
                        yield AgentEvent(type="thinking_delta", content=chunk.thinking)
                    for call in chunk.tool_calls:
                        item = tool_calls.setdefault(
                            call.index,
                            {"id": call.id or f"call_{call.index}", "name": "", "arguments": ""},
                        )
                        if call.id:
                            item["id"] = call.id
                        if call.name:
                            item["name"] += call.name
                        item["arguments"] += call.arguments
            except Exception as exc:
                yield AgentEvent(type="error", error=f"Erro na comunicação com o modelo: {exc}")
                return

            if not tool_calls:
                self.session_manager.save_message(self.active_session_id, "assistant", assistant_text)
                yield AgentEvent(type="turn_complete", content=assistant_text)
                return

            parsed = [
                {
                    "id": item["id"],
                    "type": "function",
                    "function": {"name": item["name"], "arguments": item["arguments"]},
                }
                for _, item in sorted(tool_calls.items())
            ]
            messages.append({"role": "assistant", "content": assistant_text or None, "tool_calls": parsed})
            self.session_manager.save_message(
                self.active_session_id, "assistant", assistant_text, tool_calls=parsed
            )
            for call in parsed:
                name = call["function"]["name"]
                arguments = call["function"]["arguments"]
                yield AgentEvent(type="tool_start", tool_name=name, tool_args=arguments)
                result = registry.execute(name, arguments)
                yield AgentEvent(type="tool_end", tool_name=name, tool_args=arguments, tool_result=result)
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})
                self.session_manager.save_message(
                    self.active_session_id, "tool", result, tool_call_id=call["id"], name=name
                )

        yield AgentEvent(type="turn_complete", content="[Limite máximo de iterações atingido.]")

    def run_turn(self, user_input: str) -> str:
        output = ""
        for event in self.run_turn_stream(user_input):
            if event.type == "text_delta":
                output += event.content
            elif event.type == "error":
                raise RuntimeError(event.error)
        return output
