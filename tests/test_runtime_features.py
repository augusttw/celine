from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from celine.config import CelineConfig
from celine.providers.catalog import ModelCatalog
from celine.runtime import CelineRuntime
from celine.ui.stream import _bubble
from celine.tools.memory_tools import remember
from celine.core.memory import _validate_memory_text
from celine.core.session import SessionManager
from celine.core.agent import CelineAgent
from celine.providers.base import StreamChunk
from rich.console import Console


class ModelCatalogTests(unittest.TestCase):
    def test_curated_and_cached_models_are_merged_without_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = ModelCatalog(Path(directory))
            catalog._write_cache(
                {
                    "nvidia-nim": {
                        "fetched_at": 9999999999,
                        "models": [
                            {"id": "nvidia/nemotron-3.5-lightning-30b-a3b"},
                            {"id": "meta/llama-3.1-70b-instruct"},
                        ],
                    }
                }
            )
            options = catalog.options(
                "nvidia-nim",
                "https://integrate.api.nvidia.com/v1",
                refresh=False,
            )
            names = [name for name, _ in options]
            self.assertIn("nvidia/nemotron-3.5-lightning-30b-a3b", names)
            self.assertEqual(len(names), len({name.casefold() for name in names}))


class RuntimeSelectionTests(unittest.TestCase):
    def test_provider_model_can_be_selected_without_network(self) -> None:
        class Agent:
            active_session_id = "session_test"

            def switch_model(self, model: str) -> None:
                self.selected = model

        agent = Agent()
        runtime = CelineRuntime(CelineConfig.load(), agent, Console(record=True))
        runtime._save_model_settings = lambda: None
        runtime._select_model("nvidia/nemotron-3.5-lightning-30b-a3b")
        self.assertEqual(agent.selected, "nvidia/nemotron-3.5-lightning-30b-a3b")

    def test_memory_tool_requires_explicit_consent(self) -> None:
        result = remember("um fato de teste", consent=False)
        self.assertIn("consentimento", result.lower())

    def test_memory_rejects_secrets(self) -> None:
        with self.assertRaises(ValueError):
            _validate_memory_text("api_key=sk-12345678901234567890")

    def test_old_session_context_is_ranked_and_excludes_tools(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "celine.db"
            with patch("celine.core.session.DB_PATH", db):
                manager = SessionManager()
                old = manager.create_session("Projeto Celine")
                active = manager.create_session("Agora")
                manager.save_message(old, "user", "Implementamos o cache do projeto Celine")
                manager.save_message(old, "tool", "token secreto do cache")
                manager.save_message(old, "assistant", "O cache do projeto Celine foi validado")
                matches = manager.search_context("Como ficou o projeto Celine?", active)
                self.assertTrue(matches)
                self.assertTrue(all(item["role"] in {"user", "assistant"} for item in matches))
                self.assertIn("cache", matches[0]["content"].lower())

    def test_agent_retries_a_clean_provider_failure_once(self) -> None:
        class FlakyProvider:
            def __init__(self) -> None:
                self.calls = 0

            def stream_chat(self, **_: object):
                self.calls += 1
                if self.calls == 1:
                    raise TimeoutError("transient")
                yield StreamChunk(text="recuperei")

        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "celine.db"
            with patch("celine.core.session.DB_PATH", db), patch("celine.core.agent.persona_manager.build_system_prompt", return_value="Celine"):
                manager = SessionManager()
                config = CelineConfig.load()
                agent = CelineAgent.__new__(CelineAgent)
                agent.config = config
                agent.session_manager = manager
                agent.active_session_id = manager.create_session("Teste")
                object.__setattr__(agent, "context_manager", type("Context", (), {"should_compact": lambda *_: False})())
                provider = FlakyProvider()
                object.__setattr__(agent, "_provider", provider)
                output = agent.run_turn("teste")
                self.assertEqual(output, "recuperei")
                self.assertEqual(provider.calls, 2)

    def test_thinking_panel_matches_golden_snapshot(self) -> None:
        console = Console(record=True, width=72, force_terminal=False, color_system=None)
        console.print(_bubble("", title="celine  ·  pensando…", border="#aa91b7", empty="pensando…"))
        snapshot = Path(__file__).parent / "snapshots" / "thinking.txt"
        self.assertEqual(console.export_text().strip(), snapshot.read_text(encoding="utf-8").strip())

    def test_context_compact_preserves_structured_intents_and_files(self) -> None:
        from celine.core.context import ContextManager
        cm = ContextManager(limit=1000, threshold=0.1)
        messages = [
            {"role": "system", "content": "You are Celine."},
            {"role": "user", "content": "Refatore o arquivo main.go e adicione logs"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": '{"path": "main.go"}'},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "package main..."},
            {"role": "assistant", "content": "Arquivo lido com sucesso."},
            {"role": "user", "content": "Agora rode o teste com -race"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {"name": "bash", "arguments": '{"command": "go test -race ./..."}'},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_2", "content": "PASS ok main 0.05s"},
            {"role": "assistant", "content": "Testes passaram lisos!"},
            {"role": "user", "content": "Excelente."},
            {"role": "assistant", "content": "Pronta para o próximo passo!"},
        ]
        compacted = cm.compact(messages, preserve_last_n=2)
        summary_content = compacted[1]["content"]
        self.assertIn("main.go", summary_content)
        self.assertIn("go test -race", summary_content)
        self.assertIn("Refatore o arquivo main.go", summary_content)

    def test_git_status_and_diff_tool(self) -> None:
        from celine.tools.files import git_status_and_diff
        result = git_status_and_diff(path=".")
        self.assertIn("Git Status", result)
        self.assertIn("diff", result.lower())

    def test_desktop_notify_empty_message_validation(self) -> None:
        from celine.tools.system import desktop_notify
        res = desktop_notify(title="Celine", message="")
        self.assertIn("Erro", res)


if __name__ == "__main__":
    unittest.main()

