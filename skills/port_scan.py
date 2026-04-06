from __future__ import annotations

import socket
import time
from typing import Any, Dict, List

from skills.base import BaseSkill

_DEFAULT_PORTS = "21,22,25,53,80,110,143,443,993,995,3306,3389,5432,6379,8080,8443,9200"
_MAX_PORTS = 1024


class PortScanSkill(BaseSkill):
    """Scan TCP ports on a host. Returns which ports are open."""

    name = "port_scan"
    description = "Scan TCP ports on a host. Returns which ports are open."
    parameters = {
        "host": {"type": "string", "description": "Hostname or IP address", "required": True},
        "ports": {
            "type": "string",
            "description": (
                "Comma-separated ports or a range like '1-1024' "
                f"(default: {_DEFAULT_PORTS})"
            ),
            "required": False,
        },
        "timeout": {"type": "number", "description": "Timeout per port in seconds (default 2)", "required": False},
    }

    def execute(self, host: str, ports: str = _DEFAULT_PORTS, timeout: int = 2, **kwargs) -> Dict[str, Any]:
        host = host.strip()
        timeout = max(0.1, min(float(timeout), 10))

        port_list = _parse_ports(ports)
        if isinstance(port_list, str):
            return {"error": port_list}

        if len(port_list) > _MAX_PORTS:
            return {"error": f"Too many ports ({len(port_list)}). Maximum is {_MAX_PORTS}."}

        open_ports: List[int] = []
        closed_count = 0
        t0 = time.perf_counter()

        for port in port_list:
            try:
                sock = socket.create_connection((host, port), timeout=timeout)
                sock.close()
                open_ports.append(port)
            except (socket.timeout, ConnectionRefusedError, OSError):
                closed_count += 1

        elapsed = time.perf_counter() - t0

        return {
            "host": host,
            "open_ports": open_ports,
            "closed_count": closed_count,
            "scanned_count": len(port_list),
            "elapsed_s": round(elapsed, 2),
        }


def _parse_ports(spec: str) -> List[int] | str:
    """Parse a port specification like '80,443' or '1-1024' into a sorted list of ints.

    Returns an error string if the spec is invalid.
    """
    ports: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            pieces = part.split("-", 1)
            try:
                lo, hi = int(pieces[0]), int(pieces[1])
            except ValueError:
                return f"Invalid port range: {part}"
            if lo < 1 or hi > 65535 or lo > hi:
                return f"Invalid port range: {part}"
            ports.update(range(lo, hi + 1))
        else:
            try:
                p = int(part)
            except ValueError:
                return f"Invalid port: {part}"
            if p < 1 or p > 65535:
                return f"Port out of range: {p}"
            ports.add(p)
    if not ports:
        return "No ports specified"
    return sorted(ports)
