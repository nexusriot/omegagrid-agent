from __future__ import annotations

import subprocess
from typing import Any, Dict

from skills.base import BaseSkill

# Commands that are never allowed for safety
_BLOCKED_PREFIXES = ("rm -rf /", "mkfs", "dd if=", ":(){", "shutdown", "reboot", "halt", "poweroff")


class ShellCommandSkill(BaseSkill):
    """Execute a shell command and return stdout/stderr. Has safety guards."""

    name = "shell"
    description = "Run a shell command on the host and return output. Use for system info, file ops, etc."
    parameters = {
        "command": {"type": "string", "description": "Shell command to execute", "required": True},
        "timeout": {"type": "number", "description": "Max seconds to wait (default 30)", "required": False},
    }

    def __init__(self, enabled: bool = False, max_output_chars: int = 4000):
        self.enabled = enabled
        self.max_output_chars = max_output_chars

    def execute(self, command: str, timeout: int = 30, **kwargs) -> Dict[str, Any]:
        if not self.enabled:
            return {"error": "Shell skill is disabled. Set SKILL_SHELL_ENABLED=true to enable."}

        cmd_lower = command.strip().lower()
        for prefix in _BLOCKED_PREFIXES:
            if cmd_lower.startswith(prefix):
                return {"error": f"Blocked dangerous command: {command}"}

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            stdout = result.stdout[:self.max_output_chars] if result.stdout else ""
            stderr = result.stderr[:self.max_output_chars] if result.stderr else ""
            return {
                "exit_code": result.returncode,
                "stdout": stdout,
                "stderr": stderr,
            }
        except subprocess.TimeoutExpired:
            return {"error": f"Command timed out after {timeout}s"}
        except Exception as e:
            return {"error": str(e)}
