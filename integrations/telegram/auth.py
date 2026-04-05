from __future__ import annotations

import logging
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class DBUser:
    telegram_id: int
    created_at: str
    last_activity: str


class UserStore:
    def __init__(self, enabled: bool, admin_id: int = 0, db: sqlite3.Connection | None = None):
        self.enabled = enabled
        self.admin_id = admin_id
        self.db = db

    @classmethod
    def from_env(cls) -> "UserStore":
        enabled = os.environ.get("BOT_AUTH_ENABLED", "false").lower() in ("true", "1", "yes")
        if not enabled:
            logger.info("Auth: disabled (BOT_AUTH_ENABLED is not true/1/yes). Bot is open for everyone.")
            return cls(enabled=False)

        admin_id = int(os.environ.get("BOT_ADMIN_ID", "0") or "0")
        db_path = os.environ.get("BOT_AUTH_DB", "/app/data/telegram_auth.sqlite3")
        if admin_id == 0:
            raise ValueError("auth enabled but BOT_ADMIN_ID is 0")
        if not db_path:
            raise ValueError("auth enabled but BOT_AUTH_DB is empty")

        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        db = sqlite3.connect(db_path, check_same_thread=False)
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id   INTEGER PRIMARY KEY,
                created_at    TEXT NOT NULL,
                last_activity TEXT NOT NULL
            )
            """
        )
        db.commit()
        logger.info("Auth: ENABLED. Admin ID=%s, DB=%s", admin_id, db_path)
        return cls(enabled=True, admin_id=admin_id, db=db)

    def is_enabled(self) -> bool:
        return self.enabled

    def is_admin(self, telegram_id: int) -> bool:
        return self.enabled and telegram_id == self.admin_id

    def is_authorized(self, telegram_id: int) -> bool:
        if not self.enabled:
            return True
        if telegram_id == self.admin_id:
            return True
        row = self.db.execute("SELECT 1 FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
        return row is not None

    def add_user(self, telegram_id: int) -> None:
        if not self.enabled:
            return
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute(
            """
            INSERT INTO users (telegram_id, created_at, last_activity)
            VALUES (?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET last_activity = excluded.last_activity
            """,
            (telegram_id, now, now),
        )
        self.db.commit()

    def touch(self, telegram_id: int) -> None:
        if not self.enabled or telegram_id == self.admin_id:
            return
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute(
            "UPDATE users SET last_activity = ? WHERE telegram_id = ?",
            (now, telegram_id),
        )
        self.db.commit()

    def list_users(self, limit: int = 100) -> List[DBUser]:
        if not self.enabled:
            return []
        rows = self.db.execute(
            """
            SELECT telegram_id, created_at, last_activity
            FROM users
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [DBUser(telegram_id=row[0], created_at=row[1], last_activity=row[2]) for row in rows]
