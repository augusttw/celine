from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from celine.config import CelineConfig
from celine.ui.theme import COLORS


def _detect_lexer(path_str: str) -> str:
    ext = Path(path_str).suffix.lower()
    mapping = {
        ".py": "python",
        ".rs": "rust",
        ".go": "go",
        ".ts": "typescript",
        ".js": "javascript",
        ".tsx": "tsx",
        ".jsx": "jsx",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".md": "markdown",
        ".sh": "bash",
        ".bash": "bash",
        ".fish": "fish",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".css": "css",
        ".html": "html",
        ".sql": "sql",
    }
    return mapping.get(ext, "text")


def render_tool_call(console: Console, tool_name: str, tool_args: str) -> None:
    try:
        parsed = json.loads(tool_args) if isinstance(tool_args, str) else tool_args
    except Exception:
        parsed = {}

    marker = f"[{COLORS['overlay']}]╰[/] [bold {COLORS['teal']}]◆[/]"

    if tool_name == "bash":
        cmd = parsed.get("command", tool_args)
        console.print(f"  {marker} [bold {COLORS['teal']}]terminal[/]  [{COLORS['subtext']}]{cmd}[/]")

    elif tool_name in {"read_file", "view_file"}:
        path = parsed.get("path") or parsed.get("AbsolutePath", "")
        start = parsed.get("start_line", parsed.get("StartLine", 1))
        end = parsed.get("end_line", parsed.get("EndLine", 500))
        console.print(
            f"  {marker} [bold {COLORS['teal']}]leitura[/]  "
            f"[{COLORS['text']}]{path}[/] [{COLORS['overlay']}]· {start}–{end}[/]"
        )

    elif tool_name in {"write_file", "write_to_file"}:
        path = parsed.get("path") or parsed.get("TargetFile", "")
        console.print(f"  {marker} [bold {COLORS['teal']}]escrita[/]  [{COLORS['text']}]{path}[/]")

    elif tool_name in {"edit_file", "replace_file_content"}:
        path = parsed.get("path") or parsed.get("TargetFile", "")
        console.print(f"  {marker} [bold {COLORS['teal']}]edição[/]  [{COLORS['text']}]{path}[/]")

    elif tool_name == "read_skill":
        skill_name = parsed.get("skill_name", "")
        console.print(f"  {marker} [bold {COLORS['teal']}]skill[/]  [{COLORS['text']}]{skill_name}[/]")

    elif tool_name == "list_skills":
        console.print(f"  {marker} [bold {COLORS['teal']}]skills[/]  [{COLORS['subtext']}]consultando habilidades[/]")

    elif tool_name == "web_search":
        query = parsed.get("query", "")
        console.print(f"  {marker} [bold {COLORS['teal']}]pesquisa[/]  [{COLORS['text']}]{query}[/]")

    elif tool_name == "remember":
        fact = parsed.get("fact", "")
        console.print(f"  {marker} [bold {COLORS['teal']}]memória[/]  [{COLORS['text']}]{fact}[/]")

    else:
        args_display = tool_args[:80] + ("…" if len(tool_args) > 80 else "")
        console.print(
            f"  {marker} [bold {COLORS['teal']}]{tool_name.replace('_', ' ')}[/]  "
            f"[{COLORS['subtext']}]{args_display}[/]"
        )


