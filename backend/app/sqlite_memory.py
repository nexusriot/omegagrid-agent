from __future__ import annotations

import json
import os
import sqlite3
import time
from typing import Any, Dict, List


class MemoryDB:
    """
    SQLite-backed message store for audit/history.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at REAL NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                ts REAL NOT NULL,
                role TEXT NOT NULL,
                content_json TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_session_ts ON messages(session_id, ts)")
        self.conn.commit()

    def create_session(self) -> int:
        cur = self.conn.cursor()
        cur.execute("INSERT INTO sessions(created_at) VALUES (?)", (time.time(),))
        self.conn.commit()
        return int(cur.lastrowid)

    def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("""
            SELECT s.id, s.created_at,
                   (SELECT COUNT(1) FROM messages m WHERE m.session_id = s.id) AS message_count
            FROM sessions s
            ORDER BY s.id DESC
            LIMIT ?
        """, (limit,))
        return [dict(r) for r in cur.fetchall()]

    def add_message(self, session_id: int, role: str, content: Any) -> None:
        """
        Store content as JSON.
        For plain strings -> {"content": "..."}.
        """
        if isinstance(content, str):
            payload = {"content": content}
        else:
            payload = content

        content_json = json.dumps(payload, ensure_ascii=False)
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO messages(session_id, ts, role, content_json) VALUES (?, ?, ?, ?)",
            (session_id, time.time(), role, content_json),
        )
        self.conn.commit()

    def load_tail(self, session_id: int, tail: int) -> List[Dict[str, Any]]:
        """
        Load last N messages in chronological order.
        Return list of {role, content} for Ollama chat.
        """
        cur = self.conn.cursor()
        cur.execute("""
            SELECT role, content_json
            FROM messages
            WHERE session_id = ?
            ORDER BY ts DESC
            LIMIT ?
        """, (session_id, tail))
        rows = cur.fetchall()
        rows.reverse()

        out: List[Dict[str, Any]] = []
        for r in rows:
            role = r["role"]
            payload = json.loads(r["content_json"])
            if isinstance(payload, dict) and "content" in payload and len(payload) == 1:
                content = payload["content"]
            else:
                content = json.dumps(payload, ensure_ascii=False)
            out.append({"role": role, "content": content})
        return out

    def list_messages(self, session_id: int, limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("""
            SELECT id, session_id, ts, role, content_json
            FROM messages
            WHERE session_id = ?
            ORDER BY ts ASC
            LIMIT ? OFFSET ?
        """, (session_id, limit, offset))
        rows = cur.fetchall()

        out: List[Dict[str, Any]] = []
        for r in rows:
            payload = json.loads(r["content_json"])
            # Normalize to a string for UI:
            if isinstance(payload, dict) and "content" in payload and len(payload) == 1:
                content = payload["content"]
            else:
                content = json.dumps(payload, ensure_ascii=False)
            out.append({
                "id": r["id"],
                "session_id": r["session_id"],
                "ts": r["ts"],
                "role": r["role"],
                "content": content,
            })
        return out
