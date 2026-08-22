from __future__ import annotations

from typing import Any

from celine.config import KNOWN_PROVIDER_PRESETS, CelineConfig
from celine.providers.auth import AuthResolver
from celine.providers.base import BaseProvider
from celine.providers.openai_provider import OpenAIProvider


class MissingApiKeyError(RuntimeError):
    def __init__(self, provider: str, hint: str = "") -> None:
        self.provider = provider
        self.hint = hint or f"{provider.upper().replace('-', '_')}_API_KEY"
        super().__init__(
            f"Nenhuma chave de API encontrada para o provedor '{provider}'.\n"
            f"Defina com /provider set-key {provider} <sua-chave> ou configure a variável {self.hint}."
        )


class ProviderRouter:
    @staticmethod
    def get_provider(
        config: CelineConfig,
        provider_name: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> BaseProvider:
        p_name = (provider_name or config.model.provider).strip().lower()
        target_model = model or config.model.default
        target_base_url = base_url or config.model.base_url
        target_key = api_key

        # 1. Check if provider matches known presets
        if p_name in KNOWN_PROVIDER_PRESETS:
            preset = KNOWN_PROVIDER_PRESETS[p_name]
            if not base_url:
                target_base_url = preset["base_url"]
            if not model and not config.model.default:
                target_model = preset["default_model"]

        # 2. Check custom providers
        for cp in config.custom_providers:
            if cp.name.lower() == p_name:
                target_base_url = cp.base_url
                if cp.api_key and not target_key:
                    target_key = cp.api_key
                if cp.model and not model:
                    target_model = cp.model
                break

        # 3. Resolve key
        resolved_key = target_key or AuthResolver.resolve_token(p_name)
        if not resolved_key and p_name not in {"ollama", "local"}:
            raise MissingApiKeyError(p_name)

        return OpenAIProvider(
            api_key=resolved_key or "ollama",
            base_url=target_base_url,
            default_model=target_model,
        )
