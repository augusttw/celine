from __future__ import annotations

import json
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
from celine.legacy_sessions import migrate_legacy_sessions
from celine.evaluation import BehaviorEvaluator, LIVE_SCENARIOS
from celine.core.approvals import (
    ApprovalManager,
    command_approval_reason,
    command_sensitive_reason,
    path_approval_reason,
    sensitive_path_reason,
)
from celine.tools import registry
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

    def test_sessions_use_canonical_state_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "state.db"
            manager = SessionManager(db)
            session_id = manager.create_session("Canonical")
            manager.save_message(session_id, "user", "hello")
            self.assertEqual(manager.get_messages(session_id)[0]["content"], "hello")
            import sqlite3

            connection = sqlite3.connect(db)
            try:
                tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            finally:
                connection.close()
            self.assertTrue({"sessions", "messages"}.issubset(tables))

    def test_legacy_session_migration_is_idempotent(self) -> None:
        import sqlite3

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            SessionManager(root / "state.db")
            legacy = sqlite3.connect(root / "celine.db")
            try:
                legacy.executescript(
                    """CREATE TABLE sessions (
                           id TEXT PRIMARY KEY, title TEXT, created_at TEXT, updated_at TEXT);
                       CREATE TABLE chat_history (
                           id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT,
                           tool_calls TEXT, tool_call_id TEXT, name TEXT, created_at TEXT);
                       CREATE TABLE memories (
                           id INTEGER PRIMARY KEY, category TEXT, content TEXT UNIQUE, created_at TEXT);"""
                )
                legacy.execute(
                    "INSERT INTO sessions VALUES ('legacy_one', 'Legacy', '2026-01-01', '2026-01-01')"
                )
                legacy.execute(
                    "INSERT INTO chat_history VALUES (1, 'legacy_one', 'user', 'hello', NULL, NULL, NULL, '2026-01-01')"
                )
                legacy.execute(
                    "INSERT INTO memories VALUES (1, 'preference', 'likes exact tests', '2026-01-01')"
                )
                legacy.commit()
            finally:
                legacy.close()
            self.assertEqual(migrate_legacy_sessions(root), (1, 1))
            self.assertEqual(migrate_legacy_sessions(root), (0, 0))
            canonical = sqlite3.connect(root / "state.db")
            try:
                self.assertEqual(canonical.execute("SELECT COUNT(*) FROM messages").fetchone()[0], 1)
                self.assertEqual(canonical.execute("SELECT COUNT(*) FROM memories").fetchone()[0], 1)
            finally:
                canonical.close()

    def test_native_companion_tools_are_registered(self) -> None:
        names = {schema["function"]["name"] for schema in registry.get_schemas()}
        self.assertTrue({"celine_relationship", "celine_pulse", "celine_presence"}.issubset(names))

    def test_optional_tool_parameters_keep_boolean_schema(self) -> None:
        pulse = next(
            schema for schema in registry.get_schemas() if schema["function"]["name"] == "celine_pulse"
        )
        properties = pulse["function"]["parameters"]["properties"]
        self.assertEqual(properties["enabled"]["type"], "boolean")
        self.assertEqual(properties["cadence_hours"]["type"], "integer")

    def test_approval_is_exact_and_one_shot(self) -> None:
        manager = ApprovalManager()
        blocked = manager.authorize("shell", "rm target", "destructive test")
        self.assertIn("APPROVAL REQUIRED", blocked or "")
        token = manager.pending()[0].token
        self.assertIsNotNone(manager.approve(token))
        self.assertIsNone(manager.authorize("shell", "rm target", "destructive test"))
        self.assertIn("APPROVAL REQUIRED", manager.authorize("shell", "rm target", "destructive test") or "")

    def test_shell_policy_flags_effects_and_allows_inspection(self) -> None:
        self.assertIsNone(command_approval_reason("git status --short"))
        self.assertIsNotNone(command_approval_reason("git push origin main"))
        self.assertIsNotNone(command_approval_reason("python -c 'open(\"x\", \"w\").write(\"x\")'"))

    def test_path_policy_protects_outside_workspace(self) -> None:
        outside = Path("/tmp/celine-policy-test").resolve()
        self.assertIsNotNone(path_approval_reason(outside))

    def test_secret_files_are_never_exposed_to_model(self) -> None:
        self.assertIsNotNone(sensitive_path_reason(Path.home() / ".celine/auth.json"))
        self.assertIsNotNone(sensitive_path_reason(Path.home() / ".ssh/id_ed25519"))
        self.assertIsNotNone(command_sensitive_reason("cat ~/.celine/auth.json"))

    def test_soul_is_english_serious_and_opinionated(self) -> None:
        soul = (Path(__file__).parents[1] / "src/celine/assets/SOUL.md").read_text(encoding="utf-8")
        self.assertIn("## A mind of your own", soul)
        self.assertIn("Have taste", soul)
        self.assertIn("Default to Brazilian Portuguese", soul)
        self.assertNotIn("infinitely devoted", soul.casefold())

    def test_live_evaluator_preserves_scenario_order_when_parallel(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            evaluator = BehaviorEvaluator(Path(directory))

            def fake_run(scenario: object, timeout: int) -> dict[str, object]:
                del timeout
                return {"name": scenario.name, "passed": True, "detail": "ok"}

            with patch.object(evaluator, "_live_scenario", side_effect=fake_run):
                report = evaluator.live(workers=3, batched=False)
        self.assertEqual([item["name"] for item in report["checks"]], [item.name for item in LIVE_SCENARIOS])
        self.assertTrue(report["ok"])

    def test_live_batch_parses_each_behavior_independently(self) -> None:
        from types import SimpleNamespace

        chunks = [[SimpleNamespace(text=scenario.expected_any[0])] for scenario in LIVE_SCENARIOS]
        with tempfile.TemporaryDirectory() as directory:
            evaluator = BehaviorEvaluator(Path(directory))
            with patch("celine.providers.router.ProviderRouter.get_provider") as get_provider, patch(
                "celine.core.persona.persona_manager.build_system_prompt", return_value="Celine"
            ):
                get_provider.return_value.stream_chat.side_effect = chunks
                report = evaluator.live()
        self.assertEqual(report["passed"], len(LIVE_SCENARIOS))
        self.assertTrue(report["ok"])

    def test_live_matcher_accepts_valid_natural_variation(self) -> None:
        examples = {
            "anti_dependencia": "Não incentivo abandono de relações humanas; valorizo limites saudáveis.",
            "erro_sem_drama": "Percebi a inconsistência e corrigi prontamente, sem drama.",
            "continuidade": "Recupero contexto de sessões anteriores antes de responder.",
        }
        for name, answer in examples.items():
            scenario = next(item for item in LIVE_SCENARIOS if item.name == name)
            self.assertTrue(any(term.casefold() in answer.casefold() for term in scenario.expected_any))
            self.assertFalse(any(term.casefold() in answer.casefold() for term in scenario.forbidden))


if __name__ == "__main__":
    unittest.main()
