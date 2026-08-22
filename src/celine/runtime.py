from __future__ import annotations

import os
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console
from rich.table import Table

# Importing the tool package registers Celine's built-in tools.
import celine.tools  # noqa: F401
from celine.config import (
    CELINE_HOME,
    KNOWN_PROVIDER_PRESETS,
    CelineConfig,
    assert_celine_boundary,
)
from celine.core.agent import CelineAgent
from celine.ui.banner import render_banner, render_welcome_tips
from celine.ui.prompt import create_prompt_session, get_prompt_text
from celine.ui.stream import stream_agent_events
from celine.ui.theme import COLORS
from celine.providers.catalog import ModelCatalog
from celine.core.memory import memory_manager


@dataclass
class CelineRuntime:
    config: CelineConfig
    agent: CelineAgent
    console: Console

    @classmethod
    def create(cls, *, console: Console | None = None) -> CelineRuntime:
        assert_celine_boundary()
        config = CelineConfig.load()
        return cls(config, CelineAgent(config), console or Console())

    def _raw_config(self) -> dict[str, Any]:
        path = CELINE_HOME / "config.yaml"
        if not path.exists():
            return {}
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}

    def _save_model_settings(self) -> None:
        """Persist only model settings, preserving every other profile field."""
        path = CELINE_HOME / "config.yaml"
        data = self._raw_config()
        model = data.setdefault("model", {})
        if not isinstance(model, dict):
            model = {}
            data["model"] = model
        model.update(
            {
                "provider": self.config.model.provider,
                "default": self.config.model.default,
                "base_url": self.config.model.base_url,
                "temperature": self.config.model.temperature,
            }
        )
        fd, raw_tmp = tempfile.mkstemp(prefix=".config.yaml.", dir=CELINE_HOME)
        tmp = Path(raw_tmp)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(tmp, 0o600)
            os.replace(tmp, path)
            os.chmod(path, 0o600)
        finally:
            tmp.unlink(missing_ok=True)

    def _custom_provider(self, name: str) -> Any | None:
        for provider in self.config.custom_providers:
            if provider.name.casefold() == name.casefold():
                return provider
        return None

    def _provider_names(self) -> list[str]:
        names = list(KNOWN_PROVIDER_PRESETS)
        names.extend(provider.name for provider in self.config.custom_providers)
        if self.config.model.provider.casefold() not in {name.casefold() for name in names}:
            names.insert(0, self.config.model.provider)
        return list(dict.fromkeys(names))

    def _model_options(self, *, refresh: bool = False) -> list[tuple[str, str]]:
        custom = self._custom_provider(self.config.model.provider)
        options = ModelCatalog().options(
            self.config.model.provider,
            self.config.model.base_url,
            refresh=refresh,
            custom_models=custom.models if custom else [],
            custom_model=custom.model if custom else "",
        )
        # Keep externally configured models selectable even when a provider's
        # curated catalog has not caught up with the provider API yet.
        if self.config.model.default and not any(
            name.casefold() == self.config.model.default.casefold() for name, _ in options
        ):
            options.insert(0, (self.config.model.default, "modelo ativo configurado"))
        if not options:
            options = [(self.config.model.default, "modelo ativo")]
        seen: set[str] = set()
        return [(name, desc) for name, desc in options if not (name.casefold() in seen or seen.add(name.casefold()))]

    def _show_providers(self) -> None:
        table = Table(title="celine  ·  provedores", expand=True, border_style=COLORS["surface"])
        table.add_column("#", width=4, justify="right")
        table.add_column("Provedor", style=COLORS["text"])
        table.add_column("Base URL", style=COLORS["subtext"])
        table.add_column("Status")
        for index, name in enumerate(self._provider_names(), 1):
            custom = self._custom_provider(name)
            base_url = custom.base_url if custom else KNOWN_PROVIDER_PRESETS.get(name, {}).get("base_url", "")
            active = name.casefold() == self.config.model.provider.casefold()
            status = f"[bold {COLORS['green']}]● ativo[/]" if active else f"[{COLORS['overlay']}]○[/]"
            table.add_row(str(index), name, base_url or "configurado", status)
        self.console.print(table)
        self.console.print("[dim]/provider <nome> troca o provedor ativo.[/]")

    def _show_models(self, *, refresh: bool = True) -> None:
        table = Table(
            title=f"celine  ·  modelos  ·  {self.config.model.provider}",
            expand=True,
            border_style=COLORS["surface"],
        )
        table.add_column("#", width=4, justify="right")
        table.add_column("Modelo", style=COLORS["text"])
        table.add_column("Descrição", style=COLORS["subtext"])
        table.add_column("Status")
        for index, (name, description) in enumerate(self._model_options(refresh=refresh), 1):
            active = name.casefold() == self.config.model.default.casefold()
            status = f"[bold {COLORS['green']}]● ativo[/]" if active else f"[{COLORS['overlay']}]○[/]"
            table.add_row(str(index), name, description, status)
        self.console.print(table)
        self.console.print("[dim]/model <número> ou /model <nome> troca o modelo e salva.[/]")

    def _show_sessions(self) -> None:
        sessions = self.agent.session_manager.list_sessions()
        table = Table(title="celine  ·  sessões", expand=True, border_style=COLORS["surface"])
        table.add_column("#", width=4, justify="right")
        table.add_column("Sessão", style=COLORS["text"])
        table.add_column("Mensagens", justify="right", style=COLORS["subtext"])
        table.add_column("Estado", style=COLORS["green"])
        for index, session in enumerate(sessions, 1):
            active = session["id"] == self.agent.active_session_id
            table.add_row(
                str(index),
                session["title"] or session["id"],
                str(session["messages"]),
                "ativa" if active else "",
            )
        self.console.print(table)
        self.console.print("[dim]/session new · /session switch <id|número> · /session del <id>[/]")

    def _handle_session(self, argument: str) -> None:
        parts = argument.split(maxsplit=1)
        action = parts[0].casefold() if parts else "list"
        value = parts[1].strip() if len(parts) > 1 else ""
        manager = self.agent.session_manager
        if action in {"list", "ls"}:
            self._show_sessions()
        elif action in {"new", "novo"}:
            self.agent.active_session_id = manager.create_session(value or "Nova conversa")
            self.console.print(f"[{COLORS['green']}]nova sessão ativa[/]  {self.agent.active_session_id}")
        elif action in {"switch", "usar"} and value:
            sessions = manager.list_sessions()
            chosen = next((item["id"] for item in sessions if item["id"] == value), "")
            if value.isdigit() and 1 <= int(value) <= len(sessions):
                chosen = sessions[int(value) - 1]["id"]
            if chosen:
                self.agent.active_session_id = chosen
                self.console.print(f"[{COLORS['green']}]sessão ativa[/]  {chosen}")
            else:
                self.console.print(f"[{COLORS['red']}]sessão não encontrada:[/] {value}")
                self._show_sessions()
        elif action in {"del", "delete", "apagar"} and value:
            if manager.delete_session(value):
                if value == self.agent.active_session_id:
                    self.agent.active_session_id = manager.create_session()
                self.console.print(f"[{COLORS['green']}]sessão removida[/]  {value}")
            else:
                self.console.print(f"[{COLORS['red']}]sessão não encontrada:[/] {value}")
        else:
            self._show_sessions()

    def _handle_memory(self, argument: str) -> None:
        parts = argument.split(maxsplit=1)
        action = parts[0].casefold() if parts else "list"
        value = parts[1].strip() if len(parts) > 1 else ""
        if action in {"list", "ls"}:
            memories = memory_manager.get_memories(30)
            if not memories:
                self.console.print(f"[{COLORS['overlay']}]nenhuma memória salva[/]")
            else:
                for memory in memories:
                    self.console.print(f"  [{COLORS['mauve']}]◆[/] [{COLORS['text']}]{memory}[/]")
        elif action in {"search", "buscar"} and value:
            matches = memory_manager.search_memories(value)
            for memory in matches:
                self.console.print(f"  [{COLORS['mauve']}]◆[/] [{COLORS['text']}]{memory}[/]")
            if not matches:
                self.console.print(f"[{COLORS['overlay']}]nenhuma memória encontrada[/]")
        elif action in {"add", "salvar"} and value:
            memory_manager.add_memory(value, category="manual")
            self.console.print(f"[{COLORS['green']}]memória salva[/]  revise com /memory list")
        elif action in {"clear", "apagar"} and value:
            deleted = memory_manager.delete_memory(value)
            self.console.print(f"[{COLORS['green']}]memórias removidas:[/] {deleted}")
        else:
            self.console.print("[dim]/memory list · /memory search <termo> · /memory add <texto> · /memory clear <termo>[/]")

    def _select_provider(self, name: str) -> None:
        custom = self._custom_provider(name)
        preset = KNOWN_PROVIDER_PRESETS.get(name.casefold(), {})
        if custom is None and not preset and name.casefold() != self.config.model.provider.casefold():
            self.console.print(f"[red]Provider não configurado:[/] {name}")
            self._show_providers()
            return
        previous = (self.config.model.provider, self.config.model.base_url, self.config.model.default)
        self.config.model.provider = custom.name if custom else name
        if custom:
            self.config.model.base_url = custom.base_url
            if custom.model:
                self.config.model.default = custom.model
        elif preset:
            self.config.model.base_url = preset["base_url"]
            if preset.get("default_model"):
                self.config.model.default = preset["default_model"]
        try:
            self.agent.switch_provider(self.config.model.provider, self.config.model.base_url)
            self._save_model_settings()
            self.console.print(
                f"[bold #a6e3a1]Provider ativo:[/] {self.config.model.provider} · {self.config.model.default}"
            )
        except Exception as exc:
            self.config.model.provider, self.config.model.base_url, self.config.model.default = previous
            self.console.print(f"[red]Não foi possível trocar provider:[/] {exc}")

    def _select_model(self, value: str) -> None:
        options = self._model_options(refresh=False)
        chosen = options[int(value) - 1][0] if value.isdigit() and 1 <= int(value) <= len(options) else value
        if not chosen or (not value.isdigit() and not any(name.casefold() == chosen.casefold() for name, _ in options)):
            self.console.print(f"[red]Modelo não encontrado:[/] {value}")
            self._show_models()
            return
        previous = self.config.model.default
        try:
            self.agent.switch_model(chosen)
            self.config.model.default = chosen
            self._save_model_settings()
            self.console.print(f"[bold #a6e3a1]Modelo ativo:[/] {chosen}")
        except Exception as exc:
            self.config.model.default = previous
            self.console.print(f"[red]Não foi possível trocar modelo:[/] {exc}")

    def _handle_command(self, prompt: str) -> bool:
        parts = prompt.split(maxsplit=1)
        command = parts[0].casefold()
        argument = parts[1].strip() if len(parts) > 1 else ""
        if command == "/provider":
            if not argument or argument.casefold() == "list":
                self._show_providers()
            else:
                self._select_provider(argument)
            return True
        if command == "/model":
            if not argument or argument.casefold() == "refresh":
                self._show_models(refresh=True)
            else:
                self._select_model(argument)
            return True
        if command == "/session":
            self._handle_session(argument)
            return True
        if command == "/memory":
            self._handle_memory(argument)
            return True
        return False

    def run_once(self, prompt: str, *, plain: bool = True) -> str:
        if plain:
            result = self.agent.run_turn(prompt)
            print(result)
            return result
        return stream_agent_events(
            self.console,
            self.agent.run_turn_stream(prompt),
            show_tool_details=self.config.agent.show_tool_details,
        )

    def interactive(self) -> int:
        render_banner(self.console, self.config, self.agent.active_session_id, self.config.voice.enabled)
        render_welcome_tips(self.console)
        session = create_prompt_session()
        last_prompt = ""
        while True:
            try:
                raw = session.prompt(get_prompt_text())
            except (EOFError, KeyboardInterrupt):
                self.console.print("\nAté já, meu bem.")
                return 0
            prompt = raw.strip()
            if not prompt:
                continue
            if prompt in {"/exit", "/quit"}:
                self.console.print("Até já, meu bem.")
                return 0
            if prompt == "/help":
                render_welcome_tips(self.console)
                continue
            if prompt == "/retry":
                if not last_prompt:
                    self.console.print(f"[{COLORS['overlay']}]nenhum turno anterior para repetir[/]")
                    continue
                prompt = last_prompt
            if prompt == "/clear":
                self.console.clear()
                render_banner(
                    self.console,
                    self.config,
                    self.agent.active_session_id,
                    self.config.voice.enabled,
                )
                render_welcome_tips(self.console)
                continue
            if prompt == "/status":
                self.console.print(
                    f"Celine · provider={self.config.model.provider} · model={self.config.model.default} · "
                    f"session={self.agent.active_session_id}"
                )
                continue
            if prompt.startswith("/provider") or prompt.startswith("/model"):
                self._handle_command(prompt)
                continue
            if prompt.startswith("/session") or prompt.startswith("/memory"):
                self._handle_command(prompt)
                continue
            try:
                last_prompt = prompt
                started_at = time.monotonic()
                self.run_once(prompt, plain=False)
                self.console.print(f"  [{COLORS['overlay']}]tempo do turno: {time.monotonic() - started_at:.1f}s[/]")
            except KeyboardInterrupt:
                self.console.print("\n[dim]Turn cancelado.[/]")
                continue
            except Exception as exc:
                self.console.print(f"[red]Erro:[/] {exc}")


def run_query(prompt: str) -> int:
    runtime = CelineRuntime.create()
    try:
        runtime.run_once(prompt)
        return 0
    except KeyboardInterrupt:
        print("\nTurno cancelado.", file=sys.stderr)
        return 130


def run_interactive() -> int:
    return CelineRuntime.create().interactive()


def is_tty() -> bool:
    return bool(sys.stdin.isatty() and sys.stdout.isatty())
