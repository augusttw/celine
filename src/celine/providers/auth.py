from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from celine.config import CELINE_HOME, assert_celine_boundary


class AuthResolver:
    @staticmethod
    def _normalize_provider(provider: str) -> str:
        p = provider.strip().lower().replace("_", "-")
        if p in {"nvidia-nim", "nvidianim"}:
            return "nvidia"
        if p in {"openai-codex", "openaicodex"}:
            return "openai-codex"
        if p in {"open-router", "open_router"}:
            return "openrouter"
        return p

    @staticmethod
    def resolve_token(provider: str = "openai-codex") -> str | None:
        """Resolve API key or OAuth access token for a given provider."""
        assert_celine_boundary(CELINE_HOME)
        p_canon = AuthResolver._normalize_provider(provider)
        p_raw = provider.strip().lower()

        # Special case: Ollama doesn't require a real key
        if p_canon in {"ollama", "local"}:
            return "ollama"

        # 1. Environment variables have highest priority
        env_map = {
            "openai-codex": ["CELINE_API_KEY", "OPENAI_API_KEY", "CODEX_API_KEY"],
            "openai": ["OPENAI_API_KEY", "CELINE_API_KEY"],
            "nvidia": ["NVIDIA_API_KEY", "NVIDIA_NIM_API_KEY", "CELINE_API_KEY"],
            "openrouter": ["OPENROUTER_API_KEY", "CELINE_API_KEY"],
            "deepseek": ["DEEPSEEK_API_KEY", "CELINE_API_KEY"],
            "groq": ["GROQ_API_KEY", "CELINE_API_KEY"],
            "anthropic": ["ANTHROPIC_API_KEY", "CELINE_API_KEY"],
            "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY", "CELINE_API_KEY"],
            "qwen": ["DASHSCOPE_API_KEY", "QWEN_API_KEY", "CELINE_API_KEY"],
            "nous": ["NOUS_API_KEY", "CELINE_API_KEY"],
        }

        # Check mapped env vars
        for var in env_map.get(p_canon, []):
            val = os.environ.get(var)
            if val and val.strip():
                return val.strip()

        # Check generic <PROVIDER>_API_KEY
        fallback_var = f"{p_canon.replace('-', '_').upper()}_API_KEY"
        if os.environ.get(fallback_var):
            return os.environ[fallback_var].strip()

        # 2. Check ~/.celine/auth.json
        celine_auth = CELINE_HOME / "auth.json"
        for name_variant in [p_canon, p_raw, provider]:
            token = AuthResolver._read_auth_file(celine_auth, name_variant)
            if token:
                return token

        return None

    @staticmethod
    def has_token(provider: str) -> bool:
        return AuthResolver.resolve_token(provider) is not None

    @staticmethod
    def save_token(provider: str, token: str) -> None:
        """Saves an API key or token into ~/.celine/auth.json and sets in current os.environ."""
        token_clean = token.strip()
        p_canon = AuthResolver._normalize_provider(provider)

        CELINE_HOME.mkdir(parents=True, exist_ok=True)
        celine_auth = CELINE_HOME / "auth.json"
        data: dict[str, Any] = {}
        if celine_auth.exists():
            try:
                data = json.loads(celine_auth.read_text(encoding="utf-8"))
            except Exception:
                data = {}

        if "providers" not in data or not isinstance(data["providers"], dict):
            data["providers"] = {}

        entry = {
            "api_key": token_clean,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        data["providers"][p_canon] = entry
        data["providers"][provider.lower()] = entry

        fd, raw_tmp = tempfile.mkstemp(prefix=".auth.json.", dir=CELINE_HOME)
        temporary = Path(raw_tmp)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, celine_auth)
            os.chmod(celine_auth, 0o600)
        finally:
            temporary.unlink(missing_ok=True)

        # Also set in os.environ for instant runtime availability
        env_var_name = f"{p_canon.replace('-', '_').upper()}_API_KEY"
        os.environ[env_var_name] = token_clean
        if p_canon == "nvidia":
            os.environ["NVIDIA_API_KEY"] = token_clean
            os.environ["NVIDIA_NIM_API_KEY"] = token_clean

    @staticmethod
    def _read_auth_file(path: Path, provider: str) -> str | None:
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            providers = data.get("providers", {})

            # Direct match
            if provider in providers:
                p_data = providers[provider]
                tokens = p_data.get("tokens", {})
                if isinstance(tokens, dict) and tokens.get("access_token"):
                    return str(tokens["access_token"])
                # Nous OAuth stores access_token directly in the provider entry.
                if p_data.get("access_token"):
                    return str(p_data["access_token"])
                if p_data.get("api_key"):
                    return str(p_data["api_key"])
                if p_data.get("token"):
                    return str(p_data["token"])

            # Common fallbacks
            if provider in {"openai-codex", "codex"}:
                codex_entry = providers.get("openai-codex", {})
                tok = codex_entry.get("tokens", {}).get("access_token")
                if tok:
                    return str(tok)

            if provider in {"openai"}:
                openai_entry = providers.get("openai", {})
                if openai_entry.get("api_key"):
                    return str(openai_entry["api_key"])

            if provider in {"nvidia", "nvidia-nim"}:
                nv_entry = providers.get("nvidia", {}) or providers.get("nvidia-nim", {})
                if nv_entry.get("api_key"):
                    return str(nv_entry["api_key"])

        except Exception:
            pass
        return None
