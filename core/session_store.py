"""SQLite-backed session/cookie persistence with legacy JSON fallback."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Mapping

import config


def _cookies_from_dict(raw: dict[str, Any]) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for name, value in raw.items():
        cookie_name = str(name).strip()
        if not cookie_name:
            continue
        if isinstance(value, (dict, list, tuple, set)):
            continue
        cookies[cookie_name] = "" if value is None else str(value)
    return cookies


def _cookies_from_list(raw: list[Any]) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        cookies[name] = "" if item.get("value") is None else str(item.get("value"))
    return cookies


def _cookies_from_cookie_header(raw: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    value = raw.strip()
    if value.lower().startswith("cookie:"):
        value = value.split(":", 1)[1].strip()

    for part in value.split(";"):
        chunk = part.strip()
        if not chunk or "=" not in chunk:
            continue
        name, cookie_value = chunk.split("=", 1)
        cookie_name = name.strip()
        if cookie_name:
            cookies[cookie_name] = cookie_value.strip()
    return cookies


def normalize_cookies_payload(payload: Any) -> dict[str, str]:
    """Normalize supported cookie payload shapes to {name: value}."""
    if payload is None:
        return {}

    if isinstance(payload, dict):
        cookies_field = payload.get("cookies")
        if isinstance(cookies_field, list):
            normalized = _cookies_from_list(cookies_field)
            if normalized:
                return normalized

        if "name" in payload and "value" in payload:
            normalized = _cookies_from_list([payload])
            if normalized:
                return normalized

        return _cookies_from_dict(payload)

    if isinstance(payload, list):
        return _cookies_from_list(payload)

    if isinstance(payload, str):
        return _cookies_from_cookie_header(payload)

    return {}


class SessionStore:
    """Store and load normalized cookies from SQLite, with legacy JSON migration."""

    def __init__(self, db_path: Path | None = None, legacy_cookies_file: Path | None = None):
        self.legacy_cookies_file = Path(legacy_cookies_file or config.COOKIES_FILE)
        self.db_path = Path(db_path) if db_path is not None else config.SESSION_DB_FILE
        self._lock = threading.RLock()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _initialize(self):
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS session_cookies (
                        name TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at REAL NOT NULL
                    )
                    """
                )
                conn.commit()

    def _read_legacy_json(self) -> dict[str, str]:
        path = self.legacy_cookies_file
        if not path.exists():
            return {}

        raw: Any
        try:
            with open(path, encoding="utf-8") as file_handle:
                raw = json.load(file_handle)
        except UnicodeDecodeError:
            try:
                with open(path, encoding="utf-8-sig", errors="replace") as file_handle:
                    raw = json.load(file_handle)
            except (json.JSONDecodeError, OSError, ValueError):
                return {}
        except (json.JSONDecodeError, OSError, ValueError):
            return {}
        return normalize_cookies_payload(raw)

    def save_cookies(self, payload: Mapping[str, str] | dict[str, str]) -> int:
        """Replace current cookie set with provided cookie mapping."""
        cookies = normalize_cookies_payload(dict(payload))
        now = time.time()
        with self._lock:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("DELETE FROM session_cookies")
                if cookies:
                    rows = [(name, value, now) for name, value in cookies.items()]
                    conn.executemany(
                        """
                        INSERT INTO session_cookies(name, value, updated_at)
                        VALUES (?, ?, ?)
                        """,
                        rows,
                    )
                conn.commit()
        return len(cookies)

    def get_cookies(self) -> dict[str, str]:
        with self._lock:
            try:
                with self._connect() as conn:
                    rows = conn.execute(
                        """
                        SELECT name, value
                        FROM session_cookies
                        ORDER BY name ASC
                        """
                    ).fetchall()
            except sqlite3.Error:
                return {}
        return {str(row["name"]): str(row["value"]) for row in rows}

    def _count_stored_cookies(self) -> int:
        with self._lock:
            try:
                with self._connect() as conn:
                    row = conn.execute("SELECT COUNT(*) AS total FROM session_cookies").fetchone()
            except sqlite3.Error:
                return 0
        return int(row["total"]) if row is not None else 0

    def load_cookies(self, migrate_legacy: bool = True) -> dict[str, str]:
        """Load cookies from SQLite, with optional migration from legacy JSON file."""
        cookies = self.get_cookies()
        if cookies:
            return cookies

        legacy = self._read_legacy_json()
        if legacy and migrate_legacy:
            try:
                self.save_cookies(legacy)
            except sqlite3.Error:
                pass
        return legacy

    def has_cookies(self, allow_legacy_fallback: bool = True) -> bool:
        if self._count_stored_cookies() > 0:
            return True
        if not allow_legacy_fallback:
            return False

        legacy = self._read_legacy_json()
        if legacy:
            return True

        try:
            return self.legacy_cookies_file.exists() and self.legacy_cookies_file.stat().st_size > 0
        except OSError:
            return self.legacy_cookies_file.exists()
