from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List

import requests
import yaml

from skills.base import BaseSkill


class MarkdownSkill(BaseSkill):
    """A skill defined by a Markdown file with YAML frontmatter.

    Frontmatter fields:
        name:        Unique skill name (required)
        description: Short description for the LLM (required)
        parameters:  Parameter schema dict (required)
        endpoint:    HTTP endpoint to call (optional -- enables auto-execution)
        method:      HTTP method GET or POST (default GET, only with endpoint)

    Body text (below frontmatter) is used as extra prompt context for the LLM.
    """

    def __init__(self, meta: Dict[str, Any], body: str = ""):
        self.name = meta["name"]
        self.description = meta.get("description", "")
        self.parameters = meta.get("parameters", {})
        self.endpoint = meta.get("endpoint", "")
        self.method = (meta.get("method", "GET") or "GET").upper()
        self.body = body.strip()
        self._timeout = float(meta.get("timeout", 30))

    def execute(self, **kwargs) -> Dict[str, Any]:
        if not self.endpoint:
            return {
                "info": "This is a prompt-only skill (no endpoint configured).",
                "instructions": self.body or "(none)",
                "parameters_received": kwargs,
            }

        try:
            headers = {"User-Agent": "OmegaGridAgent/1.0"}
            if self.method == "POST":
                headers["Content-Type"] = "application/json"
                r = requests.post(self.endpoint, json=kwargs, headers=headers, timeout=self._timeout)
            else:
                r = requests.get(self.endpoint, params=kwargs, headers=headers, timeout=self._timeout)

            r.raise_for_status()
            try:
                body = r.json()
            except Exception:
                body = r.text[:4000]
            return {"status_code": r.status_code, "body": body}
        except requests.exceptions.Timeout:
            return {"error": f"Request timed out after {self._timeout}s"}
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}


def _parse_frontmatter(text: str):
    """Parse YAML frontmatter from a Markdown string.

    Returns (meta_dict, body_text).
    """
    text = text.strip()
    if not text.startswith("---"):
        return {}, text

    # Find closing ---
    end = text.find("---", 3)
    if end == -1:
        return {}, text

    front = text[3:end].strip()
    body = text[end + 3:].strip()

    meta = yaml.safe_load(front) or {}
    return meta, body


def load_markdown_skills(directory: str) -> List[MarkdownSkill]:
    """Load all *.md files from directory as MarkdownSkill instances.

    Skips files that don't have valid frontmatter with a 'name' field.
    """
    skills: List[MarkdownSkill] = []
    if not os.path.isdir(directory):
        return skills

    for fname in sorted(os.listdir(directory)):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(directory, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            continue

        meta, body = _parse_frontmatter(content)
        if not meta.get("name"):
            continue
        if not meta.get("description"):
            meta["description"] = f"Skill from {fname}"

        skills.append(MarkdownSkill(meta=meta, body=body))

    return skills
