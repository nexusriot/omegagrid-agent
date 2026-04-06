from __future__ import annotations

import logging
import os
import subprocess
from typing import Any, Dict

from skills.base import BaseSkill

logger = logging.getLogger(__name__)

# Commands that are never allowed for safety
_BLOCKED_PREFIXES = ("rm -rf /", "mkfs", "dd if=", ":(){", "shutdown", "reboot", "halt", "poweroff")


class SshCommandSkill(BaseSkill):
    """Execute a command on a remote host via SSH."""

    name = "ssh"
    description = (
        "Run a command on a remote host via SSH. "
        "Requires the host to be configured (key-based auth, no password prompts). "
        "Returns stdout, stderr, and exit code."
    )
    parameters = {
        "host": {"type": "string", "description": "SSH target: user@hostname or hostname (uses default user)", "required": True},
        "command": {"type": "string", "description": "Shell command to execute on the remote host", "required": True},
        "port": {"type": "number", "description": "SSH port (default 22)", "required": False},
        "timeout": {"type": "number", "description": "Max seconds to wait (default 30)", "required": False},
        "identity_file": {"type": "string", "description": "Path to SSH private key (optional, uses default if not set)", "required": False},
    }

    def __init__(self, enabled: bool = False, max_output_chars: int = 4000,
                 default_identity_file: str = "", default_user: str = ""):
        self.enabled = enabled
        self.max_output_chars = max_output_chars
        self.default_identity_file = default_identity_file
        self.default_user = default_user

    def execute(self, host: str = "", command: str = "", port: int = 22,
                timeout: int = 30, identity_file: str = "", **kwargs) -> Dict[str, Any]:
        if not self.enabled:
            return {"error": "SSH skill is disabled. Set SKILL_SSH_ENABLED=true to enable."}

        if not host:
            return {"error": "host is required (e.g. 'user@hostname' or 'hostname')"}
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

        # Add default user if host doesn't contain @
        target = host.strip()
        if "@" not in target and self.default_user:
            target = f"{self.default_user}@{target}"

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
