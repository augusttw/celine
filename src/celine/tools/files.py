from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from celine.tools.registry import tool


def _resolve_path(raw: str) -> Path:
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    return p.resolve()


@tool(
    name="read_file",
    description="Lê o conteúdo de um arquivo de texto com numeração de linhas opcional e paginação de linhas.",
)
def read_file(path: str, start_line: int = 1, end_line: int = 500) -> str:
    """Lê um arquivo de texto local com numeração de linha.

    Args:
        path: Caminho do arquivo a ser lido.
        start_line: Linha inicial (1-indexed).
        end_line: Linha final (1-indexed).
    """
    file_path = _resolve_path(path)
    if not file_path.exists():
        return f"Arquivo não encontrado: {file_path}"
    if not file_path.is_file():
        return f"O caminho não é um arquivo: {file_path}"

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        total_lines = len(lines)

        start = max(1, start_line)
        end = min(total_lines, end_line)

        if start > total_lines:
            return f"Arquivo tem apenas {total_lines} linhas. start_line={start} está fora dos limites."

        selected_lines = lines[start - 1 : end]
        numbered = [f"{i + start}: {line}" for i, line in enumerate(selected_lines)]
        output = "\n".join(numbered)

        summary = f"\n\n[Mostrando linhas {start} a {end} de {total_lines} linhas]"
        return output + summary

    except Exception as exc:
        return f"Erro ao ler arquivo {file_path}: {exc}"


@tool(
    name="write_file",
    description="Cria ou sobrescreve um arquivo de texto no disco. Cria diretórios pai automaticamente.",
)
def write_file(path: str, content: str, overwrite: bool = True) -> str:
    """Escreve texto em um arquivo.

    Args:
        path: Caminho de destino.
        content: Conteúdo a ser escrito.
        overwrite: Se True, sobrescreve arquivo existente.
    """
    file_path = _resolve_path(path)
    if file_path.exists() and not overwrite:
        return f"Arquivo já existe e overwrite=False: {file_path}"

    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return f"Arquivo salvo com sucesso: {file_path} ({len(content)} caracteres)"
    except Exception as exc:
        return f"Erro ao escrever arquivo {file_path}: {exc}"


@tool(
    name="edit_file",
    description="Substitui um bloco específico de texto dentro de um arquivo existente.",
)
def edit_file(path: str, target: str, replacement: str) -> str:
    """Edita um arquivo substituindo `target` por `replacement`.

    Args:
        path: Caminho do arquivo a ser modificado.
        target: Texto exato que deve ser substituído.
        replacement: Novo texto de substituição.
    """
    file_path = _resolve_path(path)
    if not file_path.exists():
        return f"Arquivo não encontrado: {file_path}"

    try:
        content = file_path.read_text(encoding="utf-8")
        count = content.count(target)

        if count == 0:
            return f"Erro: O texto alvo ('target') não foi encontrado no arquivo {file_path}."
        if count > 1:
            return f"Erro: O texto alvo aparece {count} vezes no arquivo. Forneça um bloco com contexto único."

        new_content = content.replace(target, replacement, 1)
        file_path.write_text(new_content, encoding="utf-8")
        return f"Arquivo editado com sucesso: {file_path}"
    except Exception as exc:
        return f"Erro ao editar arquivo {file_path}: {exc}"


