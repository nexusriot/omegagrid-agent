from __future__ import annotations

import re
from typing import Any, Dict

import requests

from skills.base import BaseSkill


class WebScrapeSkill(BaseSkill):
    """Fetch a URL and return clean text content (HTML tags stripped)."""

    name = "web_scrape"
    description = "Fetch a web page and return its text content (HTML stripped). Useful for reading articles, docs, APIs."
    parameters = {
        "url": {"type": "string", "description": "Full URL to fetch", "required": True},
        "max_chars": {"type": "number", "description": "Max characters to return (default 4000)", "required": False},
    }

    def __init__(self, timeout: float = 15.0, default_max_chars: int = 4000):
        self.timeout = timeout
        self.default_max_chars = default_max_chars

    def execute(self, url: str, max_chars: int | None = None, **kwargs) -> Dict[str, Any]:
        limit = max_chars or self.default_max_chars

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; OmegaGridAgent/1.0)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
            }
            r = requests.get(url, headers=headers, timeout=self.timeout, allow_redirects=True)
            r.raise_for_status()
        except requests.exceptions.Timeout:
            return {"error": f"Request timed out after {self.timeout}s"}
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}

        content_type = r.headers.get("Content-Type", "")

        # If plain text or JSON, return as-is
        if "text/plain" in content_type or "application/json" in content_type:
            return {
                "url": url,
                "content_type": content_type,
                "text": r.text[:limit],
                "truncated": len(r.text) > limit,
            }

        # Strip HTML
        text = _strip_html(r.text)
        return {
            "url": url,
            "content_type": content_type,
            "text": text[:limit],
            "truncated": len(text) > limit,
        }


def _strip_html(html: str) -> str:
    """Remove HTML tags, scripts, styles and collapse whitespace."""
    # Remove script and style blocks
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.S | re.I)
    # Remove all tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Decode common entities
    for entity, char in [("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"),
                         ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")]:
        text = text.replace(entity, char)
    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
