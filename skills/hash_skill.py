from __future__ import annotations

import hashlib
from typing import Any, Dict

from skills.base import BaseSkill

_SUPPORTED_ALGORITHMS = {"md5", "sha1", "sha256", "sha512"}


class HashSkill(BaseSkill):
    """Generate cryptographic hash of text. Supports MD5, SHA1, SHA256, SHA512."""

    name = "hash"
    description = "Generate cryptographic hash of text. Supports MD5, SHA1, SHA256, SHA512."
    parameters = {
        "text": {
            "type": "string",
            "description": "Text to hash",
            "required": True,
        },
        "algorithm": {
            "type": "string",
            "description": "Hash algorithm: md5, sha1, sha256, sha512 (default sha256)",
            "required": False,
        },
    }

    def execute(self, text: str, algorithm: str = "sha256", **kwargs) -> Dict[str, Any]:
        algorithm = algorithm.strip().lower()
        if algorithm not in _SUPPORTED_ALGORITHMS:
            return {
                "error": f"Unsupported algorithm: {algorithm}. Supported: {sorted(_SUPPORTED_ALGORITHMS)}"
            }

        h = hashlib.new(algorithm)
        h.update(text.encode("utf-8"))

        return {
            "algorithm": algorithm,
            "input_length": len(text),
            "hash": h.hexdigest(),
        }