def render_tool_result(console: Console, tool_name: str, result: str, max_lines: int = 16) -> None:
    if not result:
        return

    if tool_name == "bash":
        lines = result.splitlines()
        preview = "\n".join(lines[:max_lines])
        if len(lines) > max_lines:
            preview += f"\n... [mais {len(lines) - max_lines} linhas]"

        syntax = Syntax(preview, "bash", theme="monokai", line_numbers=False, word_wrap=True)
        panel = Panel(
            syntax,
            title=f"[{COLORS['teal']}]  saída  [/]",
            border_style=COLORS["surface"],
            padding=(0, 1),
        )
        console.print(panel)

    elif tool_name in {"read_file", "view_file"}:
        lines = result.splitlines()
        preview = "\n".join(lines[:max_lines])
        if len(lines) > max_lines:
            preview += f"\n... [{len(lines) - max_lines} linhas adicionais]"

        panel = Panel(
            preview,
            title=f"[{COLORS['teal']}]  conteúdo  [/]",
            border_style=COLORS["surface"],
            padding=(0, 1),
        )
        console.print(panel)

    elif tool_name in {"edit_file", "replace_file_content"}:
        console.print(f"    [{COLORS['green']}]feito  ·  alteração aplicada[/]")

    elif tool_name == "read_skill":
        lines = result.splitlines()
        header = lines[0] if lines else "Instruções da Skill"
        console.print(
            Panel(
                f"[bold {COLORS['mauve']}]{header}[/]\n\n" + "\n".join(lines[1:7]) + ("\n..." if len(lines) > 7 else ""),
                title=f"[{COLORS['mauve']}]  skill carregada  [/]",
                border_style=COLORS["surface"],
                padding=(0, 1),
            )
        )

    elif tool_name == "remember":
        console.print(f"    [{COLORS['green']}]feito[/]  [{COLORS['subtext']}]{result}[/]")

    elif tool_name == "web_search":
        lines = result.splitlines()
        preview = "\n".join(lines[:10])
        if len(lines) > 10:
            preview += f"\n... [{len(lines) - 10} linhas adicionais]"
        console.print(
            Panel(
                preview,
                title=f"[{COLORS['lavender']}]  resultados  [/]",
                border_style=COLORS["surface"],
                padding=(0, 1),
            )
        )

    else:
        lines = result.splitlines()
        preview = "\n".join(lines[:max_lines])
        if len(lines) > max_lines:
            preview += f"\n... [{len(lines) - max_lines} linhas]"
        console.print(
            Panel(
                preview,
                title=f"[{COLORS['sky']}]{tool_name}[/]",
                border_style=COLORS["surface"],
                padding=(0, 1),
            )
        )


def render_help(console: Console) -> None:
    table = Table(
        title="[bold #f5c2e7]✦ Comandos da Celine[/]",
        border_style=COLORS["mauve"],
        header_style=f"bold {COLORS['pink']}",
        expand=True,
    )
    table.add_column("Comando", style=COLORS["yellow"], ratio=1)
    table.add_column("Argumentos", style=COLORS["subtext"], ratio=1)
    table.add_column("Descrição", style=COLORS["text"], ratio=2)

    commands = [
        ("/help", "", "Exibe esta ajuda com todos os comandos disponíveis."),
        ("/clear", "", "Limpa o terminal e redesenha o cabeçalho."),
        ("/model", "[1-N | nome]", "Exibe e permite escolher interativamente os modelos disponíveis."),
        ("/provider", "", "Exibe o provedor ativo."),
        ("/provider list", "", "Lista todos os provedores disponíveis (presets e customizados)."),
        ("/provider add", "<nome> <url> [key] [mod]", "Adiciona ou atualiza um provedor de IA (ex: NVIDIA NIM, Groq, Ollama)."),
        ("/provider remove", "<nome>", "Remove um provedor customizado."),
        ("/provider set-key", "<nome> <api_key>", "Salva chave de API em ~/.celine/auth.json."),
        ("/provider", "<nome>", "Troca o provedor ativo (ex: /provider nvidia, /provider deepseek)."),
        ("/voice", "[on|off|voice|rate]", "Ativa/desativa voz ou configura voz Edge-TTS e velocidade."),
        ("/memory", "[list|add|clear]", "Exibe, adiciona manualmente ou limpa memórias salvas."),
        ("/profile", "[view|edit]", "Visualiza ou atualiza o perfil do usuário (USER.md)."),
        ("/soul", "[view|edit|reload]", "Inspeciona ou recarrega a personalidade (SOUL.md)."),
        ("/session", "[list|new|switch|del]", "Gerencia conversas e sessões persistentes."),
        ("/skills", "[list|read]", "Lista ou lê habilidades disponíveis (ex: code-review, plan, devops)."),
        ("/compact", "", "Força compactação/resumo do histórico de conversa."),
        ("/status", "", "Exibe status detalhado do sistema, modelo, voz e recursos."),
        ("/exit ou /quit", "", "Encerra a sessão da Celine."),
    ]

    for cmd, args, desc in commands:
        table.add_row(cmd, args, desc)

    console.print(panel_wrap(table))


def render_models_table(
    console: Console,
    models: list[tuple[str, str]],
    active_model: str,
    provider_name: str,
) -> None:
    table = Table(
        title=f"[bold #f5c2e7]✦ Modelos Disponíveis · {provider_name}[/]",
        border_style=COLORS["mauve"],
        header_style=f"bold {COLORS['pink']}",
        expand=True,
    )
    table.add_column("#", style=COLORS["yellow"], width=5, justify="center")
    table.add_column("Nome do Modelo", style=COLORS["peach"], ratio=2)
    table.add_column("Descrição / Especialidade", style=COLORS["text"], ratio=3)
    table.add_column("Status", justify="center", width=10)

    for idx, (m_name, m_desc) in enumerate(models, 1):
        is_active = m_name.lower() == active_model.lower()
        status = f"[bold {COLORS['green']}]● ATIVO[/]" if is_active else f"[{COLORS['overlay']}]○[/]"
        table.add_row(f"[{idx}]", m_name, m_desc, status)

    console.print(table)
    console.print(
        f"[{COLORS['subtext']}]Para alternar:[/] [{COLORS['pink']}]/model <número>[/] ou [{COLORS['pink']}]/model <nome-do-modelo>[/]\n"
    )


