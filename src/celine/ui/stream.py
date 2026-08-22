from __future__ import annotations

from typing import Iterator

from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from celine.core.agent import AgentEvent
from celine.ui.formatting import render_tool_call, render_tool_result
from celine.ui.theme import COLORS


def _bubble(content: str, *, title: str, border: str, empty: str = "▌") -> Panel:
    body = Markdown(content) if content.strip() else Text(empty, style=COLORS["overlay"])
    return Panel(
        body,
        title=f"[bold {COLORS['pink']}]  {title}  [/]",
        title_align="left",
        border_style=border,
        padding=(0, 2),
        expand=True,
    )


def stream_agent_events(console: Console, event_stream: Iterator[AgentEvent], show_tool_details: bool = True) -> str:
    """Render a complete Celine conversation with live speech bubbles."""
    accumulated_text = ""
    thinking_ticks = 0
    thinking_frames = ("pensando…", "pensando..", "pensando...")
    console.print()
    with Live(
        _bubble("", title="celine  ·  pensando…", border=COLORS["mauve"], empty=thinking_frames[0]),
        console=console,
        refresh_per_second=12,
        transient=False,
    ) as live:
        for event in event_stream:
            if event.type == "text_delta":
                accumulated_text += event.content or ""
                live.update(_bubble(accumulated_text, title="celine  ♡", border=COLORS["surface"]))
            elif event.type == "thinking_delta" and not accumulated_text:
                thinking_ticks += 1
                frame = thinking_frames[thinking_ticks % len(thinking_frames)]
                live.update(_bubble("", title=f"celine  ·  {frame}", border=COLORS["mauve"], empty=frame))
            elif event.type == "tool_start":
                live.update(
                    _bubble(
                        accumulated_text,
                        title="celine  ·  trabalhando",
                        border=COLORS["teal"],
                        empty="preparando…",
                    )
                )
                console.print()
                render_tool_call(console, event.tool_name, event.tool_args)
            elif event.type == "tool_end" and show_tool_details and event.tool_result:
                render_tool_result(console, event.tool_name, event.tool_result)
            elif event.type == "error":
                live.update(_bubble(event.error, title="celine  ·  erro", border=COLORS["red"]))
            elif event.type == "turn_complete":
                if event.content and not accumulated_text:
                    accumulated_text = event.content
                live.update(_bubble(accumulated_text, title="celine  ♡", border=COLORS["surface"]))

    console.print(f"  [{COLORS['overlay']}]concluído  ·  ctrl-c interrompe o turno[/]")
    return accumulated_text


def render_user_message(console: Console, content: str) -> None:
    """Render the user's turn as the companion bubble above the answer."""
    console.print(_bubble(content, title="você", border=COLORS["surface"]))
