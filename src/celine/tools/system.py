from __future__ import annotations

import os
import platform
import shutil
import time
from datetime import datetime
from pathlib import Path

import psutil

from celine.tools.registry import tool


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