def render_providers_table(
    console: Console,
    providers: list[dict[str, Any]],
    active_provider: str,
) -> None:
    table = Table(
        title="[bold #b4befe]✦ Provedores de IA Suportados[/]",
        border_style=COLORS["lavender"],
        header_style=f"bold {COLORS['pink']}",
        expand=True,
    )
    table.add_column("Provedor", style=COLORS["yellow"])
    table.add_column("Base URL", style=COLORS["subtext"])
    table.add_column("Modelo Padrão", style=COLORS["peach"])
    table.add_column("Tipo", style=COLORS["teal"])
    table.add_column("Status", justify="center")

    for p in providers:
        is_active = p["name"].lower() == active_provider.lower()
        status = f"[bold {COLORS['green']}]● ATIVO[/]" if is_active else f"[{COLORS['overlay']}]○[/]"
        table.add_row(
            p["name"],
            p["base_url"][:40] + ("..." if len(p["base_url"]) > 40 else ""),
            p["model"],
            p.get("type", "preset"),
            status,
        )

    console.print(table)
    console.print(
        f"[{COLORS['subtext']}]Para alternar: [{COLORS['pink']}]/provider <nome>[/] "
        f"| Para adicionar: [{COLORS['pink']}]/provider add <nome> <url> [api_key] [modelo][/][/]\n"
    )


def render_memories_table(console: Console, memories: list[str]) -> None:
    if not memories:
        console.print(f"[{COLORS['subtext']}](Nenhuma memória salva ainda.)[/]")
        return

    table = Table(
        title="[bold #f9e2af]🧠 Memórias de Longo Prazo da Celine[/]",
        border_style=COLORS["yellow"],
        header_style=f"bold {COLORS['peach']}",
        expand=True,
    )
    table.add_column("#", style=COLORS["subtext"], width=4)
    table.add_column("Memória", style=COLORS["text"])

    for i, mem in enumerate(memories, 1):
        table.add_row(str(i), mem)

    console.print(table)


def render_sessions_table(console: Console, sessions: list[dict[str, Any]], active_id: str) -> None:
    table = Table(
        title="[bold #cba6f7]📂 Sessões de Conversa[/]",
        border_style=COLORS["mauve"],
        header_style=f"bold {COLORS['pink']}",
        expand=True,
    )
    table.add_column("ID", style=COLORS["yellow"])
    table.add_column("Título", style=COLORS["text"])
    table.add_column("Mensagens", justify="right", style=COLORS["subtext"])
    table.add_column("Atualizada em", style=COLORS["subtext"])
    table.add_column("Status", justify="center")

    for s in sessions:
        is_active = s["id"] == active_id
        status = f"[bold {COLORS['green']}]● ATIVA[/]" if is_active else f"[{COLORS['overlay']}]○[/]"
        table.add_row(
            s["id"],
            s["title"],
            str(s["messages"]),
            s["updated_at"][:19].replace("T", " "),
            status,
        )

    console.print(table)


def render_status(
    console: Console,
    config: CelineConfig,
    memory_count: int,
    session_id: str,
    voice_enabled: bool,
) -> None:
    table = Table.grid(padding=(0, 2))
    table.add_column(style=f"bold {COLORS['pink']}")
    table.add_column(style=COLORS["text"])

    voice_status = f"[green]Ativada ({config.voice.voice}, {config.voice.rate})[/]" if voice_enabled else "[dim]Desativada[/]"

    table.add_row("Modelo Padrão:", config.model.default)
    table.add_row("Provedor:", config.model.provider)
    table.add_row("Base URL:", config.model.base_url)
    table.add_row("Sessão Ativa:", session_id)
    table.add_row("Memórias Salvas:", f"{memory_count} itens")
    table.add_row("Voz (Edge-TTS):", voice_status)
    table.add_row("Streaming:", "Sim" if config.agent.streaming else "Não")

    panel = Panel(
        table,
        title="[bold #f5c2e7]✦ Status da Celine[/]",
        border_style=COLORS["mauve"],
        padding=(1, 2),
    )
    console.print(panel)


def panel_wrap(renderable: Any) -> Panel:
    return Panel(renderable, border_style=COLORS["mauve"], padding=(0, 1))
