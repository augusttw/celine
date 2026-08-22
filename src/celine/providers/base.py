from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Iterator


@dataclass
class ToolCallChunk:
    index: int
    id: str | None = None
    name: str | None = None
    arguments: str = ""


@dataclass
class StreamChunk:
    text: str = ""
    thinking: str = ""
    tool_calls: list[ToolCallChunk] = field(default_factory=list)
    finish_reason: str | None = None
    raw: Any = None


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass
class LLMResponse:
    content: str = ""
    thinking: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str | None = None
    usage: dict[str, int] = field(default_factory=dict)


class BaseProvider(ABC):
    @abstractmethod
    def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> Iterator[StreamChunk]:
        """Stream response tokens and tool call chunks from LLM."""
        pass

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Non-streaming completion."""
        pass
