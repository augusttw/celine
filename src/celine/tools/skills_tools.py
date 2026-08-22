from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from celine.config import CELINE_HOME, assert_celine_boundary
from celine.tools.registry import tool


def _get_skill_search_roots() -> list[Path]:
    assert_celine_boundary(CELINE_HOME)
    roots = [CELINE_HOME / "skills"]
    return [r for r in roots if r.exists() and r.is_dir()]


def discover_all_skills() -> dict[str, dict[str, Any]]:
    """Recursively finds skills owned by the Celine profile only."""
    skills_map: dict[str, dict[str, Any]] = {}

    for root in _get_skill_search_roots():
        for skill_file in root.rglob("SKILL.md"):
            rel_path = skill_file.parent.relative_to(root)
            skill_id = str(rel_path).replace("\\", "/")

            name = skill_file.parent.name
            description = "Habilidade especializada"
            category = skill_id.split("/")[0] if "/" in skill_id else "general"

            try:
                content = skill_file.read_text(encoding="utf-8", errors="replace")
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        frontmatter = yaml.safe_load(parts[1]) or {}
                        name = frontmatter.get("name", name)
                        description = frontmatter.get("description", description)
                else:
                    for line in content.splitlines()[:10]:
                        if line.startswith("# "):
                            description = line.replace("# ", "").strip()
                            break
            except Exception:
                pass

            skills_map[skill_id] = {
                "id": skill_id,
                "name": name,
                "description": description,
                "category": category,
                "path": str(skill_file),
            }

    return skills_map


@tool(
    name="list_skills",
    description="Lista todas as habilidades (skills) técnicas e especializadas disponíveis no sistema.",
)
def list_skills() -> str:
    """Lista todas as skills descobertas com categoria e descrição."""
    skills = discover_all_skills()
    if not skills:
        return "Nenhuma skill encontrada em ~/.celine/skills."

    by_category: dict[str, list[dict[str, Any]]] = {}
    for s in skills.values():
        cat = s["category"]
        by_category.setdefault(cat, []).append(s)

    lines: list[str] = [f"Total de {len(skills)} skills disponíveis:\n"]
    for cat, items in sorted(by_category.items()):
        lines.append(f"### Categoria: `{cat}`")
        for item in sorted(items, key=lambda x: x["id"]):
            lines.append(f"- **`{item['id']}`** ({item['name']}): {item['description']}")
        lines.append("")

    return "\n".join(lines)


@tool(
    name="read_skill",
    description="Carrega as instruções detalhadas (SKILL.md) de uma habilidade para orientar o plano de código, review ou execução.",
)
def read_skill(skill_name: str) -> str:
    """Lê o arquivo de instruções de uma skill.

    Args:
        skill_name: Identificador da skill (ex: 'software-development/code-review', 'plan', 'github/github-pr-workflow').
    """
    target = skill_name.strip().lower().replace(" ", "-")
    skills = discover_all_skills()

    # 1. Exact match by ID
    for s_id, s_data in skills.items():
        if s_id.lower() == target or s_data["name"].lower() == target:
            try:
                return Path(s_data["path"]).read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                return f"Erro ao ler skill {s_id}: {e}"

    # 2. Suffix match (e.g. 'code-review' matches 'software-development/code-review')
    for s_id, s_data in skills.items():
        if s_id.lower().endswith(f"/{target}") or target in s_id.lower():
            try:
                return Path(s_data["path"]).read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                return f"Erro ao ler skill {s_id}: {e}"

    return f"Skill '{skill_name}' não encontrada. Use 'list_skills' para consultar os identificadores válidos."
