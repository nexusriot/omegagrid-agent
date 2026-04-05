from __future__ import annotations

import socket
import time
from typing import Any, Dict

from skills.base import BaseSkill


class PingCheckSkill(BaseSkill):
    """Check if a host is reachable via TCP connect (not ICMP ping, works without root)."""

    name = "ping_check"
    description = "Check if a host:port is reachable (TCP connect). Default port 80. Returns latency."
    parameters = {
        "host": {"type": "string", "description": "Hostname or IP address", "required": True},
        "port": {"type": "number", "description": "TCP port to connect to (default 80)", "required": False},
        "timeout": {"type": "number", "description": "Timeout in seconds (default 5)", "required": False},
    }

    def execute(self, host: str, port: int = 80, timeout: int = 5, **kwargs) -> Dict[str, Any]:
        host = host.strip()
        port = int(port)
        timeout = min(int(timeout), 30)

        # Resolve DNS first
        try:
            t0 = time.perf_counter()
            addrs = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
            dns_ms = (time.perf_counter() - t0) * 1000
        except socket.gaierror as e:
            return {"host": host, "port": port, "reachable": False, "error": f"DNS resolution failed: {e}"}

        if not addrs:
            return {"host": host, "port": port, "reachable": False, "error": "No addresses found"}

        resolved_ip = addrs[0][4][0]

        # TCP connect
        try:
            t0 = time.perf_counter()
            sock = socket.create_connection((host, port), timeout=timeout)
            connect_ms = (time.perf_counter() - t0) * 1000
            sock.close()
            return {
                "host": host,
                "resolved_ip": resolved_ip,
                "port": port,
                "reachable": True,
                "dns_ms": round(dns_ms, 2),
                "connect_ms": round(connect_ms, 2),
                "total_ms": round(dns_ms + connect_ms, 2),
            }
        except socket.timeout:
            return {"host": host, "resolved_ip": resolved_ip, "port": port, "reachable": False, "error": f"Connection timed out ({timeout}s)"}
        except ConnectionRefusedError:
            return {"host": host, "resolved_ip": resolved_ip, "port": port, "reachable": False, "error": "Connection refused"}
        except OSError as e:
            return {"host": host, "resolved_ip": resolved_ip, "port": port, "reachable": False, "error": str(e)}
