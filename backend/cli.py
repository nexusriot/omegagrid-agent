#!/usr/bin/env python3
"""
Minimal CLI client for the REST API.

Usage:
  python cli.py --api http://localhost:8000 --new
  python cli.py --api http://localhost:8000 --session 1 "hello"
"""
from __future__ import annotations

import argparse
import json
import requests


def post(api: str, path: str, payload: dict):
    r = requests.post(api.rstrip("/") + path, json=payload, timeout=120)
    if not r.ok:
        raise SystemExit(f"HTTP {r.status_code}: {r.text}")
    return r.json()


def get(api: str, path: str):
    r = requests.get(api.rstrip("/") + path, timeout=60)
    if not r.ok:
        raise SystemExit(f"HTTP {r.status_code}: {r.text}")
    return r.json()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--api", default="http://localhost:8000")
    p.add_argument("--new", action="store_true", help="create a new session")
    p.add_argument("--session", type=int, default=None, help="use existing session id")
    p.add_argument("--remember", action="store_true", help="allow agent to store memories")
    p.add_argument("query", nargs="*", help="query text")
    args = p.parse_args()

    if args.new:
        s = post(args.api, "/api/sessions/new", {})
        print(json.dumps(s, indent=2))
        return

    if not args.query:
        # list sessions
        s = get(args.api, "/api/sessions")
        print(json.dumps(s, indent=2))
        return

    q = " ".join(args.query)
    payload = {"query": q, "session_id": args.session, "remember": bool(args.remember)}
    res = post(args.api, "/api/query", payload)
    print(res.get("answer", ""))
    print("\n--- meta ---")
    print(json.dumps(res.get("meta", {}), indent=2))


if __name__ == "__main__":
    main()
