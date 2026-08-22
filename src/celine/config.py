from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

HOME = Path.home()
CELINE_HOME = Path(os.environ.get("CELINE_HOME", HOME / ".celine")).expanduser().resolve()
PROTECTED_HERMES_HOME = (HOME / ".hermes").resolve()


def assert_celine_boundary(path: Path | None = None) -> Path:
    """Return the Celine root and reject any path inside the Hermes profile."""
    root = (path or CELINE_HOME).expanduser().resolve()
    if root == PROTECTED_HERMES_HOME or root.is_relative_to(PROTECTED_HERMES_HOME):
        raise RuntimeError(f"CELINE_HOME isolado é obrigatório; recusando {root}")
    return root

# Pre-configured known providers
KNOWN_PROVIDER_PRESETS = {
    "openai-codex": {
        "base_url": "https://chatgpt.com/backend-api/codex",
        "default_model": "gpt-5.6-luna",
        "description": "OpenAI Codex backend via ChatGPT OAuth (auth.json)",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
        "description": "OpenAI API Oficial",
    },
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "default_model": "meta/llama-3.1-70b-instruct",
        "description": "NVIDIA NIM — Accelerated AI Inference",
    },
    "nvidia-nim": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "default_model": "meta/llama-3.1-70b-instruct",
        "description": "NVIDIA NIM — Accelerated AI Inference",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "anthropic/claude-3.5-sonnet",
        "description": "OpenRouter Multi-Model Gateway",
    },
    "qwen": {
        "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen3.7-plus",
        "description": "Alibaba DashScope (Qwen 3.5 / 3.7)",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "description": "DeepSeek API Oficial",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "description": "Groq LPU Inference Engine",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "default_model": "llama3.2",
        "description": "Ollama Local (sem necessidade de API key)",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "default_model": "gemini-2.0-flash",
        "description": "Google Gemini OpenAI Endpoint",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1",
        "default_model": "claude-3-5-sonnet-20241022",
        "description": "Anthropic Claude API",
    },
}

KNOWN_PROVIDER_MODELS: dict[str, list[tuple[str, str]]] = {
    "openai-codex": [
        ("gpt-5.6-luna", "Flagship recente com alta inteligência e raciocínio"),
        ("gpt-5.1", "Rápido, equilibrado e fluido para conversas diárias"),
        ("gpt-5.1-codex", "Especializado em engenharia de software e automação"),
        ("gpt-5-sonnet", "Modelo balanceado para tarefas gerais"),
    ],
    "nvidia": [
        ("meta/llama-3.1-70b-instruct", "Llama 3.1 70B: Modelo ativo de alta capacidade e coding"),
        ("meta/llama-3.1-8b-instruct", "Llama 3.1 8B: Resposta instantânea, leve e fluida"),
        ("meta/llama-3.3-70b-instruct", "Llama 3.3 70B: Modelo mais recente da Meta"),
        ("nvidia/llama-3.1-nemotron-70b-instruct", "Nemotron 70B: Requer ativação em build.nvidia.com"),
        ("nvidia/nemotron-3.5-lightning-30b-a3b", "Nemotron 3.5 Lightning 30B: baixa latência para agentes"),
    ],
    "nvidia-nim": [
        ("meta/llama-3.1-70b-instruct", "Llama 3.1 70B: Modelo ativo de alta capacidade e coding"),
        ("meta/llama-3.1-8b-instruct", "Llama 3.1 8B: Resposta instantânea, leve e fluida"),
        ("meta/llama-3.3-70b-instruct", "Llama 3.3 70B: Modelo mais recente da Meta"),
        ("nvidia/llama-3.1-nemotron-70b-instruct", "Nemotron 70B: Requer ativação em build.nvidia.com"),
        ("nvidia/nemotron-3.5-lightning-30b-a3b", "Nemotron 3.5 Lightning 30B: baixa latência para agentes"),
    ],
    "openrouter": [
        ("anthropic/claude-3.5-sonnet", "Claude 3.5 Sonnet: padrão da indústria para código"),
        ("deepseek/deepseek-r1", "DeepSeek R1: modelo aberto de raciocínio profundo"),
        ("deepseek/deepseek-chat", "DeepSeek V3: excelente qualidade e custo ultra-baixo"),
        ("google/gemini-2.0-flash-001", "Gemini 2.0 Flash: resposta instantânea e janela gigante"),
        ("meta-llama/llama-3.3-70b-instruct", "Meta Llama 3.3 70B"),
        ("qwen/qwen-2.5-coder-32b-instruct", "Qwen 2.5 Coder 32B"),
    ],
    "openai": [
        ("gpt-4o", "OpenAI GPT-4o: flagship multimodal balanceado"),
        ("gpt-4o-mini", "OpenAI GPT-4o Mini: rápido e de baixo custo"),
        ("o1", "OpenAI o1: raciocínio profundo passo a passo"),
        ("o3-mini", "OpenAI o3-mini: modelo ágil focado em STEM e código"),
    ],
    "deepseek": [
        ("deepseek-chat", "DeepSeek V3: modelo principal balanceado e veloz"),
        ("deepseek-reasoner", "DeepSeek R1: raciocínio avançado com cadeia analítica"),
    ],
    "qwen": [
        ("qwen3.7-plus", "Qwen 3.7 Plus: modelo mais inteligente da Alibaba DashScope"),
        ("qwen3.6-plus", "Qwen 3.6 Plus: alta velocidade e precisão em português"),
        ("qwen-max", "Qwen Max: modelo com capacidade máxima de contexto"),
        ("qwen-turbo", "Qwen Turbo: modelo ultra-leve para respostas imediatas"),
    ],
    "groq": [
        ("llama-3.3-70b-versatile", "Llama 3.3 70B com taxa de geração ultra-alta"),
        ("llama-3.1-8b-instant", "Llama 3.1 8B geração instantânea"),
        ("deepseek-r1-distill-llama-70b", "DeepSeek R1 destilado no Llama 70B"),
        ("mixtral-8x7b-32768", "Mistral MoE 8x7B"),
    ],
    "ollama": [
        ("llama3.2", "Llama 3.2 rodando localmente via Ollama"),
        ("qwen2.5-coder", "Qwen 2.5 Coder para desenvolvimento local"),
        ("deepseek-r1", "DeepSeek R1 local"),
        ("mistral", "Mistral 7B local"),
    ],
    "gemini": [
        ("gemini-2.0-flash", "Gemini 2.0 Flash oficial via OpenAI compatibility"),
        ("gemini-2.0-flash-thinking-exp", "Gemini 2.0 Flash Thinking Experimental"),
        ("gemini-1.5-pro", "Gemini 1.5 Pro"),
    ],
    "anthropic": [
        ("claude-3-5-sonnet-20241022", "Claude 3.5 Sonnet oficial"),
        ("claude-3-5-haiku-20241022", "Claude 3.5 Haiku"),
        ("claude-3-opus-20240229", "Claude 3 Opus"),
    ],
}


