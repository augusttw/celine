from __future__ import annotations

import inspect
import json
import types
from dataclasses import dataclass
from typing import Any, Callable, Union, get_args, get_origin, get_type_hints


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
            origin = get_origin(param_type)
            args = get_args(param_type)
            if origin in {types.UnionType, Union}:
                non_none = [item for item in args if item is not type(None)]
                param_type = non_none[0] if len(non_none) == 1 else str
                origin = get_origin(param_type)
            json_type = "string"
            if param_type in (int, float):
                json_type = "number" if param_type is float else "integer"
            elif param_type is bool:
                json_type = "boolean"
            elif param_type in (list, tuple) or origin in (list, tuple):
                json_type = "array"
            elif param_type is dict or origin is dict:
                json_type = "object"

            prop_schema: dict[str, Any] = {"type": json_type}
            if json_type == "array":
                item_type = get_args(param_type)[0] if get_args(param_type) else str
                prop_schema["items"] = {"type": "integer" if item_type is int else "string"}
            if param.default is not inspect.Parameter.empty and param.default is not None:
                prop_schema["default"] = param.default
            properties[param_name] = prop_schema

            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        parameters = {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
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
