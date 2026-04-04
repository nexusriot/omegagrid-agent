from __future__ import annotations

from typing import Any, Dict, List

from skills.base import BaseSkill


class SkillRegistry:
    """Registry that holds all available skills for the agent."""

    def __init__(self):
        self._skills: Dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill):
        self._skills[skill.name] = skill

    def get(self, name: str) -> BaseSkill | None:
        return self._skills.get(name)

    def list_names(self) -> List[str]:
        return list(self._skills.keys())

    def describe(self) -> List[Dict[str, Any]]:
        return [s.schema() for s in self._skills.values()]

    def describe_for_prompt(self) -> str:
        """Format skill descriptions for the LLM system prompt."""
        if not self._skills:
            return ""
        lines = []
        for s in self._skills.values():
            params = ", ".join(
                f"{k}" + (f" (required)" if p.get("required") else " (optional)")
                for k, p in s.parameters.items()
            )
            lines.append(f"- {s.name}({params}): {s.description}")
        return "\n".join(lines)
