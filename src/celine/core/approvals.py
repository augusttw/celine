from __future__ import annotations

import hashlib
import json
import re
import shlex
import threading
from dataclasses import dataclass
from pathlib import Path

import yaml

from celine.config import CELINE_HOME


@dataclass(frozen=True)
class PendingApproval:
    token: str
    effect: str
    payload: str
    reason: str


class ApprovalManager:
    """In-process, one-shot approval broker for visible or destructive effects."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._pending: dict[str, PendingApproval] = {}
        self._approved: set[str] = set()

    @staticmethod
    def mode() -> str:
        try:
            data = yaml.safe_load((CELINE_HOME / "config.yaml").read_text(encoding="utf-8")) or {}
            mode = str((data.get("approvals") or {}).get("mode", "manual")).casefold()
        except (OSError, yaml.YAMLError, AttributeError):
            mode = "manual"
        return mode if mode in {"manual", "off", "deny"} else "manual"

    @staticmethod
    def _token(effect: str, payload: str) -> str:
        digest = hashlib.sha256(f"{effect}\0{payload}".encode()).hexdigest()[:10]
        return digest.upper()

    def authorize(self, effect: str, payload: str, reason: str) -> str | None:
        mode = self.mode()
        if mode == "off":
            return None
        token = self._token(effect, payload)
        with self._lock:
            if token in self._approved:
                self._approved.remove(token)
                self._pending.pop(token, None)
                return None
            if mode == "deny":
                return f"Blocked by approvals.mode=deny: {reason}"
            self._pending[token] = PendingApproval(token, effect, payload, reason)
        return (
            f"APPROVAL REQUIRED [{token}]: {reason}. "
            f"Tell the user to run /approve {token}, then /retry. Approval is one-shot and exact."
        )

    def approve(self, token: str) -> PendingApproval | None:
        normalized = token.strip().upper()
        with self._lock:
            pending = self._pending.get(normalized)
            if pending:
                self._approved.add(normalized)
            return pending

    def pending(self) -> list[PendingApproval]:
        with self._lock:
            return list(self._pending.values())


approval_manager = ApprovalManager()

_SENSITIVE_NAMES = {
    "auth.json", ".env", ".npmrc", ".pypirc", "credentials", "credentials.json",
    "id_rsa", "id_ed25519", "id_ecdsa", "id_dsa", "known_hosts.old",
}


def sensitive_path_reason(path: Path) -> str | None:
    resolved = path.expanduser().resolve()
    if resolved.name.casefold() in _SENSITIVE_NAMES:
        return "credential-bearing files are never exposed to the model"
    if any(part.casefold() in {".ssh", ".gnupg", "keyrings"} for part in resolved.parts):
        return "private key and keyring directories are never exposed to the model"
    if resolved.suffix.casefold() in {".pem", ".key", ".p12", ".pfx"}:
        return "private key material is never exposed to the model"
    return None


def command_sensitive_reason(command: str) -> str | None:
    lowered = command.casefold()
    markers = (
        "auth.json", "/.env", " .env", "/.ssh", "id_rsa", "id_ed25519", "id_ecdsa",
        ".pem", ".p12", ".pfx", "/.gnupg", "credentials.json",
    )
    return "the command targets credential or private-key material" if any(x in lowered for x in markers) else None

_HIGH_RISK_COMMANDS = re.compile(
    r"\b(sudo|su\s|rm\s|rmdir\s|dd\s|mkfs|fdisk|parted|shutdown|reboot|poweroff|"
    r"chown\s|chmod\s|mount\s|umount\s|kill\s|pkill\s|killall\s|systemctl\s|dinitctl\s|"
    r"pacman\s|apt\s|dnf\s|yum\s|brew\s|pip\s+install|uv\s+tool\s+install|"
    r"git\s+(push|commit|reset|clean|checkout|restore)|gh\s+(pr|repo|issue))\b",
    re.IGNORECASE,
)
_SHELL_MUTATION = re.compile(r"(^|[^<])>{1,2}|\b(tee|truncate|install|mv|cp|mkdir|touch|ln)\b", re.IGNORECASE)


def command_approval_reason(command: str) -> str | None:
    clean = " ".join(command.split())
    if _HIGH_RISK_COMMANDS.search(clean):
        return "the shell command may change system, repository, process, package, or remote state"
    redirection_checked = re.sub(r"(?:\d?>|\d?>>)\s*/dev/null\b", "", clean)
    if _SHELL_MUTATION.search(redirection_checked):
        return "the shell command writes to the filesystem"
    try:
        first = shlex.split(clean)[0] if clean else ""
    except ValueError:
        return "the shell command could not be parsed safely"
    if first in {"bash", "sh", "zsh", "fish", "env"}:
        return f"the shell wrapper '{first}' can conceal an unreviewed command"
    if first in {"python", "python3", "node", "ruby", "perl"} and re.search(r"(?:^|\s)(?:-c|-e)(?:\s|$)", clean):
        return f"inline {first} code can perform unrestricted effects"
    read_only = {
        "pwd", "ls", "rg", "grep", "find", "sed", "head", "tail", "cat", "stat", "file", "du", "df",
        "ps", "date", "uname", "which", "type", "readlink", "git", "sqlite3", "wc", "sort", "cut",
        "python", "python3", "pytest", "go", "npm", "cargo", "make", "cmake", "ninja",
    }
    if first not in read_only:
        return f"the shell program '{first or 'unknown'}' is not in Celine's reviewed command set"
    return None


def path_approval_reason(path: Path) -> str | None:
    resolved = path.resolve()
    cwd = Path.cwd().resolve()
    if resolved == (CELINE_HOME / "config.yaml").resolve():
        return "the target contains security-sensitive configuration"
    if ".git" in resolved.parts:
        return "the target is inside Git's internal metadata"
    if not resolved.is_relative_to(cwd):
        return f"the target is outside the current workspace ({cwd})"
    return None


def approval_payload(kind: str, value: object) -> str:
    return json.dumps({"kind": kind, "value": value}, ensure_ascii=False, sort_keys=True, default=str)
