from __future__ import annotations

import time
from typing import Any, Dict, Optional

import requests

from skills.base import BaseSkill


class HttpHealthSkill(BaseSkill):
    """HTTP health check. Checks status code, response time, and optionally matches a string in the body."""

    name = "http_health"
    description = (
        "HTTP health check. Checks status code, response time, "
        "and optionally matches a string in the body."
    )
    parameters = {
        "url": {"type": "string", "description": "URL to check", "required": True},
        "method": {
            "type": "string",
            "description": "HTTP method: GET or HEAD (default GET)",
            "required": False,
        },
        "expected_status": {
            "type": "number",
            "description": "Expected HTTP status code (default 200)",
            "required": False,
        },
        "body_contains": {
            "type": "string",
            "description": "String to search for in the response body",
            "required": False,
        },
        "timeout": {
            "type": "number",
            "description": "Request timeout in seconds (default 10)",
            "required": False,
        },
    }

    def execute(
        self,
        url: str,
        method: str = "GET",
        expected_status: int = 200,
        body_contains: Optional[str] = None,
        timeout: int = 10,
        **kwargs,
    ) -> Dict[str, Any]:
        url = url.strip()
        method = method.upper().strip()
        if method not in ("GET", "HEAD"):
            return {"error": f"Unsupported method: {method}. Use GET or HEAD."}

        expected_status = int(expected_status)
        timeout = max(1, min(int(timeout), 60))

        try:
            t0 = time.perf_counter()
            resp = requests.request(method, url, timeout=timeout, allow_redirects=True)
            elapsed_ms = (time.perf_counter() - t0) * 1000

            status_ok = resp.status_code == expected_status

            body_match: Optional[bool] = None
            if body_contains is not None and method == "GET":
                body_match = body_contains in resp.text

            ok = status_ok and (body_match is None or body_match)

            return {
                "url": url,
                "status_code": resp.status_code,
                "ok": ok,
                "response_time_ms": round(elapsed_ms, 2),
                "body_match": body_match,
                "content_length": len(resp.content),
                "error": None,
            }
        except requests.RequestException as e:
            return {
                "url": url,
                "status_code": None,
                "ok": False,
                "response_time_ms": None,
                "body_match": None,
                "content_length": None,
                "error": str(e),
            }
