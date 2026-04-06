from __future__ import annotations

import re
import subprocess
from typing import Any, Dict, List, Optional

from skills.base import BaseSkill


class WhoisLookupSkill(BaseSkill):
    """WHOIS lookup for a domain. Returns registrar, creation/expiry dates, nameservers."""

    name = "whois"
    description = "WHOIS lookup for a domain. Returns registrar, creation/expiry dates, nameservers."
    parameters = {
        "domain": {"type": "string", "description": "Domain name to look up", "required": True},
    }

    def execute(self, domain: str, **kwargs) -> Dict[str, Any]:
        domain = domain.strip().lower().rstrip(".")

        try:
            result = subprocess.run(
                ["whois", domain],
                capture_output=True, text=True, timeout=30,
            )
        except FileNotFoundError:
            return {
                "error": (
                    "whois binary not found. Install it with: "
                    "apt install whois (Debian/Ubuntu) or yum install whois (RHEL/CentOS)."
                ),
                "domain": domain,
            }
        except subprocess.TimeoutExpired:
            return {"error": "whois command timed out after 30s", "domain": domain}

        raw = result.stdout or ""
        if result.returncode != 0 and not raw:
            return {"error": f"whois failed: {result.stderr.strip()}", "domain": domain}

        registrar = _first_match(raw, r"(?i)registrar\s*:\s*(.+)")
        creation_date = _first_match(raw, r"(?i)creat(?:ion|ed)\s*date\s*:\s*(.+)")
        expiry_date = _first_match(
            raw, r"(?i)(?:expir(?:y|ation)\s*date|paid-till)\s*:\s*(.+)"
        )
        updated_date = _first_match(raw, r"(?i)updated?\s*date\s*:\s*(.+)")
        nameservers = _all_matches(raw, r"(?i)name\s*server\s*:\s*(.+)")
        status = _all_matches(raw, r"(?i)(?:domain\s+)?status\s*:\s*(.+)")

        return {
            "domain": domain,
            "registrar": registrar,
            "creation_date": creation_date,
            "expiry_date": expiry_date,
            "updated_date": updated_date,
            "nameservers": sorted(set(ns.lower() for ns in nameservers)),
            "status": status,
            "raw": raw[:2000],
        }


def _first_match(text: str, pattern: str) -> Optional[str]:
    m = re.search(pattern, text)
    return m.group(1).strip() if m else None


def _all_matches(text: str, pattern: str) -> List[str]:
    return [m.strip() for m in re.findall(pattern, text)]
