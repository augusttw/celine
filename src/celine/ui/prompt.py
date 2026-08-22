from __future__ import annotations

from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style

from celine.config import CELINE_HOME

SLASH_COMMANDS = [
    "/help",
    "/clear",
    "/model",
    "/model 1",
    "/model 2",
    "/model 3",
    "/provider",
    "/provider list",
    "/provider add",
    "/provider remove",
    "/provider set-key",
    "/voice",
    "/voice on",
    "/voice off",
    "/memory",
    "/memory list",
    "/memory add",
    "/memory clear",
    "/profile",
    "/soul",
    "/soul view",
    "/soul reload",
    "/session",
    "/session new",
    "/session list",
    "/skills",
    "/skills list",
    "/compact",
    "/status",
    "/exit",
    "/quit",
]

PROMPT_STYLE = Style.from_dict(
    {
        "prompt": "#e69ab3 bold",
        "command": "#d0b27a",
        "completion-menu.completion": "bg:#171419 #ddd7dc",
        "completion-menu.completion.current": "bg:#312a33 #e69ab3 bold",
        "auto-suggestion": "#766e78 italic",
    }
)


def create_prompt_session() -> PromptSession:
    CELINE_HOME.mkdir(parents=True, exist_ok=True)
    history_file = CELINE_HOME / "input.history"

    completer = WordCompleter(
        SLASH_COMMANDS,
        ignore_case=True,
        sentence=False,
    )

    return PromptSession(
        history=FileHistory(str(history_file)),
        auto_suggest=AutoSuggestFromHistory(),
        completer=completer,
        style=PROMPT_STYLE,
        enable_history_search=True,
    )


def get_prompt_text() -> HTML:
    return HTML("<ansimagenta>você</ansimagenta> <ansibrightblack>›</ansibrightblack> ")