@dataclass
class ModelConfig:
    default: str = "gpt-5.6-luna"
    provider: str = "openai-codex"
    base_url: str = "https://chatgpt.com/backend-api/codex"
    temperature: float = 0.7


@dataclass
class VoiceConfig:
    enabled: bool = False
    voice: str = "pt-BR-FranciscaNeural"
    rate: str = "+0%"
    pitch: str = "+0Hz"
    volume: str = "+0%"


@dataclass
class AgentConfig:
    max_turns: int = 30
    streaming: bool = True
    context_limit: int = 40000
    compaction_threshold: float = 0.85
    show_tool_details: bool = True


@dataclass
class CustomProvider:
    name: str
    base_url: str
    api_key: str = ""
    model: str = ""
    models: list[str] = field(default_factory=list)


@dataclass
class CelineConfig:
    model: ModelConfig = field(default_factory=ModelConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    custom_providers: list[CustomProvider] = field(default_factory=list)

    @classmethod
    def load(cls) -> CelineConfig:
        config_path = CELINE_HOME / "config.yaml"
        data: dict[str, Any] = {}
        # Celine configuration is self-contained. Never inherit another profile.
        if config_path.exists():
            try:
                celine_data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
                if isinstance(celine_data, dict):
                    data.update(celine_data)
            except Exception:
                pass

        model_dict = data.get("model", {})
        if not isinstance(model_dict, dict):
            model_dict = {}

        default_model = os.environ.get("CELINE_MODEL") or model_dict.get("default", "gpt-5.6-luna")
        provider = os.environ.get("CELINE_PROVIDER") or model_dict.get("provider", "openai-codex")
        base_url = os.environ.get("CELINE_BASE_URL") or model_dict.get("base_url", "https://chatgpt.com/backend-api/codex")

        voice_dict = data.get("voice", {})
        if not isinstance(voice_dict, dict):
            voice_dict = {}
        tts_dict = data.get("tts", {})
        edge_dict = tts_dict.get("edge", {}) if isinstance(tts_dict, dict) else {}

        voice_enabled = os.environ.get("CELINE_VOICE", "").lower() in {"1", "true", "on", "yes"}
        if not voice_enabled and "enabled" in voice_dict:
            voice_enabled = bool(voice_dict.get("enabled", False))

        voice_name = voice_dict.get("voice") or edge_dict.get("voice") or "pt-BR-FranciscaNeural"

        # Custom providers
        custom_list: list[CustomProvider] = []
        for cp in data.get("custom_providers", []):
            if isinstance(cp, dict) and "name" in cp and "base_url" in cp:
                raw_models = cp.get("models", [])
                if isinstance(raw_models, dict):
                    parsed_models = [str(name) for name in raw_models]
                elif isinstance(raw_models, list):
                    parsed_models = [str(name) for name in raw_models]
                else:
                    parsed_models = []
                custom_list.append(
                    CustomProvider(
                        name=cp["name"],
                        base_url=cp["base_url"],
                        api_key=cp.get("api_key", ""),
                        model=cp.get("model", ""),
                        models=parsed_models,
                    )
                )

        return cls(
            model=ModelConfig(
                default=default_model,
                provider=provider,
                base_url=base_url,
                temperature=float(model_dict.get("temperature", 0.7)),
            ),
            voice=VoiceConfig(
                enabled=voice_enabled,
                voice=voice_name,
                rate=voice_dict.get("rate", "+0%"),
                pitch=voice_dict.get("pitch", "+0Hz"),
                volume=voice_dict.get("volume", "+0%"),
            ),
            agent=AgentConfig(
                max_turns=int(data.get("agent", {}).get("max_turns", 30)),
                streaming=bool(data.get("agent", {}).get("streaming", True)),
                context_limit=int(data.get("agent", {}).get("context_limit", 40000)),
                compaction_threshold=float(data.get("agent", {}).get("compaction_threshold", 0.85)),
                show_tool_details=bool(data.get("agent", {}).get("show_tool_details", True)),
            ),
            custom_providers=custom_list,
        )

    def save(self) -> None:
        CELINE_HOME.mkdir(parents=True, exist_ok=True)
        config_path = CELINE_HOME / "config.yaml"
        from celine.providers.auth import AuthResolver

        for cp in self.custom_providers:
            if cp.api_key:
                AuthResolver.save_token(cp.name, cp.api_key)
        try:
            data = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
        except (OSError, yaml.YAMLError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        data.update(
            {
                "model": {
                    "default": self.model.default,
                    "provider": self.model.provider,
                    "base_url": self.model.base_url,
                    "temperature": self.model.temperature,
                },
                "voice": {
                    "enabled": self.voice.enabled,
                    "voice": self.voice.voice,
                    "rate": self.voice.rate,
                    "pitch": self.voice.pitch,
                    "volume": self.voice.volume,
                },
                "agent": {
                    "max_turns": self.agent.max_turns,
                    "streaming": self.agent.streaming,
                    "context_limit": self.agent.context_limit,
                    "compaction_threshold": self.agent.compaction_threshold,
                    "show_tool_details": self.agent.show_tool_details,
                },
                "custom_providers": [
                    {
                        "name": cp.name,
                        "base_url": cp.base_url,
                        "model": cp.model,
                        "models": cp.models,
                    }
                    for cp in self.custom_providers
                ],
            }
        )
        fd, raw_tmp = tempfile.mkstemp(prefix=".config.yaml.", dir=CELINE_HOME)
        temporary = Path(raw_tmp)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                yaml.safe_dump(data, handle, default_flow_style=False, allow_unicode=True, sort_keys=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, config_path)
            os.chmod(config_path, 0o600)
        finally:
            temporary.unlink(missing_ok=True)

    def add_or_update_provider(
        self,
        name: str,
        base_url: str,
        api_key: str = "",
        model: str = "",
        models: list[str] | None = None,
    ) -> None:
        norm_name = name.strip()
        for cp in self.custom_providers:
            if cp.name.lower() == norm_name.lower():
                cp.base_url = base_url.strip()
                if api_key:
                    cp.api_key = api_key.strip()
                if model:
                    cp.model = model.strip()
                if models:
                    cp.models = models
                self.save()
                return

        self.custom_providers.append(
            CustomProvider(
                name=norm_name,
                base_url=base_url.strip(),
                api_key=api_key.strip(),
                model=model.strip(),
                models=models or [],
            )
        )
        self.save()

    def remove_provider(self, name: str) -> bool:
        norm_name = name.strip().lower()
        initial_len = len(self.custom_providers)
        self.custom_providers = [cp for cp in self.custom_providers if cp.name.lower() != norm_name]
        if len(self.custom_providers) != initial_len:
            self.save()
            return True
        return False

    def list_all_providers(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []

        for p_name, preset in KNOWN_PROVIDER_PRESETS.items():
            results.append(
                {
                    "name": p_name,
                    "base_url": preset["base_url"],
                    "model": preset["default_model"],
                    "type": "preset",
                    "description": preset.get("description", ""),
                }
            )

        for cp in self.custom_providers:
            if cp.name.lower() not in {r["name"].lower() for r in results}:
                results.append(
                    {
                        "name": cp.name,
                        "base_url": cp.base_url,
                        "model": cp.model or "(padrão)",
                        "type": "custom",
                        "description": "Provedor personalizado",
                    }
                )

        return results

    def get_models_for_provider(self, provider_name: str | None = None) -> list[tuple[str, str]]:
        p_name = (provider_name or self.model.provider).strip().lower()

        if p_name in KNOWN_PROVIDER_MODELS:
            return list(KNOWN_PROVIDER_MODELS[p_name])

        if p_name in {"nvidia-nim", "nvidianim"}:
            return list(KNOWN_PROVIDER_MODELS["nvidia"])

        for cp in self.custom_providers:
            if cp.name.lower() == p_name:
                models_list: list[tuple[str, str]] = []
                if cp.model:
                    models_list.append((cp.model, "Modelo principal configurado"))
                for m in cp.models:
                    if m != cp.model:
                        models_list.append((m, "Modelo alternativo"))
                if models_list:
                    return models_list

        return [(self.model.default, "Modelo padrão atual")]
