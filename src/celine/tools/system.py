from __future__ import annotations

import os
import platform
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

import psutil

from celine.tools.registry import tool


def _get_notification_env() -> dict[str, str] | None:
    env = os.environ.copy()
    if env.get("DBUS_SESSION_BUS_ADDRESS"):
        return env
    if os.name != "posix" or not hasattr(os, "getuid"):
        return None
    runtime = Path(f"/run/user/{os.getuid()}")
    bus = runtime / "bus"
    if not bus.is_socket():
        return None
    env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={bus}"
    env.setdefault("XDG_RUNTIME_DIR", str(runtime))
    return env


@tool(
    name="desktop_notify",
    description="Envia uma notificação visual no desktop (Sway/Wayland) via notify-send com nome do app Celine.",
)
def desktop_notify(title: str = "Celine", message: str = "", urgency: str = "normal") -> str:
    """Envia uma notificação desktop no Wayland/Sway.

    Args:
        title: Título da notificação (ex: 'Celine', 'Build concluído').
        message: Conteúdo da notificação.
        urgency: Nível de urgência: 'low', 'normal', 'critical'.
    """
    clean_title = " ".join(str(title).split()).strip() or "Celine"
    clean_message = " ".join(str(message).split()).strip()

    if not clean_message:
        return "Erro: mensagem de notificação não pode ser vazia."

    binary = shutil.which("notify-send")
    if not binary:
        return "Erro: utilitário 'notify-send' não encontrado no PATH do sistema."

    env = _get_notification_env()
    if env is None:
        return "Erro: barramento D-Bus / XDG_RUNTIME_DIR indisponível para envio de notificações."

    valid_urgencies = {"low", "normal", "critical"}
    urg = urgency if urgency in valid_urgencies else "normal"

    try:
        process = subprocess.run(
            [
                binary,
                "--app-name=Celine",
                "--icon=dialog-information",
                f"--urgency={urg}",
                clean_title,
                clean_message,
            ],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
        if process.returncode != 0:
            err = (process.stderr or process.stdout).strip() or "Falha no notify-send."
            return f"Erro ao enviar notificação: {err}"

        return f"Notificação enviada no desktop com sucesso: '{clean_title}'"
    except Exception as exc:
        return f"Erro ao executar notify-send: {exc}"


@tool(
    name="system_info",
    description="Retorna informações sobre o sistema operacional, uso de CPU, memória RAM, disco e ambiente atual.",
)
def system_info() -> str:
    """Retorna dados do sistema operacional e hardware."""
    try:
        uname = platform.uname()
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        cpu_count = psutil.cpu_count(logical=True)
        cpu_percent = psutil.cpu_percent(interval=0.1)

        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        uptime_str = f"{uptime.days}d {uptime.seconds // 3600}h {(uptime.seconds % 3600) // 60}m"

        return (
            f"**Sistema**: {uname.system} {uname.release} ({uname.machine})\n"
            f"**Host**: {uname.node}\n"
            f"**CPU**: {cpu_count} núcleos ({cpu_percent}% em uso)\n"
            f"**RAM**: {mem.used / (1024**3):.1f} GB / {mem.total / (1024**3):.1f} GB ({mem.percent}%)\n"
            f"**Disco (/)**: {disk.used / (1024**3):.1f} GB / {disk.total / (1024**3):.1f} GB ({disk.percent}%)\n"
            f"**Uptime**: {uptime_str}\n"
            f"**Usuário**: {os.environ.get('USER', 'desconhecido')}\n"
            f"**Shell**: {os.environ.get('SHELL', 'bash')}\n"
            f"**Diretório Atual**: {os.getcwd()}\n"
            f"**Data e Hora**: {datetime.now():%d/%m/%Y %H:%M:%S}"
        )
    except Exception as exc:
        return f"Erro ao coletar dados do sistema: {exc}"


@tool(
    name="current_datetime",
    description="Retorna a data e hora local exata e fuso horário.",
)
def current_datetime() -> str:
    """Retorna a data e hora atual formatada."""
    now = datetime.now()
    return f"Data/Hora local: {now:%A, %d de %B de %Y às %H:%M:%S} (Timestamp: {int(time.time())})"
