"""Skill that lets the agent create new markdown-based skills at runtime.

The agent can decide that a capability is missing and create a new skill
on the fly.  Created skills are persisted as .md files in the skills
directory and registered immediately so they are available within the
same conversation.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict

import yaml

from skills.base import BaseSkill
from skills.markdown_skill import MarkdownSkill, _parse_frontmatter

logger = logging.getLogger(__name__)

_SAFE_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,48}$")


class SkillCreatorSkill(BaseSkill):
    name = "skill_creator"
    description = (
        "Create, list, show, or delete dynamic skills.  Use action='create' "
        "when a user asks for a capability that no existing skill covers."
    )
    parameters: Dict[str, Dict[str, Any]] = {
        "action": {
            "type": "string",
            "description": "One of: create, list, show, delete",
            "required": True,
        },
        "name": {
            "type": "string",
            "description": "Skill name (lowercase, underscores, 2-49 chars).  Required for create/show/delete.",
            "required": False,
        },
        "description": {
            "type": "string",
            "description": "Short skill description for the LLM prompt.  Required for create.",
            "required": False,
        },
        "parameters_schema": {
            "type": "object",
            "description": (
                "Parameter definitions, e.g. "
                '{"city": {"type": "string", "description": "City name", "required": true}}. '
                "Required for create."
            ),
            "required": False,
        },
        "endpoint": {
            "type": "string",
            "description": "HTTP endpoint the skill should call (optional — omit for prompt-only skills).",
            "required": False,
        },
        "method": {
            "type": "string",
            "description": "HTTP method: GET or POST (default GET).  Only used with endpoint.",
            "required": False,
        },
        "instructions": {
            "type": "string",
            "description": "Free-text body / instructions appended after the YAML frontmatter.",
            "required": False,
        },
    }

    def __init__(self, skills_dir: str, skill_registry):
        """
        Args:
            skills_dir:      Filesystem path where .md skill files are stored.
            skill_registry:  The live SkillRegistry instance so we can hot-register.
        """
        self._skills_dir = skills_dir
        self._registry = skill_registry

    def execute(self, **kwargs) -> Dict[str, Any]:
        action = (kwargs.get("action") or "").strip().lower()
        if action == "create":
            return self._create(kwargs)
        if action == "list":
            return self._list()
        if action == "show":
            return self._show(kwargs)
        if action == "delete":
            return self._delete(kwargs)
        return {"error": f"Unknown action '{action}'.  Use create, list, show, or delete."}

    def _create(self, kw: dict) -> Dict[str, Any]:
        name = (kw.get("name") or "").strip().lower()
        if not name:
            return {"error": "Parameter 'name' is required for create."}
        if not _SAFE_NAME_RE.match(name):
            return {"error": f"Invalid skill name '{name}'.  Use lowercase + underscores, 2-49 chars, start with a letter."}

        description = (kw.get("description") or "").strip()
        if not description:
            return {"error": "Parameter 'description' is required for create."}

        params_schema = kw.get("parameters_schema") or kw.get("parameters") or {}
        if isinstance(params_schema, str):
            # LLM sometimes sends JSON string
            import json
            try:
                params_schema = json.loads(params_schema)
            except Exception:
                return {"error": "parameters_schema must be a valid JSON object."}

        endpoint = (kw.get("endpoint") or "").strip()
        method = (kw.get("method") or "GET").strip().upper()
        instructions = (kw.get("instructions") or "").strip()

        # Build YAML frontmatter dict
        meta: Dict[str, Any] = {
            "name": name,
            "description": description,
        }
        if params_schema:
            meta["parameters"] = params_schema
        if endpoint:
            meta["endpoint"] = endpoint
            meta["method"] = method

        # Render the .md file
        frontmatter = yaml.dump(meta, default_flow_style=False, allow_unicode=True).strip()
        parts = ["---", frontmatter, "---"]
        if instructions:
            parts.append("")
            parts.append(instructions)
        content = "\n".join(parts) + "\n"

        # Write file
        os.makedirs(self._skills_dir, exist_ok=True)
        fpath = os.path.join(self._skills_dir, f"{name}.md")
        overwrite = os.path.exists(fpath)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)

        # Hot-register in the live skill registry
        skill = MarkdownSkill(meta=meta, body=instructions)
        self._registry.register(skill)

        logger.info("skill_creator: %s skill '%s' -> %s", "updated" if overwrite else "created", name, fpath)
        return {
            "status": "updated" if overwrite else "created",
            "skill_name": name,
            "file": fpath,
            "description": description,
            "has_endpoint": bool(endpoint),
            "parameters": list(params_schema.keys()) if params_schema else [],
            "hint": f"Skill '{name}' is now registered and can be called immediately.",
        }


    def _list(self) -> Dict[str, Any]:
        # List .md files in skills dir
        md_skills = []
        if os.path.isdir(self._skills_dir):
            for fname in sorted(os.listdir(self._skills_dir)):
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(self._skills_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        raw = f.read()
                    meta, _ = _parse_frontmatter(raw)
                    md_skills.append({
                        "name": meta.get("name", fname),
                        "description": meta.get("description", ""),
                        "file": fname,
                        "has_endpoint": bool(meta.get("endpoint")),
                    })
                except Exception:
                    md_skills.append({"file": fname, "error": "parse error"})
        return {"dynamic_skills": md_skills, "count": len(md_skills)}


    def _show(self, kw: dict) -> Dict[str, Any]:
        name = (kw.get("name") or "").strip().lower()
        if not name:
            return {"error": "Parameter 'name' is required for show."}
        fpath = os.path.join(self._skills_dir, f"{name}.md")
        if not os.path.isfile(fpath):
            return {"error": f"Skill file not found: {name}.md"}
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        meta, body = _parse_frontmatter(content)
        return {"name": name, "meta": meta, "body": body, "file": fpath}


    def _delete(self, kw: dict) -> Dict[str, Any]:
        name = (kw.get("name") or "").strip().lower()
        if not name:
            return {"error": "Parameter 'name' is required for delete."}
        fpath = os.path.join(self._skills_dir, f"{name}.md")
        if not os.path.isfile(fpath):
            return {"error": f"Skill file not found: {name}.md"}
        os.remove(fpath)
        self._registry.unregister(name)
        logger.info("skill_creator: deleted skill '%s' (%s)", name, fpath)
        return {"status": "deleted", "skill_name": name}
