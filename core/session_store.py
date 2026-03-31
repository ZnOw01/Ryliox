"""SQLite-backed session/cookie persistence with legacy JSON fallback."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import config

logger = logging.getLogger(__name__)

CookieRecord = dict[str, Any]


def _parse_cookie_expires(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    if isinstance(value, (int, float)):
        return int(float(value))
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return int(float(stripped))
        except ValueError:
            return None
    return None


def _normalize_cookie_name(value: Any) -> str:
    return str(value or "").strip()


def _normalize_cookie_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple, set)):
        return ""
    return str(value)


def _normalize_cookie_record(raw: Mapping[str, Any], *, default_domain: str | None = None) -> CookieRecord | None:
    name = _normalize_cookie_name(raw.get("name"))
    if not name:
        return None

    domain_value = str(raw.get("domain") or default_domain or "").strip().lower().lstrip(".")
    path_value = str(raw.get("path") or "/").strip() or "/"
    expires = _parse_cookie_expires(raw.get("expires"))

    record: CookieRecord = {
        "name": name,
        "value": _normalize_cookie_value(raw.get("value")),
        "domain": domain_value or None,
        "path": path_value,
        "secure": bool(raw.get("secure")),
        "http_only": bool(raw.get("httpOnly") or raw.get("http_only")),
        "expires": expires,
        "same_site": str(raw.get("sameSite") or raw.get("same_site") or "").strip() or None,
    }
    return record


def _cookies_from_dict(raw: Mapping[str, Any]) -> list[CookieRecord]:
    cookies: list[CookieRecord] = []
    for name, value in raw.items():
        cookie_name = _normalize_cookie_name(name)
        if not cookie_name:
            continue
        if isinstance(value, Mapping) and {"name", "value"} & set(value):
            normalized = _normalize_cookie_record(value, default_domain=None)
            if normalized is not None:
                cookies.append(normalized)
            continue
        if isinstance(value, (dict, list, tuple, set)):
            continue
        cookies.append(
            {
                "name": cookie_name,
                "value": _normalize_cookie_value(value),
                "domain": None,
                "path": "/",
                "secure": False,
                "http_only": False,
                "expires": None,
                "same_site": None,
            }
        )
    return cookies


def _cookies_from_list(raw: list[Any]) -> list[CookieRecord]:
    cookies: list[CookieRecord] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        normalized = _normalize_cookie_record(item)
        if normalized is not None:
            cookies.append(normalized)
    return cookies


def _cookies_from_cookie_header(raw: str) -> list[CookieRecord]:
    cookies: list[CookieRecord] = []
    value = raw.strip()
    if value.lower().startswith("cookie:"):
        value = value.split(":", 1)[1].strip()

    for part in value.split(";"):
        chunk = part.strip()
        if not chunk or "=" not in chunk:
            continue
        name, cookie_value = chunk.split("=", 1)
        cookie_name = _normalize_cookie_name(name)
        if not cookie_name:
            continue
        cookies.append(
            {
                "name": cookie_name,
                "value": cookie_value.strip(),
                "domain": None,
                "path": "/",
                "secure": False,
                "http_only": False,
                "expires": None,
                "same_site": None,
            }
        )
    return cookies


def _dedupe_cookie_records(records: list[CookieRecord]) -> list[CookieRecord]:
    deduped: list[CookieRecord] = []
    seen: set[tuple[str, str, str]] = set()
    for record in records:
        key = (
            _normalize_cookie_name(record.get("name")),
            str(record.get("domain") or "").lower(),
            str(record.get("path") or "/"),
        )
        if not key[0] or key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def normalize_cookie_records_payload(payload: Any) -> list[CookieRecord]:
    """Normalize supported cookie payload shapes to cookie records."""
    if payload is None:
        return []

    records: list[CookieRecord]
    if isinstance(payload, Mapping):
        cookies_field = payload.get("cookies")
        if isinstance(cookies_field, Mapping):
            records = _cookies_from_dict(cookies_field)
        elif isinstance(cookies_field, list):
            records = _cookies_from_list(cookies_field)
        elif isinstance(cookies_field, str):
            records = _cookies_from_cookie_header(cookies_field)
        elif "name" in payload and "value" in payload:
            records = _cookies_from_list([payload])
        else:
            records = _cookies_from_dict(payload)
    elif isinstance(payload, list):
        records = _cookies_from_list(payload)
    elif isinstance(payload, str):
        records = _cookies_from_cookie_header(payload)
    else:
        records = []

    return _dedupe_cookie_records(records)


def normalize_cookies_payload(payload: Any) -> dict[str, str]:
    """Normalize supported payloads to a flat ``{name: value}`` mapping."""
    cookies: dict[str, str] = {}
    for record in normalize_cookie_records_payload(payload):
        cookies[str(record["name"])] = str(record["value"])
    return cookies


class SessionStore:
    """Store and load cookies from SQLite, with legacy JSON migration."""

    def __init__(
        self, db_path: Path | None = None, legacy_cookies_file: Path | None = None
    ):
        self.legacy_cookies_file = Path(legacy_cookies_file or config.COOKIES_FILE)
        self.db_path = Path(db_path) if db_path is not None else config.SESSION_DB_FILE
        self._lock = threading.RLock()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _initialize(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS session_cookie_records (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        value TEXT NOT NULL,
                        domain TEXT,
                        path TEXT NOT NULL DEFAULT '/',
                        secure INTEGER NOT NULL DEFAULT 0,
                        http_only INTEGER NOT NULL DEFAULT 0,
                        expires INTEGER,
                        same_site TEXT,
                        updated_at REAL NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_session_cookie_unique
                    ON session_cookie_records(name, COALESCE(domain, ''), path)
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_session_cookie_name
                    ON session_cookie_records(name)
                    """
                )
                conn.commit()

    def _read_legacy_json(self) -> list[CookieRecord]:
        path = self.legacy_cookies_file
        if not path.exists():
            return []

        raw: Any
        try:
            with open(path, encoding="utf-8") as file_handle:
                raw = json.load(file_handle)
        except UnicodeDecodeError as exc:
            logger.warning("Legacy cookies file is not valid UTF-8 (%s): %s", path, exc)
            try:
                with open(path, encoding="utf-8-sig", errors="replace") as file_handle:
                    raw = json.load(file_handle)
            except (json.JSONDecodeError, OSError, ValueError) as fallback_exc:
                logger.warning("Failed to read legacy cookies file with UTF-8 BOM fallback (%s): %s", path, fallback_exc)
                return []
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            logger.warning("Failed to read legacy cookies file (%s): %s", path, exc)
            return []
        return normalize_cookie_records_payload(raw)

    def save_cookies(self, payload: Any) -> int:
        """Replace the current cookie set with the provided payload."""
        cookies = normalize_cookie_records_payload(payload)
        now = time.time()
        with self._lock:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("DELETE FROM session_cookie_records")
                if cookies:
                    rows = [
                        (
                            str(cookie["name"]),
                            str(cookie["value"]),
                            cookie.get("domain"),
                            str(cookie.get("path") or "/"),
                            1 if cookie.get("secure") else 0,
                            1 if cookie.get("http_only") else 0,
                            cookie.get("expires"),
                            cookie.get("same_site"),
                            now,
                        )
                        for cookie in cookies
                    ]
                    conn.executemany(
                        """
                        INSERT INTO session_cookie_records(
                            name, value, domain, path, secure, http_only, expires, same_site, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        rows,
                    )
                conn.commit()
        return len(cookies)

    def get_cookies(self) -> dict[str, str]:
        rows: list[sqlite3.Row] = []
        with self._lock:
            try:
                with self._connect() as conn:
                    rows = conn.execute(
                        """
                        SELECT name, value, domain, path, secure, http_only, expires, same_site
                        FROM session_cookie_records
                        ORDER BY
                            CASE WHEN domain IS NULL OR domain = '' THEN 1 ELSE 0 END,
                            LENGTH(COALESCE(domain, '')) DESC,
                            path ASC,
                            name ASC
                        """
                    ).fetchall()
            except sqlite3.Error:
                return []
        return [
            {
                "name": str(row["name"]),
                "value": str(row["value"]),
                "domain": str(row["domain"]).lower() if row["domain"] else None,
                "path": str(row["path"] or "/"),
                "secure": bool(row["secure"]),
                "http_only": bool(row["http_only"]),
                "expires": int(row["expires"]) if row["expires"] is not None else None,
                "same_site": str(row["same_site"]) if row["same_site"] else None,
            }
            for row in rows
        ]

    def get_cookies(self) -> dict[str, str]:
        cookies: dict[str, str] = {}
        for record in self.get_cookie_records():
            cookies[str(record["name"])] = str(record["value"])
        return cookies

    def _count_stored_cookies(self) -> int:
        row: sqlite3.Row | None = None
        with self._lock:
            try:
                with self._connect() as conn:
                    row = conn.execute(
                        "SELECT COUNT(*) AS total FROM session_cookies"
                    ).fetchone()
            except sqlite3.Error:
                return 0
        return int(row["total"]) if row is not None else 0

    def load_cookie_records(self, migrate_legacy: bool = True) -> list[CookieRecord]:
        """Load cookie records, with optional migration from legacy JSON."""
        cookies = self.get_cookie_records()
        if cookies:
            return cookies

        legacy = self._read_legacy_json()
        if legacy and migrate_legacy:
            try:
                self.save_cookies(legacy)
            except sqlite3.Error:
                logger.warning("Failed to migrate legacy cookies from %s", self.legacy_cookies_file)
        return legacy

    def load_cookies(self, migrate_legacy: bool = True) -> dict[str, str]:
        records = self.load_cookie_records(migrate_legacy=migrate_legacy)
        cookies: dict[str, str] = {}
        for record in records:
            cookies[str(record["name"])] = str(record["value"])
        return cookies

    def has_cookies(self, allow_legacy_fallback: bool = True) -> bool:
        if self._count_stored_cookies() > 0:
            return True
        if not allow_legacy_fallback:
            return False

        legacy = self._read_legacy_json()
        if legacy:
            return True

        try:
            return (
                self.legacy_cookies_file.exists()
                and self.legacy_cookies_file.stat().st_size > 0
            )
        except OSError:
            return self.legacy_cookies_file.exists()