@tool(
    name="list_dir",
    description="Lista arquivos e diretórios em uma pasta com indicação de tamanho e tipo.",
)
def list_dir(path: str = ".", max_depth: int = 2) -> str:
    """Lista conteúdo de um diretório.

    Args:
        path: Caminho da pasta.
        max_depth: Profundidade máxima de listagem (padrão: 2).
    """
    dir_path = _resolve_path(path)
    if not dir_path.exists():
        return f"Pasta não encontrada: {dir_path}"
    if not dir_path.is_dir():
        return f"O caminho não é uma pasta: {dir_path}"

    results: list[str] = []

    def _scan(current: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            entries = sorted(current.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
            for entry in entries:
                if entry.name.startswith(".") and entry.name in {".git", ".venv", "__pycache__", ".pytest_cache"}:
                    continue
                rel = entry.relative_to(dir_path)
                if entry.is_dir():
                    results.append(f"📁 {rel}/")
                    _scan(entry, depth + 1)
                else:
                    size = entry.stat().st_size if entry.exists() else 0
                    results.append(f"📄 {rel} ({size} B)")
                if len(results) >= 200:
                    return
        except PermissionError:
            results.append(f"⚠️ Sem permissão para ler: {current}")

    _scan(dir_path, 1)
    if not results:
        return f"Pasta {dir_path} está vazia."

    if len(results) >= 200:
        results.append("\n[... listagem limitada a 200 itens ...]")
    return "\n".join(results)


@tool(
    name="find_files",
    description="Busca arquivos correspondentes a um padrão glob dentro de um diretório.",
)
def find_files(pattern: str, path: str = ".") -> str:
    """Encontra arquivos por padrão glob (ex: '*.py', '**/*.ts').

    Args:
        pattern: Padrão glob de busca.
        path: Pasta raiz para busca.
    """
    root = _resolve_path(path)
    if not root.exists():
        return f"Pasta não encontrada: {root}"

    matches: list[str] = []
    try:
        for p in root.glob(pattern):
            if any(part.startswith(".") and part in {".git", ".venv", "__pycache__"} for part in p.parts):
                continue
            rel = p.relative_to(root)
            matches.append(str(rel) + ("/" if p.is_dir() else ""))
            if len(matches) >= 100:
                break
    except Exception as exc:
        return f"Erro na busca: {exc}"

    if not matches:
        return f"Nenhum arquivo encontrado para o padrão '{pattern}' em {root}."

    return "\n".join(matches[:100])


@tool(
    name="grep_search",
    description="Pesquisa ocorrências de um termo ou regex dentro dos arquivos de um diretório.",
)
def grep_search(query: str, path: str = ".", is_regex: bool = False, max_results: int = 30) -> str:
    """Pesquisa texto em arquivos.

    Args:
        query: Termo ou expressão regular.
        path: Pasta raiz da pesquisa.
        is_regex: Se True, interpreta query como regex.
        max_results: Número máximo de ocorrências retornadas.
    """
    root = _resolve_path(path)
    if not root.exists():
        return f"Pasta não encontrada: {root}"

    results: list[str] = []
    flags = 0 if is_regex else re.IGNORECASE
    compiled = re.compile(query if is_regex else re.escape(query), flags)

    for dirpath, dirnames, filenames in os.walk(root):
        # Ignore common noise dirs
        dirnames[:] = [d for d in dirnames if d not in {".git", ".venv", "__pycache__", "node_modules", ".pytest_cache"}]
        for fname in filenames:
            fpath = Path(dirpath) / fname
            try:
                text = fpath.read_text(encoding="utf-8", errors="ignore")
                for line_idx, line in enumerate(text.splitlines(), start=1):
                    if compiled.search(line):
                        rel = fpath.relative_to(root)
                        results.append(f"{rel}:{line_idx}: {line.strip()[:180]}")
                        if len(results) >= max_results:
                            return "\n".join(results) + f"\n[... limitado a {max_results} resultados ...]"
            except Exception:
                continue

    if not results:
        return f"Nenhuma correspondência encontrada para '{query}' em {root}."
    return "\n".join(results)


@tool(
    name="git_status_and_diff",
    description="Inspeciona o status e as alterações recentes (diff) do repositório Git no diretório especificado.",
)
def git_status_and_diff(path: str = ".", max_diff_lines: int = 150) -> str:
    """Retorna o git status e o git diff do repositório.

    Args:
        path: Caminho da pasta do repositório.
        max_diff_lines: Limite de linhas do diff retornado.
    """
    root = _resolve_path(path)
    if not root.exists():
        return f"Pasta não encontrada: {root}"

    import subprocess

    try:
        status_proc = subprocess.run(
            ["git", "status", "--short", "--branch"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if status_proc.returncode != 0:
            return f"Não é um repositório git ou erro ao executar git: {status_proc.stderr.strip()}"

        diff_proc = subprocess.run(
            ["git", "diff", "--stat"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )

        diff_detail = subprocess.run(
            ["git", "diff"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )

        diff_lines = diff_detail.stdout.splitlines()
        truncated = False
        if len(diff_lines) > max_diff_lines:
            diff_text = "\n".join(diff_lines[:max_diff_lines]) + f"\n\n[... diff truncado em {max_diff_lines} linhas ...]"
        else:
            diff_text = "\n".join(diff_lines)

        output = [
            f"### Git Status ({root}):",
            status_proc.stdout.strip() or "(working tree clean)",
            "",
            "### Resumo de Modificações (diff --stat):",
            diff_proc.stdout.strip() or "(nenhuma alteração pendente)",
        ]

        if diff_text.strip():
            output.extend(["", "### Diff Detalhado:", diff_text])

        return "\n".join(output)
    except Exception as exc:
        return f"Erro ao inspecionar git: {exc}"

