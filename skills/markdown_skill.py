from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List

import requests
import yaml

from skills.base import BaseSkill

logger = logging.getLogger(__name__)


class MarkdownSkill(BaseSkill):
    """A skill defined by a Markdown file with YAML frontmatter.

    Supports three modes:

    1. **Single-endpoint** — `endpoint` field present.  One HTTP call.
    2. **Pipeline** — `steps` list present.  Multiple HTTP calls executed in
       sequence; results from earlier steps are available to later steps via
       ``{{step_name.field.path}}`` placeholders.
    3. **Prompt-only** — neither endpoint nor steps.  Returns body instructions
       for the LLM to interpret.

    Frontmatter fields:
        name:        Unique skill name (required)
        description: Short description for the LLM (required)
        parameters:  Parameter schema dict (optional)
        endpoint:    HTTP endpoint to call (mode 1)
        method:      HTTP method GET or POST (default GET, mode 1)
        steps:       List of step dicts (mode 2)
        timeout:     Per-request timeout in seconds (default 30)

    Step dict fields (pipeline mode):
        name:      Step identifier (used in placeholders, required)
        endpoint:  HTTP URL — may contain {{param}} or {{step_name.path}} (required)
        method:    GET or POST (default GET)
        headers:   Extra headers dict (optional)
        body:      POST body dict — may contain placeholders (optional)
        params:    Query-string dict — may contain placeholders (optional)

    Placeholders:
        {{param_name}}            — replaced with skill input parameter
        {{step_name.path.to.key}} — replaced with a value from a previous step's
                                     JSON response (dot-separated path)
    """

    def __init__(self, meta: Dict[str, Any], body: str = "", skill_executor=None):
        self.name = meta["name"]
        self.description = meta.get("description", "")
        self.parameters = meta.get("parameters") or {}
        self.endpoint = meta.get("endpoint", "")
        self.method = (meta.get("method", "GET") or "GET").upper()
        self.body = body.strip()
        self._timeout = float(meta.get("timeout", 30))
        self._steps: List[Dict[str, Any]] = meta.get("steps") or []
        # Optional callable: (skill_name: str, args: dict) -> dict
        # Lets pipeline steps invoke other registered skills.
        self._skill_executor = skill_executor


    def execute(self, **kwargs) -> Dict[str, Any]:
        if self._steps:
            return self._execute_pipeline(kwargs)
        if self.endpoint:
            return self._execute_single(kwargs)
        return {
            "info": "This is a prompt-only skill (no endpoint configured).",
            "instructions": self.body or "(none)",
            "parameters_received": kwargs,
        }


    def _execute_single(self, kwargs: dict) -> Dict[str, Any]:
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


    def _execute_pipeline(self, kwargs: dict) -> Dict[str, Any]:
        """Run steps sequentially, collecting results into a context dict.

        Each step is one of two kinds:
          - **HTTP step** — has an `endpoint:` field
          - **Skill step** — has a `skill:` field naming another registered skill
        """
        ctx: Dict[str, Any] = {}          # step_name -> parsed result
        results: List[Dict[str, Any]] = []

        for i, step in enumerate(self._steps):
            step_name = step.get("name") or f"step_{i+1}"
            skill_call = step.get("skill", "")
            raw_endpoint = step.get("endpoint", "")

            # ----- Skill step -----
            if skill_call:
                if self._skill_executor is None:
                    parsed = {"error": "no skill executor available; pipeline cannot call other skills"}
                else:
                    raw_args = step.get("args") or {}
                    resolved_args = _resolve_obj(raw_args, kwargs, ctx) if raw_args else {}
                    try:
                        parsed = self._skill_executor(skill_call, resolved_args)
                    except Exception as e:
                        parsed = {"error": str(e), "skill": skill_call}
                ctx[step_name] = parsed
                results.append({"step": step_name, "kind": "skill", "skill": skill_call, "body": parsed})
                logger.debug("pipeline %s skill step %s -> %s", self.name, step_name, str(parsed)[:200])
                continue

            # ----- HTTP step -----
            if not raw_endpoint:
                results.append({"step": step_name, "error": "step has neither 'endpoint' nor 'skill'"})
                continue

            method = (step.get("method", "GET") or "GET").upper()
            extra_headers = step.get("headers") or {}
            raw_params = step.get("params") or {}
            raw_body = step.get("body") or {}

            # Resolve placeholders
            endpoint = _resolve_str(raw_endpoint, kwargs, ctx)
            params = _resolve_obj(raw_params, kwargs, ctx) if raw_params else {}
            body_data = _resolve_obj(raw_body, kwargs, ctx) if raw_body else {}

            headers = {"User-Agent": "OmegaGridAgent/1.0"}
            headers.update(extra_headers)

            r = None
            try:
                if method == "POST":
                    headers["Content-Type"] = "application/json"
                    r = requests.post(endpoint, json=body_data, headers=headers,
                                      params=params or None, timeout=self._timeout)
                else:
                    merged_params = {**kwargs, **params}
                    r = requests.get(endpoint, params=merged_params or None,
                                     headers=headers, timeout=self._timeout)
                r.raise_for_status()
                try:
                    parsed = r.json()
                except Exception:
                    parsed = r.text[:4000]
            except requests.exceptions.Timeout:
                parsed = {"error": f"timeout after {self._timeout}s"}
            except requests.exceptions.RequestException as e:
                parsed = {"error": str(e)}

            ctx[step_name] = parsed
            status_code = r.status_code if r is not None else None
            # Truncate large responses in the result summary
            preview = json.dumps(parsed, ensure_ascii=False, default=str)
            if len(preview) > 2000:
                preview = preview[:2000] + "...(truncated)"
            results.append({"step": step_name, "kind": "http", "status": status_code, "body": parsed})
            logger.debug("pipeline %s http step %s: %s", self.name, step_name, preview[:200])

        return {
            "pipeline": self.name,
            "steps_completed": len(results),
            "results": results,
            "instructions": self.body or "(interpret the step results above)",
        }


