from __future__ import annotations

import base64
from typing import Any, Dict

from skills.base import BaseSkill


class Base64Skill(BaseSkill):
    """Encode or decode base64 strings."""

    name = "base64"
    description = "Encode or decode base64 strings."
    parameters = {
        "action": {
            "type": "string",
            "description": "Action to perform: 'encode' or 'decode'",
            "required": True,
        },
        "text": {
            "type": "string",
            "description": "Text to encode, or base64 string to decode",
            "required": True,
        },
    }

    def execute(self, action: str, text: str, **kwargs) -> Dict[str, Any]:
        action = action.strip().lower()
        if action not in ("encode", "decode"):
            return {"error": f"Invalid action: {action}. Must be 'encode' or 'decode'."}

        if action == "encode":
            encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
            return {
                "action": "encode",
                "input": text[:100],
                "output": encoded,
            }
        else:
            try:
                decoded = base64.b64decode(text, validate=True).decode("utf-8")
            except Exception as e:
                return {
                    "action": "decode",
                    "input": text[:100],
                    "output": None,
                    "error": f"Decode failed: {e}",
                }
            return {
                "action": "decode",
                "input": text[:100],
                "output": decoded,
            }
