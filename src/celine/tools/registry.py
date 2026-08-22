from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from typing import Any, Callable, get_type_hints


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    func: Callable[..., Any]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, func: Callable[..., Any], name: str | None = None, description: str | None = None) -> Callable[..., Any]:
        fn_name = name or func.__name__
        doc = description or (inspect.getdoc(func) or f"Execute {fn_name}")

        sig = inspect.signature(func)
        type_hints = get_type_hints(func)

        properties: dict[str, Any] = {}
        required: list[str] = []

        for param_name, param in sig.parameters.items():
            if param_name in {"self", "cls"}:
                continue

            param_type = type_hints.get(param_name, str)
            json_type = "string"
            if param_type in (int, float):
                json_type = "number" if param_type is float else "integer"
            elif param_type is bool:
                json_type = "boolean"
            elif param_type in (list, tuple) or getattr(param_type, "__origin__", None) in (list, tuple):
                json_type = "array"
            elif param_type is dict or getattr(param_type, "__origin__", None) is dict:
                json_type = "object"

            prop_schema: dict[str, Any] = {"type": json_type}
            
            # Extract doc from param if docstring follows google/sphinx format
            properties[param_name] = prop_schema

            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        parameters = {
            "type": "object",
            "properties": properties,
            "required": required,
        }

        self._tools[fn_name] = ToolDefinition(
            name=fn_name,
            description=doc,
            parameters=parameters,
            func=func,
        )
        return func

    def get_schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in self._tools.values()
        ]

    def execute(self, name: str, arguments: str | dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if not tool:
            return f"Erro: ferramenta '{name}' não encontrada."

        if isinstance(arguments, str):
            try:
                args_dict = json.loads(arguments) if arguments.strip() else {}
            except Exception as e:
                return f"Erro ao decodificar argumentos JSON para {name}: {e}"
        else:
            args_dict = arguments

        try:
            result = tool.func(**args_dict)
            if isinstance(result, str):
                return result
            return json.dumps(result, ensure_ascii=False, indent=2)
        except Exception as exc:
            return f"Erro executando ferramenta '{name}': {exc}"


# Global tool registry
registry = ToolRegistry()


def tool(name: str | None = None, description: str | None = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        registry.register(func, name=name, description=description)
        return func

    return decorator