_PLACEHOLDER_RE = re.compile(r"\{\{(.+?)\}\}")


def _resolve_value(key: str, params: dict, ctx: dict) -> str:
    """Resolve a single placeholder key like 'param_name' or 'step.path.to.val'."""
    # First check direct params
    if key in params:
        return str(params[key])

    # Then check step context (dot-separated path)
    parts = key.split(".")
    step_name = parts[0]
    if step_name in ctx:
        obj = ctx[step_name]
        for part in parts[1:]:
            if isinstance(obj, dict):
                obj = obj.get(part, "")
            elif isinstance(obj, list) and part.isdigit():
                idx = int(part)
                obj = obj[idx] if idx < len(obj) else ""
            else:
                obj = ""
                break
        return str(obj)

    return f"{{{{{key}}}}}"  # leave unresolved


def _resolve_str(text: str, params: dict, ctx: dict) -> str:
    """Replace all {{...}} placeholders in a string."""
    return _PLACEHOLDER_RE.sub(lambda m: _resolve_value(m.group(1), params, ctx), text)


def _resolve_obj(obj: Any, params: dict, ctx: dict) -> Any:
    """Recursively resolve placeholders in a dict/list/string."""
    if isinstance(obj, str):
        return _resolve_str(obj, params, ctx)
    if isinstance(obj, dict):
        return {k: _resolve_obj(v, params, ctx) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_obj(item, params, ctx) for item in obj]
    return obj


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


def load_markdown_skills(directory: str, skill_executor=None) -> List[MarkdownSkill]:
    """Load all *.md files from directory as MarkdownSkill instances.

    Skips files that don't have valid frontmatter with a 'name' field.

    Args:
        directory:       Directory containing .md skill files
        skill_executor:  Optional callable (skill_name, args) -> dict for
                         pipeline steps that invoke other registered skills.
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

        skills.append(MarkdownSkill(meta=meta, body=body, skill_executor=skill_executor))

    return skills
