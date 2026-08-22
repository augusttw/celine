from __future__ import annotations

from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text

from celine.config import CelineConfig
from celine.ui.theme import COLORS


def render_banner(console: Console, config: CelineConfig, session_id: str, voice_enabled: bool) -> None:
    short_session = session_id[-8:] if len(session_id) > 8 else session_id
    voice_label = "voz ativa" if voice_enabled else "voz silenciosa"

    welcome = Text("Estou aqui. O que vamos construir?", style=COLORS["text"])
    details = Text()
    details.append(config.model.default, style=f"bold {COLORS['subtext']}")
    details.append("   ·   ", style=COLORS["surface"])
    details.append(config.model.provider, style=COLORS["subtext"])
    details.append("   ·   ", style=COLORS["surface"])
    details.append(voice_label, style=COLORS["overlay"])

    panel = Panel(
        Group(welcome, details),
        title=f"[bold {COLORS['pink']}]  celine  [/][{COLORS['mauve']}]♡  [/]",
        title_align="left",
        subtitle=f"[{COLORS['overlay']}]  sessão · {short_session}  [/]",
        subtitle_align="right",
        border_style=COLORS["surface"],
        box=box.ROUNDED,
        padding=(0, 2),
    )
    console.print()
    console.print(panel)


def render_welcome_tips(console: Console) -> None:
    tips = (
        f"  [{COLORS['overlay']}]atalhos[/]  "
        f"[{COLORS['pink']}]/help[/]  [{COLORS['pink']}]/model[/]  "
        f"[{COLORS['pink']}]/provider[/]  [{COLORS['pink']}]/session[/]  "
        f"[{COLORS['pink']}]/memory[/]  [{COLORS['pink']}]/retry[/]  "
        f"[{COLORS['pink']}]/exit[/]"
    )
    console.print(tips)
    console.print(f"  [{COLORS['overlay']}]tab completa  ·  ↑ histórico  ·  ctrl-c interrompe[/]")
    console.print()
