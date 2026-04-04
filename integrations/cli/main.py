import argparse
import json
import requests

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--api", default="http://127.0.0.1:8000")
    p.add_argument("--session", type=int, default=None)
    p.add_argument("query")
    args = p.parse_args()

    payload = {"query": args.query, "session_id": args.session, "remember": True}
    r = requests.post(f"{args.api}/api/query", json=payload, timeout=120)
    r.raise_for_status()
    print(json.dumps(r.json(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
