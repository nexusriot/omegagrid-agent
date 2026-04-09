from __future__ import annotations

import base64
import logging
import os
import stat
import subprocess
import tempfile
from typing import Any, Dict

from skills.base import BaseSkill

logger = logging.getLogger(__name__)

# Commands that are never allowed for safety
_BLOCKED_PREFIXES = ("rm -rf /", "mkfs", "dd if=", ":(){", "shutdown", "reboot", "halt", "poweroff")


def _materialize_private_key(content: str) -> str:
    """Write a private key string to a chmod-600 temp file and return its path.

    Accepts either:
      - A raw PEM key (with real newlines or escaped \\n sequences)
      - A base64-encoded PEM blob
    """
    text = (content or "").strip()
    if not text:
        return ""

    # Tolerate escaped newlines from .env files: KEY="-----BEGIN...\n..."
    if "\\n" in text and "\n" not in text:
        text = text.replace("\\n", "\n")

    # Heuristic: if it doesn't look like PEM, try base64-decoding it
    if not text.lstrip().startswith("-----BEGIN"):
        try:
            decoded = base64.b64decode(text, validate=False).decode("utf-8")
            if "-----BEGIN" in decoded:
                text = decoded
        except Exception:
            pass

    if not text.endswith("\n"):
        text += "\n"

    fd, path = tempfile.mkstemp(prefix="omegagrid_ssh_", suffix=".key")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0600
    except Exception:
        try:
            os.remove(path)
        except OSError:
            pass
        raise

    logger.info("SSH skill: materialized private key to %s", path)
    return path


class SshCommandSkill(BaseSkill):
    """Execute a command on a remote host via SSH."""

    name = "ssh"
    description = (
        "Run a command on a remote host via SSH. "
        "Requires the host to be configured (key-based auth, no password prompts). "
        "Returns stdout, stderr, and exit code."
    )
    parameters = {
        "host": {"type": "string", "description": "SSH target hostname or IP. May include user as 'user@hostname'.", "required": True},
        "command": {"type": "string", "description": "Shell command to execute on the remote host", "required": True},
        "user": {"type": "string", "description": "SSH username. Takes priority over the .env default. Optional if host already contains 'user@'.", "required": False},
        "port": {"type": "number", "description": "SSH port (default 22)", "required": False},
        "timeout": {"type": "number", "description": "Max seconds to wait (default 30)", "required": False},
        "identity_file": {"type": "string", "description": "Path to SSH private key (optional, uses default if not set)", "required": False},
    }

    def __init__(self, enabled: bool = False, max_output_chars: int = 4000,
                 default_identity_file: str = "", default_user: str = "",
                 private_key_content: str = ""):
        self.enabled = enabled
        self.max_output_chars = max_output_chars
        self.default_user = default_user

        # If inline key content is supplied via env, materialize it to a
        # temp file and use that as the default identity file.  An explicit
        # SKILL_SSH_IDENTITY_FILE still takes precedence.
        if default_identity_file:
            self.default_identity_file = default_identity_file
        elif private_key_content:
            try:
                self.default_identity_file = _materialize_private_key(private_key_content)
            except Exception as e:
                logger.error("SSH skill: failed to materialize inline key: %s", e)
                self.default_identity_file = ""
        else:
            self.default_identity_file = ""

    def execute(self, host: str = "", command: str = "", user: str = "",
                port: int = 22, timeout: int = 30, identity_file: str = "",
                **kwargs) -> Dict[str, Any]:
        if not self.enabled:
            return {"error": "SSH skill is disabled. Set SKILL_SSH_ENABLED=true to enable."}

        if not host:
            return {"error": "host is required (e.g. 'hostname' or 'user@hostname')"}
        if not command:
            return {"error": "command is required"}

        # Safety check
        cmd_lower = command.strip().lower()
        for prefix in _BLOCKED_PREFIXES:
            if cmd_lower.startswith(prefix):
                return {"error": f"Blocked dangerous command: {command}"}

        # Build SSH command
        ssh_args = [
            "ssh",
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "ConnectTimeout=10",
            "-o", "BatchMode=yes",
            "-p", str(int(port)),
        ]

        key_file = identity_file or self.default_identity_file
        if key_file:
            ssh_args.extend(["-i", key_file])

        # Resolve target user with priority:
        #   1. user@... already inside the host string  (highest)
        #   2. explicit `user` parameter from the prompt
        #   3. self.default_user from .env  (lowest)
        target = host.strip()
        if "@" not in target:
            chosen_user = (user or "").strip() or self.default_user
            if chosen_user:
                target = f"{chosen_user}@{target}"

        ssh_args.append(target)
        ssh_args.append(command)

        logger.info("SSH executing: %s on %s (port %d)", command, target, port)

        try:
            result = subprocess.run(
                ssh_args,
                capture_output=True,
                text=True,
                timeout=min(int(timeout), 120),
            )
            stdout = result.stdout[:self.max_output_chars] if result.stdout else ""
            stderr = result.stderr[:self.max_output_chars] if result.stderr else ""

            return {
                "host": target,
                "command": command,
                "exit_code": result.returncode,
                "stdout": stdout,
                "stderr": stderr,
            }
        except subprocess.TimeoutExpired:
            return {"error": f"SSH command timed out after {timeout}s", "host": target, "command": command}
        except FileNotFoundError:
            return {"error": "ssh binary not found. Ensure openssh-client is installed."}
        except Exception as e:
            return {"error": str(e), "host": target, "command": command}
