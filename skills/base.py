from __future__ import annotations

from typing import Any, Dict


class BaseSkill:
    """Base class for agent skills.

    A skill is a higher-level capability than a tool. Skills can:
    - Have parameters with descriptions
    - Be discovered and invoked by the agent via the tool-call mechanism
    - Call external APIs, run shell commands, or compose other tools
    """

    name: str = "base_skill"
    description: str = "Base skill"
    parameters: Dict[str, Dict[str, Any]] = {}

    def schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError
