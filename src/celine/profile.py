from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from celine.legacy_sessions import migrate_legacy_sessions
from celine.skill_isolation import normalize_celine_skills

# Identity settings are kept current by Celine. Inference and safety choices
# deliberately are not: after the first install they belong to the user and to
# the full Hermes provider/configuration surface.
PROFILE_CONFIG = {
    "display.interface": "tui",
    "display.skin": "celine-afterglow",
}

PROFILE_DEFAULTS = {
    "model.provider": "openai-codex",
    "model.default": "gpt-5.6-sol",
    "approvals.mode": "manual",
}

LEGACY_SOUL_HASHES = {
    "4bbda99315ebf2d108e64147093b73e1e468d1bc3c18309fea8e21aefd9d6459",
    "9c028d7fd3e8ace5d9c848f0a2c3e75391aeb9f015214859d99832d3129f5772",
}


class ProfileError(RuntimeError):
    pass


@dataclass
class Report:
    title: str
    items: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    ok: bool = True

    def render(self) -> str:
        status = "✓" if self.ok else "✗"
        lines = [f"{status} {self.title}"]
        lines.extend(f"  • {item}" for item in self.items)
        lines.extend(f"  ! {warning}" for warning in self.warnings)
        return "\n".join(lines)


def _private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass


def _atomic_json(path: Path, data: dict[str, Any]) -> None:
    _private_dir(path.parent)
    fd, raw_tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp = Path(raw_tmp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
        path.chmod(0o600)
    finally:
        tmp.unlink(missing_ok=True)


def _atomic_yaml(path: Path, data: dict[str, Any]) -> None:
    _private_dir(path.parent)
    fd, raw_tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp = Path(raw_tmp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
        path.chmod(0o600)
    finally:
        tmp.unlink(missing_ok=True)


def _same_bytes(source: Path, destination: Path) -> bool:
    if not destination.exists() or not destination.is_file():
        return False
    return hashlib.sha256(source.read_bytes()).digest() == hashlib.sha256(destination.read_bytes()).digest()


class ProfileInstaller:
    def __init__(self, home: Path | None = None, hermes_bin: str | None = None) -> None:
        # CELINE_HOME is the only profile override. Inheriting HERMES_HOME here
        # could accidentally target whichever Hermes profile launched Celine.
        env_home = os.environ.get("CELINE_HOME")
        self.home = (home or Path(env_home or Path.home() / ".celine")).expanduser().resolve()
        protected_hermes = (Path.home() / ".hermes").resolve()
        if self.home == protected_hermes or self.home.is_relative_to(protected_hermes):
            raise ProfileError(f"CELINE_HOME deve ser isolado; recusando usar diretório do Hermes padrão: {self.home}")
        # Kept as a compatibility argument for callers of older releases.
        # Celine no longer discovers, imports, or executes Hermes.
        self.hermes_bin = hermes_bin
        self._backup_root: Path | None = None
        self._created_paths: list[Path] = []

    def _assert_profile_boundary(self) -> None:
        protected_hermes = (Path.home() / ".hermes").resolve()
        resolved_home = self.home.resolve()
        boundary_broken = (
            resolved_home != self.home
            or resolved_home == protected_hermes
            or resolved_home.is_relative_to(protected_hermes)
        )
        if boundary_broken:
            raise ProfileError(f"Boundary inválida para CELINE_HOME: {self.home}")

    def _preflight(self) -> None:
        self._assert_profile_boundary()
        _private_dir(self.home)

    def _backup(self, path: Path) -> Path | None:
        if not path.exists():
            return None
        if self._backup_root is None:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            self._backup_root = self.home / "backups" / f"profile-migration-{stamp}"
            _private_dir(self._backup_root)
        try:
            relative = path.relative_to(self.home)
        except ValueError as exc:
            raise ProfileError(f"Recusando backup fora do profile Celine: {path}") from exc
        target = self._backup_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.is_dir():
            shutil.copytree(path, target, dirs_exist_ok=True)
        else:
            shutil.copy2(path, target)
        return target

    def _copy_asset(self, source: Path, destination: Path, *, overwrite: bool) -> bool:
        if destination.is_symlink():
            raise ProfileError(f"Recusando sobrescrever symlink no profile Celine: {destination}")
        resolved_parent = destination.parent.resolve()
        if not resolved_parent.is_relative_to(self.home):
            raise ProfileError(f"Destino de asset escaparia do profile Celine: {destination}")
        if _same_bytes(source, destination):
            return False
        if destination.exists() and not overwrite:
            return False
        if destination.exists():
            self._backup(destination)
        else:
            self._created_paths.append(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, raw_tmp = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
        tmp = Path(raw_tmp)
        os.close(fd)
        try:
            shutil.copyfile(source, tmp)
            if os.name == "posix":
                tmp.chmod(0o600)
            if not destination.parent.resolve().is_relative_to(self.home) or destination.is_symlink():
                raise ProfileError(f"Destino mudou durante instalação do asset: {destination}")
            os.replace(tmp, destination)
        finally:
            tmp.unlink(missing_ok=True)
        return True

    def _install_assets(self, force_persona: bool, report: Report) -> None:
        celine_assets = Path(str(resources.files("celine").joinpath("assets")))
        soul_source = celine_assets / "SOUL.md"
        skin_source = celine_assets / "skins" / "celine-afterglow.yaml"
        soul_destination = self.home / "SOUL.md"
        persona_current = _same_bytes(soul_source, soul_destination)
        legacy_persona = (
            soul_destination.exists()
            and hashlib.sha256(soul_destination.read_bytes()).hexdigest() in LEGACY_SOUL_HASHES
        )
        if persona_current:
            report.items.append("persona Celine já está atual")
        elif self._copy_asset(soul_source, soul_destination, overwrite=force_persona or legacy_persona):
            report.items.append("persona Celine instalada")
        elif soul_destination.exists() and not force_persona:
            report.items.append("SOUL.md customizado preservado; `celine evaluate` valida o conteúdo instalado")

        if self._copy_asset(skin_source, self.home / "skins" / skin_source.name, overwrite=True):
            report.items.append("skin celine-afterglow instalada")

        widget_source = celine_assets / "tui-widgets" / "celine-pulse.mjs"
        if self._copy_asset(widget_source, self.home / "tui-widgets" / widget_source.name, overwrite=True):
            report.items.append("widget TUI celine-pulse instalado")

        plugin_source = Path(str(resources.files("celine_companion")))
        plugin_destination = self.home / "plugins" / "celine-companion"
        for source in plugin_source.rglob("*"):
            if source.is_file() and "__pycache__" not in source.parts and not source.name.endswith(".pyc"):
                relative = source.relative_to(plugin_source)
                self._copy_asset(source, plugin_destination / relative, overwrite=True)
        report.items.append("plugin celine-companion instalado")

    def _sync_auth(self, source_home: Path, report: Report) -> None:
        source = source_home.expanduser().resolve() / "auth.json"
        if not source.exists():
            raise ProfileError(f"Credenciais de origem não encontradas: {source}")
        try:
            source_data = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProfileError(f"Não foi possível ler {source}.") from exc
        provider = source_data.get("providers", {}).get("openai-codex")
        if not isinstance(provider, dict):
            raise ProfileError("Provider openai-codex não encontrado no auth.json de origem.")

        destination = self.home / "auth.json"
        if destination.is_symlink():
            raise ProfileError(f"Recusando escrever credenciais através de symlink: {destination}")
        current: dict[str, Any] = {}
        if destination.exists():
            try:
                current = json.loads(destination.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ProfileError(f"auth.json da Celine é inválido: {destination}") from exc
            self._backup(destination)
        else:
            self._created_paths.append(destination)
        providers = current.setdefault("providers", {})
        if not isinstance(providers, dict):
            raise ProfileError("Campo providers inválido no auth.json da Celine.")
        providers["openai-codex"] = provider
        _atomic_json(destination, current)
        report.items.append("credencial openai-codex sincronizada para a cópia isolada da Celine")

    def _configure(self, report: Report, *, first_install: bool) -> None:
        self._assert_profile_boundary()
        config_path = self.home / "config.yaml"
        if config_path.is_symlink():
            raise ProfileError(f"Recusando configurar profile através de symlink: {config_path}")
        try:
            data = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
        except (OSError, yaml.YAMLError) as exc:
            raise ProfileError(f"config.yaml inválido: {config_path}") from exc
        if not isinstance(data, dict):
            data = {}
        settings = {**PROFILE_DEFAULTS, **PROFILE_CONFIG} if first_install else PROFILE_CONFIG
        for dotted_key, value in settings.items():
            target = data
            parts = dotted_key.split(".")
            for part in parts[:-1]:
                child = target.setdefault(part, {})
                if not isinstance(child, dict):
                    raise ProfileError(f"Configuração incompatível em {dotted_key}")
                target = child
            target[parts[-1]] = value
        _atomic_yaml(config_path, data)
        if first_install:
            report.items.append(
                "defaults iniciais configurados; provider, modelo, APIs e approvals ficam livres depois"
            )
        else:
            report.items.append("identidade visual atualizada sem alterar provider, modelo, APIs ou approvals")
        report.items.append("runtime próprio Celine configurado: provider, memória, sessões e ferramentas locais")

    def _rollback(self) -> None:
        for path in reversed(self._created_paths):
            if path.is_file() or path.is_symlink():
                path.unlink(missing_ok=True)
        if self._backup_root and self._backup_root.exists():
            for source in self._backup_root.rglob("*"):
                if not source.is_file():
                    continue
                relative = source.relative_to(self._backup_root)
                destination = self.home / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)

    @staticmethod
    def _read_scalar_config(path: Path, dotted_key: str) -> str | None:
        if not path.exists():
            return None
        target = dotted_key.split(".")
        stack: list[tuple[int, str]] = []
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            if not raw_line.strip() or raw_line.lstrip().startswith(("#", "-")):
                continue
            indent = len(raw_line) - len(raw_line.lstrip(" "))
            line = raw_line.strip()
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            while stack and stack[-1][0] >= indent:
                stack.pop()
            current = [item[1] for item in stack] + [key.strip()]
            value = value.strip()
            if current == target and value:
                return value.strip("'\"")
            if not value:
                stack.append((indent, key.strip()))
        return None

    def _config_drift(self) -> list[str]:
        config_path = self.home / "config.yaml"
        drift: list[str] = []
        for key, expected in PROFILE_CONFIG.items():
            actual = self._read_scalar_config(config_path, key)
            if actual != expected:
                drift.append(f"{key}: esperado {expected!r}, encontrado {actual!r}")
        return drift

    def _migrate_config_secrets(self, report: Report | None = None) -> int:
        """Move legacy provider keys out of config.yaml into auth.json."""
        config_path = self.home / "config.yaml"
        if not config_path.exists() or config_path.is_symlink():
            return 0
        try:
            data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            return 0
        providers = data.get("custom_providers") if isinstance(data, dict) else None
        if not isinstance(providers, list):
            return 0

        from celine.providers.auth import AuthResolver

        migrated = 0
        for provider in providers:
            if not isinstance(provider, dict):
                continue
            token = str(provider.pop("api_key", "") or "").strip()
            name = str(provider.get("name", "") or "").strip()
            if token and name:
                AuthResolver.save_token(name, token)
                migrated += 1
        if migrated:
            self._backup(config_path)
            _atomic_yaml(config_path, data)
            if report:
                report.items.append(f"{migrated} credencial(is) movida(s) de config.yaml para auth.json")
        return migrated

    def install(
        self,
        *,
        force_persona: bool = False,
        sync_auth: bool = False,
        source_hermes_home: Path | None = None,
    ) -> Report:
        self._preflight()
        self._backup_root = None
        self._created_paths = []
        config_path = self.home / "config.yaml"
        first_install = not config_path.exists() and not (self.home / ".celine-profile-version").exists()
        _private_dir(self.home)
        report = Report("Profile Celine instalado")
        try:
            self._install_assets(force_persona, report)
            if sync_auth:
                source = source_hermes_home or Path.home() / ".hermes"
                if source.expanduser().resolve() == self.home:
                    raise ProfileError("A origem das credenciais não pode ser o próprio CELINE_HOME.")
                self._sync_auth(source, report)
            if config_path.exists():
                self._backup(config_path)
            else:
                self._created_paths.append(config_path)
            self._configure(report, first_install=first_install)
            self._migrate_config_secrets(report)
            skill_files, skill_replacements = normalize_celine_skills(self.home)
            if skill_files:
                report.items.append(
                    f"{skill_files} arquivos de skills isolados em ~/.celine ({skill_replacements} caminhos corrigidos)"
                )
            sessions_added, messages_added = migrate_legacy_sessions(self.home)
            if sessions_added or messages_added:
                report.items.append(
                    f"legacy state synchronized into state.db: {sessions_added} session(s), {messages_added} message(s)"
                )
            for private_file in (
                self.home / "config.yaml",
                self.home / "auth.json",
                self.home / "SOUL.md",
                self.home / "state.db",
                self.home / "celine.db",
            ):
                if private_file.exists() and os.name == "posix":
                    private_file.chmod(0o600)
            marker = self.home / ".celine-profile-version"
            if not marker.exists():
                self._created_paths.append(marker)
            marker.write_text("1.5.0\n", encoding="utf-8")
            marker.chmod(0o600)
        except Exception as exc:
            try:
                self._rollback()
            except Exception as rollback_exc:
                raise ProfileError(f"Instalação falhou e rollback também falhou: {rollback_exc}") from exc
            raise
        if self._backup_root:
            report.items.append(f"backup criado em {self._backup_root}")
        return report

    def ensure_installed(self) -> None:
        self._assert_profile_boundary()
        required = [
            self.home / "SOUL.md",
            self.home / "skins" / "celine-afterglow.yaml",
            self.home / "tui-widgets" / "celine-pulse.mjs",
            self.home / "plugins" / "celine-companion" / "plugin.yaml",
            self.home / "plugins" / "celine-companion" / "desktop" / "plugin.js",
            self.home / ".celine-profile-version",
        ]
        if not all(path.exists() for path in required):
            self.install(force_persona=False, sync_auth=False)
        else:
            self._migrate_config_secrets()
            drift = self._config_drift()
            if drift:
                raise ProfileError("Configuração da Celine mudou; execute `celine install`. " + "; ".join(drift))
        normalize_celine_skills(self.home)
        migrate_legacy_sessions(self.home)
        if os.name == "posix":
            private_files = (
                self.home / "auth.json",
                self.home / "config.yaml",
                self.home / "SOUL.md",
                self.home / "state.db",
            )
            for private_file in private_files:
                if private_file.exists():
                    private_file.chmod(0o600)

    def doctor(self) -> Report:
        self._assert_profile_boundary()
        report = Report("Diagnóstico Celine")
        checks = {
            "SOUL.md": self.home / "SOUL.md",
            "skin": self.home / "skins" / "celine-afterglow.yaml",
            "widget TUI": self.home / "tui-widgets" / "celine-pulse.mjs",
            "plugin": self.home / "plugins" / "celine-companion" / "plugin.yaml",
            "plugin Desktop": self.home / "plugins" / "celine-companion" / "desktop" / "plugin.js",
            "config": self.home / "config.yaml",
        }
        for label, path in checks.items():
            if path.exists():
                report.items.append(f"{label}: {path}")
            else:
                report.ok = False
                report.warnings.append(f"ausente: {path}")
        for mismatch in self._config_drift():
            report.ok = False
            report.warnings.append(f"config divergente — {mismatch}")
        try:
            from celine.config import CelineConfig
            from celine.core.memory import DB_PATH as MEMORY_DB_PATH
            from celine.core.session import DB_PATH as SESSION_DB_PATH
            from celine.providers.catalog import ModelCatalog
            from celine.tools import registry

            canonical = (self.home / "state.db").resolve()
            if SESSION_DB_PATH.resolve() != canonical or MEMORY_DB_PATH.resolve() != canonical:
                report.ok = False
                report.warnings.append("runtime session/memory storage is not unified on state.db")
            else:
                report.items.append("canonical state: sessions and memory use state.db")
            registered = {schema["function"]["name"] for schema in registry.get_schemas()}
            companion = {"celine_relationship", "celine_pulse", "celine_presence"}
            if not companion.issubset(registered):
                report.ok = False
                report.warnings.append("native companion tools are not fully registered")
            else:
                report.items.append("native companion tools registered: relationship, pulse, presence")

            runtime_config = CelineConfig.load()
            probe_ok, model_count, probe_detail = ModelCatalog(self.home).probe(
                runtime_config.model.provider,
                runtime_config.model.base_url,
            )
            report.items.append(
                f"provider ativo: {runtime_config.model.provider} · modelo: {runtime_config.model.default}"
            )
            if probe_ok:
                report.items.append(f"endpoint de modelos: {model_count} disponível(is) · {probe_detail}")
            else:
                if probe_detail == "credencial ausente":
                    report.ok = False
                report.warnings.append(f"endpoint de modelos: {probe_detail}")
        except Exception as exc:
            report.warnings.append(f"probe do provider falhou: {type(exc).__name__}")
        auth = self.home / "auth.json"
        provider = self._read_scalar_config(self.home / "config.yaml", "model.provider") or ""
        auth_required = provider not in {"local", "ollama"}
        if auth.exists() and os.name == "posix":
            mode = stat.S_IMODE(auth.stat().st_mode)
            if mode != 0o600:
                report.ok = False
                report.warnings.append(f"auth.json está com modo {oct(mode)}, esperado 0o600")
        elif auth_required:
            report.ok = False
            report.warnings.append(f"ausente: {auth} (necessário para provider {provider or 'não configurado'})")
        else:
            report.items.append("auth não necessária para provider local")
        report.items.append("runtime independente validado: sem dependência de executável ou profile Hermes")
        return report
