from __future__ import annotations

import os
import subprocess
from pathlib import Path

from celine.tools.registry import tool
from celine.core.approvals import (
    approval_manager,
    approval_payload,
    command_approval_reason,
    command_sensitive_reason,
)

MAX_OUTPUT_CHARS = 30000
MAX_OUTPUT_LINES = 800


@tool(
    name="bash",
    description="Executa comandos no shell bash do Linux. Retorna o código de saída, stdout e stderr.",
)
def bash(command: str, timeout: int = 120) -> str:
    """Executa um comando no terminal bash.

    Args:
        command: Comando shell a ser executado.
        timeout: Tempo limite em segundos (padrão: 120).
    """
    if not command.strip():
        return "Comando vazio."

    sensitive = command_sensitive_reason(command)
    if sensitive:
        return f"Blocked: {sensitive}. Inspect only metadata or credential names, never secret values."

    reason = command_approval_reason(command)
    if reason:
        blocked = approval_manager.authorize("shell", approval_payload("shell", command), reason)
        if blocked:
            return blocked

    cwd = os.getcwd()

    try:
        process = subprocess.run(
            ["bash", "-c", command],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            errors="replace",
        )

        stdout = process.stdout
        stderr = process.stderr
        exit_code = process.returncode

        lines_out = stdout.splitlines()
        lines_err = stderr.splitlines()

        output_parts: list[str] = []

        if lines_out:
            if len(lines_out) > MAX_OUTPUT_LINES:
                head = lines_out[:400]
                tail = lines_out[-200:]
                omitted = len(lines_out) - 600
                stdout = "\n".join(head) + f"\n\n[... {omitted} linhas omitidas ...]\n\n" + "\n".join(tail)
            if len(stdout) > MAX_OUTPUT_CHARS:
                stdout = stdout[:MAX_OUTPUT_CHARS] + "\n[... saída truncada por limite de caracteres ...]"
            output_parts.append(stdout)

        if lines_err:
            if len(lines_err) > MAX_OUTPUT_LINES:
                head = lines_err[:200]
                tail = lines_err[-100:]
                omitted = len(lines_err) - 300
                stderr = "\n".join(head) + f"\n\n[... {omitted} linhas de erro omitidas ...]\n\n" + "\n".join(tail)
            if len(stderr) > MAX_OUTPUT_CHARS:
                stderr = stderr[:MAX_OUTPUT_CHARS] + "\n[... erro truncado por limite de caracteres ...]"
            output_parts.append(f"[STDERR]\n{stderr}")

        result_text = "\n".join(output_parts) if output_parts else "(comando executado com sucesso sem saída)"

        if exit_code != 0:
            return f"[Código de saída: {exit_code}]\n{result_text}"

        return result_text

    except subprocess.TimeoutExpired:
        return f"Erro: Comando excedeu o tempo limite de {timeout} segundos."
    except Exception as exc:
        return f"Erro na execução do comando: {exc}"
