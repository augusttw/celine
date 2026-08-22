from __future__ import annotations

import shutil
from pathlib import Path

TEXT_SUFFIXES = {
    ".md", ".txt", ".py", ".sh", ".bash", ".yaml", ".yml",
    ".json", ".toml", ".js", ".mjs", ".ts", ".tsx",
}
RUNTIME_NOTICE = """\
> **Celine runtime boundary:** this is technical documentation for Celine's internal executor.
> Celine is the agent's only public identity and her state lives in `~/.celine/`.
> Commands named `hermes` and upstream package names are implementation details, not her name or home.

"""


def normalize_celine_skills(home: Path) -> tuple[int, int]:
    """Keep installed skill paths and the runtime hub scoped to Celine.

    Returns ``(files_changed, replacements)``. The pass is idempotent and only
    rewrites explicit default-home literals; technical command/package names are
    preserved so upstream integrations continue to work.
    """

    root = home / "skills"
    if not root.is_dir():
        return 0, 0

    legacy_hub = root / "autonomous-ai-agents" / "hermes-agent"
    celine_hub = root / "autonomous-ai-agents" / "celine-runtime"
    if legacy_hub.is_dir():
        if celine_hub.exists():
            shutil.copytree(legacy_hub, celine_hub, dirs_exist_ok=True)
            shutil.rmtree(legacy_hub)
        else:
            legacy_hub.rename(celine_hub)

    files_changed = 0
    replacements = 0
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            original = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        count = original.count("~/.hermes")
        updated = original.replace("~/.hermes", "~/.celine")

        if path == celine_hub / "SKILL.md":
            updated = updated.replace("name: hermes-agent\n", "name: celine-runtime\n", 1)
            updated = updated.replace(
                'description: "Use, configure, theme, extend, and orchestrate Hermes Agent."',
                'description: "Use when configuring or extending Celine runtime features."',
                1,
            )
            updated = updated.replace("# Hermes Agent\n", "# Celine Runtime\n", 1)
            updated = updated.replace(
                "Hermes Agent is an open-source AI agent framework by Nous Research",
                "Celine is an independent digital agent whose internal runtime "
                "is an open-source framework by Nous Research",
                1,
            )
            updated = updated.replace("What makes Hermes different:", "What makes Celine capable:", 1)
            identity_replacements = {
                "Hermes learns from experience": "Celine learns from experience",
                "Hermes Agent framework": "the internal runtime",
                "Hermes works with any LLM provider": "Celine works with any LLM provider",
                "Hermes instances": "Celine instances",
                "every Hermes feature": "every Celine feature",
                "a Hermes feature": "a Celine feature",
                '"can Hermes do X?"': '"can Celine do X?"',
                '"Hermes can\'t do that"': '"Celine can\'t do that"',
                "Hermes ships far more": "Celine ships far more",
                "everything else Hermes ships": "everything else Celine ships",
                "Spawning Additional Hermes Instances": "Spawning Additional Celine Instances",
                "additional Hermes processes": "additional Celine processes",
                "Hermes uses prompt_toolkit": "Celine uses prompt_toolkit",
                "Three real cap paths in Hermes": "Three real cap paths in Celine's runtime",
            }
            for source, replacement in identity_replacements.items():
                updated = updated.replace(source, replacement)
            if RUNTIME_NOTICE.strip() not in updated:
                marker = "# Celine Runtime\n\n"
                updated = updated.replace(marker, marker + RUNTIME_NOTICE, 1)

        if updated == original:
            continue
        path.write_text(updated, encoding="utf-8")
        files_changed += 1
        replacements += count
    return files_changed, replacements