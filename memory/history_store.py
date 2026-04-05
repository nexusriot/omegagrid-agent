from __future__ import annotations

import json
import os
import sqlite3
import time
from typing import Any, Dict, List


class HistoryStore:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self.conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at REAL NOT NULL)")
        cur.execute(
            "CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER NOT NULL, ts REAL NOT NULL, role TEXT NOT NULL, content_json TEXT NOT NULL)"
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_session_ts ON messages(session_id, ts)")
        self.conn.commit()

    def create_session(self) -> int:
        cur = self.conn.cursor()
        cur.execute("INSERT INTO sessions(created_at) VALUES (?)", (time.time(),))
        self.conn.commit()
        return int(cur.lastrowid)

    def add_message(self, session_id: int, role: str, content: Any) -> None:
        payload = content if isinstance(content, dict) else {"content": content}
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO messages(session_id, ts, role, content_json) VALUES (?, ?, ?, ?)",
            (session_id, time.time(), role, json.dumps(payload, ensure_ascii=False)),
        )
        self.conn.commit()

    def load_tail(self, session_id: int, limit: int = 30) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT role, content_json FROM messages WHERE session_id = ? ORDER BY ts DESC LIMIT ?",
            (session_id, limit),
        )
        rows = list(cur.fetchall())[::-1]
        out: List[Dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row["content_json"])
            # Skip old raw_model_json debug entries — they pollute LLM context
            if isinstance(payload, dict) and "raw_model_json" in payload:
                continue
            if isinstance(payload, dict) and "content" in payload and len(payload) == 1:
                content = payload["content"]
            else:
                content = json.dumps(payload, ensure_ascii=False)
            out.append({"role": row["role"], "content": content})
        return out

    def list_sessions(self, limit: int = 100) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            '''
            SELECT s.id, s.created_at,
                   (SELECT COUNT(1) FROM messages m WHERE m.session_id = s.id) AS message_count
            FROM sessions s
            ORDER BY s.id DESC
            LIMIT ?
            ''',
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]

    def list_messages(self, session_id: int, limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT id, session_id, ts, role, content_json FROM messages WHERE session_id = ? ORDER BY ts ASC LIMIT ? OFFSET ?",
            (session_id, limit, offset),
        )
        out: List[Dict[str, Any]] = []
        for row in cur.fetchall():
            payload = json.loads(row["content_json"])
            if isinstance(payload, dict) and "content" in payload and len(payload) == 1:
                content = payload["content"]
            else:
                content = json.dumps(payload, ensure_ascii=False)
            out.append({
                "id": row["id"],
                "session_id": row["session_id"],
                "ts": row["ts"],
                "role": row["role"],
                "content": content,
            })
        return out
