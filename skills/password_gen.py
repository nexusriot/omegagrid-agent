from __future__ import annotations

import secrets
import string
from typing import Any, Dict

from skills.base import BaseSkill


_AMBIGUOUS = set("Il1O0o")


class PasswordGenSkill(BaseSkill):
    """Generate cryptographically-secure random passwords using the secrets module."""

    name = "password_gen"
    description = (
        "Generate one or more cryptographically secure random passwords. Configurable "
        "length, character classes (letters, digits, symbols), and ambiguous-character "
        "exclusion. Guarantees at least one character from each requested class."
    )
    parameters = {
        "length": {
            "type": "integer",
            "description": "Password length (8-128, default 16)",
            "required": False,
        },
        "count": {
            "type": "integer",
            "description": "How many passwords to generate (1-50, default 1)",
            "required": False,
        },
        "use_uppercase": {
            "type": "boolean",
            "description": "Include uppercase letters (default true)",
            "required": False,
        },
        "use_lowercase": {
            "type": "boolean",
            "description": "Include lowercase letters (default true)",
            "required": False,
        },
        "use_digits": {
            "type": "boolean",
            "description": "Include digits 0-9 (default true)",
            "required": False,
        },
        "use_symbols": {
            "type": "boolean",
            "description": "Include punctuation symbols (default true)",
            "required": False,
        },
        "exclude_ambiguous": {
            "type": "boolean",
            "description": "Exclude visually ambiguous characters (Il1O0o) (default false)",
            "required": False,
        },
    }

    def execute(
        self,
        length: int = 16,
        count: int = 1,
        use_uppercase: bool = True,
        use_lowercase: bool = True,
        use_digits: bool = True,
        use_symbols: bool = True,
        exclude_ambiguous: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        try:
            length = int(length)
            count = int(count)
        except (TypeError, ValueError):
            return {"error": "length and count must be integers"}

        if length < 8 or length > 128:
            return {"error": "length must be between 8 and 128"}
        if count < 1 or count > 50:
            return {"error": "count must be between 1 and 50"}

        classes = []
        if use_lowercase:
            classes.append(string.ascii_lowercase)
        if use_uppercase:
            classes.append(string.ascii_uppercase)
        if use_digits:
            classes.append(string.digits)
        if use_symbols:
            classes.append("!@#$%^&*()-_=+[]{};:,.<>/?")

        if not classes:
            return {"error": "at least one character class must be enabled"}

        if exclude_ambiguous:
            classes = ["".join(ch for ch in cls if ch not in _AMBIGUOUS) for cls in classes]
            classes = [c for c in classes if c]
            if not classes:
                return {"error": "no characters left after excluding ambiguous ones"}

        if length < len(classes):
            return {"error": f"length must be at least {len(classes)} to include one of each class"}

        all_chars = "".join(classes)

        passwords = []
        for _ in range(count):
            # Guarantee at least one char from each class
            chars = [secrets.choice(cls) for cls in classes]
            chars += [secrets.choice(all_chars) for _ in range(length - len(classes))]
            # Cryptographic shuffle
            for i in range(len(chars) - 1, 0, -1):
                j = secrets.randbelow(i + 1)
                chars[i], chars[j] = chars[j], chars[i]
            passwords.append("".join(chars))

        return {
            "length": length,
            "count": count,
            "passwords": passwords,
            "classes": {
                "uppercase": use_uppercase,
                "lowercase": use_lowercase,
                "digits": use_digits,
                "symbols": use_symbols,
            },
            "exclude_ambiguous": exclude_ambiguous,
        }
