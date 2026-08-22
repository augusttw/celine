from __future__ import annotations

import json
from typing import Any, Iterator

from openai import OpenAI

from celine.providers.base import (
    BaseProvider,
    LLMResponse,
    StreamChunk,
    ToolCall,
    ToolCallChunk,
)


class OpenAIProvider(BaseProvider):
    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        default_model: str = "gpt-5.6-luna",
        timeout: float = 120.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.default_model = default_model
        self.timeout = timeout

        kwargs: dict[str, Any] = {
            "api_key": api_key,
            "timeout": timeout,
        }
        if base_url:
            kwargs["base_url"] = base_url
            if "integrate.api.nvidia.com" in base_url:
                kwargs["default_headers"] = {"User-Agent": "Celine-Agent/0.2.0"}

        self.client = OpenAI(**kwargs)

    def _prepare_payload(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        stream: bool = True,
    ) -> dict[str, Any]:
        target_model = model or self.default_model

        payload: dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "stream": stream,
        }

        # Temperature: reasoning models don't support custom temp
        if not ("o1" in target_model or "o3" in target_model):
            payload["temperature"] = temperature

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        return payload

    def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> Iterator[StreamChunk]:
        target_model = model or self.default_model
        payload = self._prepare_payload(messages, tools, target_model, temperature, stream=True)

        try:
            response_stream = self.client.chat.completions.create(**payload)
        except Exception as exc:
            err_str = str(exc)
            # If failed because tools are unsupported or route not found with tools, retry without tools
            if tools and any(k in err_str.lower() for k in ["tools", "tool_choice", "function", "not found", "400", "404"]):
                payload_no_tools = self._prepare_payload(messages, None, target_model, temperature, stream=True)
                try:
                    response_stream = self.client.chat.completions.create(**payload_no_tools)
                except Exception as inner_exc:
                    self._handle_api_error(inner_exc, target_model)
            else:
                self._handle_api_error(exc, target_model)

        for chunk in response_stream:
            if not chunk.choices:
                continue

            choice = chunk.choices[0]
            delta = choice.delta
            finish_reason = choice.finish_reason

            text_delta = delta.content or ""
            thinking_delta = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None) or ""

            tool_chunks: list[ToolCallChunk] = []
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    tc_index = getattr(tc, "index", 0)
                    tc_id = getattr(tc, "id", None)
                    tc_fn = getattr(tc, "function", None)
                    fn_name = getattr(tc_fn, "name", None) if tc_fn else None
                    fn_args = getattr(tc_fn, "arguments", "") if tc_fn else ""
                    tool_chunks.append(
                        ToolCallChunk(
                            index=tc_index,
                            id=tc_id,
                            name=fn_name,
                            arguments=fn_args or "",
                        )
                    )

            yield StreamChunk(
                text=text_delta,
                thinking=str(thinking_delta),
                tool_calls=tool_chunks,
                finish_reason=finish_reason,
                raw=chunk,
            )

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        target_model = model or self.default_model
        payload = self._prepare_payload(messages, tools, target_model, temperature, stream=False)

        try:
            response = self.client.chat.completions.create(**payload)
        except Exception as exc:
            err_str = str(exc)
            if tools and any(k in err_str.lower() for k in ["tools", "tool_choice", "function", "not found", "400", "404"]):
                payload_no_tools = self._prepare_payload(messages, None, target_model, temperature, stream=False)
                try:
                    response = self.client.chat.completions.create(**payload_no_tools)
                except Exception as inner_exc:
                    self._handle_api_error(inner_exc, target_model)
            else:
                self._handle_api_error(exc, target_model)

        choice = response.choices[0]
        msg = choice.message
        content = msg.content or ""
        thinking = getattr(msg, "reasoning_content", None) or getattr(msg, "reasoning", None) or ""

        tool_calls: list[ToolCall] = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=tc.function.arguments,
                    )
                )

        usage_dict: dict[str, int] = {}
        if response.usage:
            usage_dict = {
                "prompt_tokens": response.usage.prompt_tokens or 0,
                "completion_tokens": response.usage.completion_tokens or 0,
                "total_tokens": response.usage.total_tokens or 0,
            }

        return LLMResponse(
            content=content,
            thinking=str(thinking) if thinking else "",
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason,
            usage=usage_dict,
        )

    def _handle_api_error(self, exc: Exception, model_name: str) -> None:
        err_msg = str(exc)
        if "not found for account" in err_msg.lower() or "function" in err_msg.lower() and "404" in err_msg:
            raise RuntimeError(
                f"O modelo '{model_name}' não está ativo na sua conta NVIDIA Build ou requer aceitar os termos em https://build.nvidia.com/.\n"
                f"👉 Dica: Troque para um modelo ativo com: /model meta/llama-3.1-70b-instruct ou /model meta/llama-3.1-8b-instruct"
            ) from exc
        raise exc
