from __future__ import annotations

import ipaddress
from typing import Any, Dict

from skills.base import BaseSkill


class CidrCalcSkill(BaseSkill):
    """Calculate network info from a CIDR block (subnet mask, range, hosts, etc.)."""

    name = "cidr_calc"
    description = (
        "Calculate network info from a CIDR block (IPv4 or IPv6): network address, "
        "broadcast, netmask, hostmask, prefix length, total addresses, usable host range, "
        "and whether it's private/global/multicast/loopback. Optionally checks if a "
        "given IP is contained in the network."
    )
    parameters = {
        "cidr": {
            "type": "string",
            "description": "CIDR block, e.g. '192.168.1.0/24' or '2001:db8::/32'. A bare IP gets /32 (v4) or /128 (v6).",
            "required": True,
        },
        "check_ip": {
            "type": "string",
            "description": "Optional IP address to check for membership in the network",
            "required": False,
        },
    }

    def execute(self, cidr: str = "", check_ip: str = "", **kwargs) -> Dict[str, Any]:
        cidr = (cidr or "").strip()
        if not cidr:
            return {"error": "cidr is required"}

        try:
            net = ipaddress.ip_network(cidr, strict=False)
        except ValueError as e:
            return {"error": f"invalid CIDR: {e}"}

        is_v4 = isinstance(net, ipaddress.IPv4Network)
        total = net.num_addresses

        # Usable host range
        if is_v4:
            if net.prefixlen == 32:
                first_host = str(net.network_address)
                last_host = str(net.network_address)
                usable_hosts = 1
            elif net.prefixlen == 31:
                # RFC 3021 point-to-point: both addresses usable
                first_host = str(net.network_address)
                last_host = str(net.broadcast_address)
                usable_hosts = 2
            else:
                first_host = str(net.network_address + 1)
                last_host = str(net.broadcast_address - 1)
                usable_hosts = total - 2
        else:
            # IPv6 has no broadcast; all addresses are usable
            first_host = str(net.network_address)
            last_host = str(net.network_address + total - 1)
            usable_hosts = total

        result: Dict[str, Any] = {
            "cidr": str(net),
            "version": net.version,
            "network_address": str(net.network_address),
            "netmask": str(net.netmask),
            "hostmask": str(net.hostmask),
            "prefix_length": net.prefixlen,
            "total_addresses": total,
            "usable_hosts": usable_hosts,
            "first_host": first_host,
            "last_host": last_host,
            "is_private": net.is_private,
            "is_global": net.is_global,
            "is_multicast": net.is_multicast,
            "is_loopback": net.is_loopback,
            "is_link_local": net.is_link_local,
            "is_reserved": net.is_reserved,
        }

        if is_v4:
            result["broadcast_address"] = str(net.broadcast_address)

        if check_ip:
            try:
                ip = ipaddress.ip_address(check_ip.strip())
                result["check_ip"] = str(ip)
                result["check_ip_in_network"] = ip in net
            except ValueError as e:
                result["check_ip_error"] = f"invalid IP: {e}"

        return result
