"""Provider model discovery with a safe, profile-local cache."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx

from celine.config import CELINE_HOME, KNOWN_PROVIDER_MODELS
from celine.providers.auth import AuthResolver


class ModelCatalog:
    """Merge curated models with provider-discovered models.

    Discovery is deliberately best-effort: a provider outage must never make
    the model picker unusable. The cache contains metadata only, never tokens.
    """

    CACHE_TTL = 15 * 60

    def __init__(self, home: Path | None = None) -> None:
        self.home = home or CELINE_HOME
        self.cache_path = self.home / "cache" / "provider_models.json"

    def options(
        self,
        provider: str,
        base_url: str,
        *,
        refresh: bool = False,
        custom_models: list[str] | None = None,
        custom_model: str = "",
    ) -> list[tuple[str, str]]:
        provider_key = provider.strip().lower()
        options: list[tuple[str, str]] = []
        seen: set[str] = set()

        aliases = {"nvidia-nim": "nvidia", "nvidianim": "nvidia"}
        for name, description in KNOWN_PROVIDER_MODELS.get(aliases.get(provider_key, provider_key), []):
            self._append(options, seen, name, description)

        for name in custom_models or []:
            self._append(options, seen, str(name), "modelo configurado")
        if custom_model:
            self._append(options, seen, custom_model, "modelo padrão do provider")

        discovered = self._discover(provider, base_url, refresh=refresh)
        for item in discovered:
            name = str(item.get("id", "")).strip()
            if not name:
                continue
            description = str(item.get("description") or "modelo descoberto no provider")
            self._append(options, seen, name, description)
        return options

    def probe(self, provider: str, base_url: str) -> tuple[bool, int, str]:
        """Check provider authentication and model endpoint without exposing secrets."""
        token = AuthResolver.resolve_token(provider)
        if not token and provider.strip().lower() not in {"ollama", "local"}:
            return False, 0, "credencial ausente"
        try:
            response = httpx.get(
                f"{base_url.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {token or 'ollama'}", "User-Agent": "Celine-Agent/1.5"},
                timeout=4.0,
            )
            response.raise_for_status()
            payload = response.json()
            raw_models = payload.get("data", []) if isinstance(payload, dict) else []
            count = len([item for item in raw_models if isinstance(item, dict) and item.get("id")])
            return True, count, f"HTTP {response.status_code}"
        except httpx.HTTPStatusError as exc:
            return False, 0, f"HTTP {exc.response.status_code}"
        except (OSError, ValueError, TypeError, httpx.HTTPError) as exc:
            return False, 0, type(exc).__name__

    @staticmethod
    def _append(
        options: list[tuple[str, str]], seen: set[str], name: str, description: str
    ) -> None:
        key = name.casefold()
        if name and key not in seen:
            seen.add(key)
            options.append((name, description))

    def _discover(self, provider: str, base_url: str, *, refresh: bool) -> list[dict[str, Any]]:
        key = provider.strip().lower()
        cached = self._read_cache().get(key, {})
        now = time.time()
        if not refresh and isinstance(cached, dict) and now - float(cached.get("fetched_at", 0)) < self.CACHE_TTL:
            return list(cached.get("models", []))

        token = AuthResolver.resolve_token(provider)
        if not token:
            return list(cached.get("models", [])) if isinstance(cached, dict) else []

        endpoint = f"{base_url.rstrip('/')}/models"
        try:
            response = httpx.get(
                endpoint,
                headers={"Authorization": f"Bearer {token}", "User-Agent": "Celine-Agent/1.5"},
                timeout=4.0,
            )
            response.raise_for_status()
            payload = response.json()
            raw_models = payload.get("data", []) if isinstance(payload, dict) else []
            models = [
                {
                    "id": str(item.get("id", "")),
                    "description": str(item.get("description") or "modelo descoberto no provider"),
                }
                for item in raw_models
                if isinstance(item, dict) and item.get("id")
            ]
            self._write_cache({**self._read_cache(), key: {"fetched_at": now, "models": models}})
            return models
        except (OSError, ValueError, TypeError, httpx.HTTPError):
            return list(cached.get("models", [])) if isinstance(cached, dict) else []

    def _read_cache(self) -> dict[str, Any]:
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _write_cache(self, data: dict[str, Any]) -> None:
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.cache_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            temporary.replace(self.cache_path)
        except OSError:
            pass
