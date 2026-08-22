from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from celine.config import CelineConfig
from celine.providers.catalog import ModelCatalog
from celine.runtime import CelineRuntime
from celine.ui.stream import _bubble
from celine.tools.memory_tools import remember
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

    def test_thinking_panel_matches_golden_snapshot(self) -> None:
        console = Console(record=True, width=72)
        console.print(_bubble("", title="celine  ·  pensando…", border="#aa91b7", empty="pensando…"))
        snapshot = Path(__file__).parent / "snapshots" / "thinking.txt"
        self.assertEqual(console.export_text().strip(), snapshot.read_text(encoding="utf-8").strip())


if __name__ == "__main__":
    unittest.main()
