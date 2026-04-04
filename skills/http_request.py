from __future__ import annotations

from typing import Any, Dict

import requests

from skills.base import BaseSkill


class HttpRequestSkill(BaseSkill):
    """Call an external HTTP API endpoint. Supports GET and POST methods."""

    name = "http_request"
    description = "Make an HTTP request to an external URL. Returns status code and response body."
    parameters = {
        "url": {"type": "string", "description": "Full URL to call", "required": True},
        "method": {"type": "string", "description": "HTTP method: GET or POST (default GET)", "required": False},
        "body": {"type": "object", "description": "JSON body for POST requests", "required": False},
        "headers": {"type": "object", "description": "Extra HTTP headers", "required": False},
    }

    def __init__(self, timeout: float = 30.0, max_response_chars: int = 4000):
        self.timeout = timeout
        self.max_response_chars = max_response_chars

    def execute(self, url: str, method: str = "GET", body: dict | None = None,
                headers: dict | None = None, **kwargs) -> Dict[str, Any]:
        method = method.upper()
        if method not in ("GET", "POST"):
            return {"error": f"Unsupported method: {method}. Use GET or POST."}

        req_headers = dict(headers or {})

        try:
            if method == "GET":
                r = requests.get(url, headers=req_headers, timeout=self.timeout)
            else:
                req_headers.setdefault("Content-Type", "application/json")
                r = requests.post(url, json=body, headers=req_headers, timeout=self.timeout)

            # Try to parse as JSON, fall back to text
            try:
                resp_body = r.json()
            except Exception:
                resp_body = r.text[:self.max_response_chars]

            return {
                "status_code": r.status_code,
                "body": resp_body,
            }
        except requests.exceptions.Timeout:
            return {"error": f"Request timed out after {self.timeout}s"}
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}
