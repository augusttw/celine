from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

PLATFORM_CREDENTIAL_KEYS = {
    "telegram": (("TELEGRAM_BOT_TOKEN",),),
    "discord": (("DISCORD_BOT_TOKEN",),),
    "slack": (("SLACK_BOT_TOKEN",),),
    "whatsapp": (("WHATSAPP_ENABLED",),),
    "signal": (("SIGNAL_HTTP_URL", "SIGNAL_ACCOUNT"),),
    "matrix": (("MATRIX_ACCESS_TOKEN",),),
    "email": (("EMAIL_ADDRESS", "EMAIL_PASSWORD", "EMAIL_IMAP_HOST", "EMAIL_SMTP_HOST"),),
    "sms": (("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER"),),
}
PLATFORMS = tuple(PLATFORM_CREDENTIAL_KEYS)


def _notification_env() -> dict[str, str] | None:
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


def _scalar_yaml(path: Path, dotted_key: str) -> str | None:
    if not path.exists():
        return None
    target = dotted_key.split(".")
    stack: list[tuple[int, str]] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw.strip() or raw.lstrip().startswith(("#", "-")) or ":" not in raw:
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        key, value = raw.strip().split(":", 1)
        while stack and stack[-1][0] >= indent:
            stack.pop()
        current = [item[1] for item in stack] + [key.strip()]
        value = value.strip().strip("'\"")
        if current == target and value:
            return value
        if not value:
            stack.append((indent, key.strip()))
    return None


def _env_key_names(path: Path) -> set[str]:
    names: set[str] = set()
    if not path.exists():
        return names
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() and value.strip().strip("'\""):
            names.add(key.strip())
    return names


def presence_status(home: Path | None = None) -> dict[str, Any]:
    root = (home or Path(os.environ.get("CELINE_HOME", Path.home() / ".celine"))).expanduser().resolve()
    config = root / "config.yaml"
    env_names = _env_key_names(root / ".env")
    platforms = []
    for name in PLATFORMS:
        credential_groups = PLATFORM_CREDENTIAL_KEYS[name]
        credentials_present = any(all(key in env_names for key in group) for group in credential_groups)
        enabled = (_scalar_yaml(config, f"gateway.platforms.{name}.enabled") or "false").lower() == "true"
        platforms.append(
            {
                "name": name,
                "credentials_present": credentials_present,
                "enabled": enabled,
                "connected": None,
            }
        )
    return {
        "profile_home": str(root),
        "desktop_notification_transport_available": bool(shutil.which("notify-send"))
        and _notification_env() is not None,
        "platforms": platforms,
        "note": "connected requer o status do gateway em execução; nenhuma credencial é exibida",
    }


def notify_desktop(title: str, message: str) -> dict[str, Any]:
    clean_title = " ".join(str(title).split()).strip() or "Celine"
    clean_message = " ".join(str(message).split()).strip()
    if len(clean_title) > 80:
        raise ValueError("title excede 80 caracteres.")
    if not clean_message:
        raise ValueError("message é obrigatório.")
    if len(clean_message) > 500:
        raise ValueError("message excede 500 caracteres.")
    binary = shutil.which("notify-send")
    if not binary:
        return {"success": False, "reason": "notify-send indisponível"}
    env = _notification_env()
    if env is None:
        return {"success": False, "reason": "sessão DBus indisponível"}
    process = subprocess.run(
        [binary, "--app-name=Celine", "--icon=dialog-information", clean_title, clean_message],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        env=env,
    )
    if process.returncode != 0:
        return {"success": False, "reason": (process.stderr or process.stdout).strip() or "notify-send falhou"}
    return {"success": True, "title": clean_title}


def handle_presence(args: dict[str, Any], **_: Any) -> str:
    try:
        action = str(args.get("action", "status")).strip()
        if action == "status":
            return json.dumps({"success": True, **presence_status()}, ensure_ascii=False)
        if action == "notify":
            origin = str(args.get("origin", "manual"))
            if origin == "proactive":
                from .storage import RelationshipStore

                config = RelationshipStore().pulse_status()["config"]
                if not config.get("desktop_notifications"):
                    return json.dumps(
                        {"success": False, "error": "notificações proativas não foram autorizadas"},
                        ensure_ascii=False,
                    )
            result = notify_desktop(str(args.get("title", "Celine")), str(args.get("message", "")))
            return json.dumps(result, ensure_ascii=False)
        return json.dumps({"success": False, "error": "action inválida"}, ensure_ascii=False)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)
