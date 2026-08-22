from __future__ import annotations

from rich.style import Style
from rich.theme import Theme

# Celine signature palette: soft ink, dusty rose and quiet mineral accents.
# It is intentionally restrained so long sessions stay comfortable to read.
COLORS = {
    "pink": "#e69ab3",
    "mauve": "#aa91b7",
    "lavender": "#9e9bd1",
    "sapphire": "#819fbe",
    "sky": "#84b7bd",
    "teal": "#82b9ac",
    "green": "#96b995",
    "yellow": "#d0b27a",
    "peach": "#d7a080",
    "maroon": "#c58a98",
    "red": "#d67f8b",
    "text": "#ddd7dc",
    "subtext": "#aaa1aa",
    "overlay": "#766e78",
    "surface": "#312a33",
    "base": "#171419",
    "crust": "#0f0d11",
}

CELINE_THEME = Theme(
    {
        "celine.title": Style(color=COLORS["pink"], bold=True),
        "celine.subtitle": Style(color=COLORS["lavender"], italic=True),
        "celine.border": Style(color=COLORS["mauve"]),
        "celine.user": Style(color=COLORS["pink"], bold=True),
        "celine.assistant": Style(color=COLORS["pink"], bold=True),
        "celine.tool": Style(color=COLORS["sky"], bold=True),
        "celine.tool_result": Style(color=COLORS["text"]),
        "celine.memory": Style(color=COLORS["yellow"]),
        "celine.error": Style(color=COLORS["red"], bold=True),
        "celine.dim": Style(color=COLORS["overlay"]),
        "celine.success": Style(color=COLORS["green"]),
        "celine.highlight": Style(color=COLORS["peach"], bold=True),
    }
)
