from __future__ import annotations

import ipaddress
from typing import Any, Dict

import requests

from skills.base import BaseSkill


class IpInfoSkill(BaseSkill):
    """Look up geolocation, ASN, ISP, and reverse-DNS for an IP via ip-api.com (no key)."""

    name = "ip_info"
    description = (
        "Look up geolocation, ASN, ISP, and reverse-DNS info for an IPv4/IPv6 address "
        "via ip-api.com (free, no API key). If 'ip' is omitted, returns info for the "
        "caller's public IP."
    )
    parameters = {
        "ip": {
            "type": "string",
            "description": "IPv4 or IPv6 address to look up. If omitted, uses caller's public IP.",
            "required": False,
        },
    }

    def __init__(self, timeout: float = 10.0):
        self._timeout = timeout

    def execute(self, ip: str = "", **kwargs) -> Dict[str, Any]:
        ip = (ip or "").strip()
        if ip:
            try:
                ipaddress.ip_address(ip)
            except ValueError:
                return {"error": f"Invalid IP address: {ip}"}

        url = f"http://ip-api.com/json/{ip}" if ip else "http://ip-api.com/json/"
        params = {
            "fields": "status,message,query,country,countryCode,region,regionName,"
                      "city,zip,lat,lon,timezone,isp,org,as,reverse,mobile,proxy,hosting"
        }
        try:
            r = requests.get(
                url,
                params=params,
                headers={"User-Agent": "OmegaGridAgent/1.0"},
                timeout=self._timeout,
            )
            r.raise_for_status()
            data = r.json()
        except requests.exceptions.Timeout:
            return {"error": f"Request timed out after {self._timeout}s"}
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}
        except ValueError:
            return {"error": "invalid JSON response from ip-api.com"}

        if data.get("status") != "success":
            return {
                "error": data.get("message", "lookup failed"),
                "ip": data.get("query", ip),
            }

        return {
            "ip": data.get("query"),
            "country": data.get("country"),
            "country_code": data.get("countryCode"),
            "region": data.get("regionName"),
            "region_code": data.get("region"),
            "city": data.get("city"),
            "zip": data.get("zip"),
            "lat": data.get("lat"),
            "lon": data.get("lon"),
            "timezone": data.get("timezone"),
            "isp": data.get("isp"),
            "org": data.get("org"),
            "asn": data.get("as"),
            "reverse_dns": data.get("reverse"),
            "mobile": data.get("mobile"),
            "proxy": data.get("proxy"),
            "hosting": data.get("hosting"),
        }
