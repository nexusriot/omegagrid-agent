from __future__ import annotations

import socket
import subprocess
from typing import Any, Dict, List

from skills.base import BaseSkill

_ALLOWED_TYPES = {"A", "AAAA", "MX", "TXT", "CNAME", "NS", "SOA", "PTR", "SRV"}


class DnsLookupSkill(BaseSkill):
    """Resolve DNS records for a domain. Falls back to socket if dig is unavailable."""

    name = "dns_lookup"
    description = "Look up DNS records (A, AAAA, MX, TXT, CNAME, NS) for a domain."
    parameters = {
        "domain": {"type": "string", "description": "Domain name to look up", "required": True},
        "record_type": {"type": "string", "description": "Record type: A, AAAA, MX, TXT, CNAME, NS (default A)", "required": False},
    }

    def execute(self, domain: str, record_type: str = "A", **kwargs) -> Dict[str, Any]:
        rtype = record_type.upper().strip()
        if rtype not in _ALLOWED_TYPES:
            return {"error": f"Unsupported record type: {rtype}. Allowed: {sorted(_ALLOWED_TYPES)}"}

        domain = domain.strip().rstrip(".")

        # Try dig first (richer output)
        result = _try_dig(domain, rtype)
        if result is not None:
            return result

        # Fallback to socket (only supports A/AAAA)
        if rtype in ("A", "AAAA"):
            return _socket_resolve(domain, rtype)

        return {"error": f"dig not available and socket only supports A/AAAA lookups"}


def _try_dig(domain: str, rtype: str) -> Dict[str, Any] | None:
    """Use dig command for DNS lookup. Returns None if dig is not available."""
    try:
        result = subprocess.run(
            ["dig", "+short", "+time=5", "+tries=2", domain, rtype],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return None

        lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
        return {
            "domain": domain,
            "type": rtype,
            "records": lines,
            "count": len(lines),
            "method": "dig",
        }
    except FileNotFoundError:
        return None
    except Exception:
        return None


def _socket_resolve(domain: str, rtype: str) -> Dict[str, Any]:
    """Fallback DNS resolution using socket.getaddrinfo."""
    family = socket.AF_INET if rtype == "A" else socket.AF_INET6
    try:
        results = socket.getaddrinfo(domain, None, family, socket.SOCK_STREAM)
        addresses = sorted(set(r[4][0] for r in results))
        return {
            "domain": domain,
            "type": rtype,
            "records": addresses,
            "count": len(addresses),
            "method": "socket",
        }
    except socket.gaierror as e:
        return {"error": f"DNS resolution failed: {e}", "domain": domain, "type": rtype}
