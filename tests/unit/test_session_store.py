"""Unit tests for SessionStore.

Tests cover:
- Cookie normalization
- Cookie storage and retrieval
- Database operations
- Legacy JSON migration
- Edge cases
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from typing import TYPE_CHECKING
from unittest.mock import patch

from core.session_store import SessionStore, normalize_cookies_payload

if TYPE_CHECKING:
    from pathlib import Path


class TestNormalizeCookiesPayload:
    """Tests for normalize_cookies_payload function."""

    def test_empty_payload(self):
        """Test that None returns empty dict."""
        result = normalize_cookies_payload(None)
        assert result == {}

    def test_dict_payload(self):
        """Test normalizing dict payload."""
        payload = {"session": "abc123", "user": "test"}
        result = normalize_cookies_payload(payload)
        assert result == {"session": "abc123", "user": "test"}

    def test_list_payload(self):
        """Test normalizing EditThisCookie list format."""
        payload = [
            {"name": "session", "value": "abc123"},
            {"name": "user", "value": "test"},
        ]
        result = normalize_cookies_payload(payload)
        assert result == {"session": "abc123", "user": "test"}

    def test_string_payload(self):
        """Test normalizing cookie string format."""
        payload = "session=abc123; user=test; token=xyz"
        result = normalize_cookies_payload(payload)
        assert result == {"session": "abc123", "user": "test", "token": "xyz"}

    def test_cookie_header_format(self):
        """Test normalizing 'Cookie: name=value' format."""
        payload = "Cookie: session=abc123; user=test"
        result = normalize_cookies_payload(payload)
        assert result == {"session": "abc123", "user": "test"}

    def test_nested_cookies_field(self):
        """Test payload with nested 'cookies' field."""
        payload = {
            "cookies": [
                {"name": "session", "value": "abc123"},
            ]
        }
        result = normalize_cookies_payload(payload)
        assert result == {"session": "abc123"}

    def test_nested_single_cookie(self):
        """Test payload with single cookie in 'cookies' field."""
        payload = {
            "name": "session",
            "value": "abc123",
        }
        result = normalize_cookies_payload(payload)
        assert result == {"session": "abc123"}

    def test_invalid_values_filtered(self):
        """Test that invalid values are filtered out."""
        payload = {
            "valid": "value",
            "invalid": {"nested": "dict"},  # Should be filtered
            "also_invalid": ["list"],  # Should be filtered
        }
        result = normalize_cookies_payload(payload)
        assert result == {"valid": "value"}

    def test_none_values(self):
        """Test that None values are handled."""
        payload = {"session": None, "user": "test"}
        result = normalize_cookies_payload(payload)
        assert result == {"session": "", "user": "test"}

    def test_empty_strings_filtered(self):
        """Test that empty cookie names are filtered."""
        payload = {
            "": "value",
            "valid": "test",
        }
        result = normalize_cookies_payload(payload)
        assert result == {"valid": "test"}


class TestSessionStoreInitialization:
    """Tests for SessionStore initialization."""

    def test_creates_database_file(self, temp_db_path: Path):
        """Test that SessionStore creates database file."""
        assert not temp_db_path.exists()

        SessionStore(db_path=temp_db_path)

        assert temp_db_path.exists()

    def test_creates_directory_if_not_exists(self, temp_dir: Path):
        """Test that SessionStore creates parent directories."""
        nested_path = temp_dir / "nested" / "path" / "cookies.db"

        SessionStore(db_path=nested_path)

        assert nested_path.parent.exists()

    def test_initializes_table(self, temp_db_path: Path):
        """Test that SessionStore creates required table."""
        SessionStore(db_path=temp_db_path)

        # Verify table exists by querying it
        with closing(sqlite3.connect(str(temp_db_path))) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='session_cookie_records'"
            )
            assert cursor.fetchone() is not None


class TestSessionStoreSaveCookies:
    """Tests for save_cookies method."""

    def test_save_cookies_dict(self, temp_db_path: Path):
        """Test saving cookies as dict."""
        store = SessionStore(db_path=temp_db_path)
        cookies = {"session": "abc123", "user": "test"}

        count = store.save_cookies(cookies)

        assert count == 2

    def test_save_overwrites_previous(self, temp_db_path: Path):
        """Test that save overwrites previous cookies."""
        store = SessionStore(db_path=temp_db_path)

        store.save_cookies({"old": "cookie"})
        store.save_cookies({"new": "cookie"})

        result = store.get_cookies()
        assert result == {"new": "cookie"}

    def test_save_empty_clears_all(self, temp_db_path: Path):
        """Test that saving empty dict clears all cookies."""
        store = SessionStore(db_path=temp_db_path)

        store.save_cookies({"session": "test"})
        store.save_cookies({})

        result = store.get_cookies()
        assert result == {}

    def test_save_returns_count(self, temp_db_path: Path):
        """Test that save returns number of cookies saved."""
        store = SessionStore(db_path=temp_db_path)
        cookies = {"a": "1", "b": "2", "c": "3"}

        count = store.save_cookies(cookies)

        assert count == 3


class TestSessionStoreGetCookies:
    """Tests for get_cookies method."""

    def test_get_empty_store(self, temp_db_path: Path):
        """Test getting cookies from empty store."""
        store = SessionStore(db_path=temp_db_path)

        result = store.get_cookies()

        assert result == {}

    def test_get_returns_saved_cookies(self, temp_db_path: Path):
        """Test that get returns saved cookies."""
        store = SessionStore(db_path=temp_db_path)
        cookies = {"session": "abc123", "user": "test"}

        store.save_cookies(cookies)
        result = store.get_cookies()

        assert result == cookies

    def test_get_cookie_records_returns_saved_metadata(self, temp_db_path: Path):
        """Test that record retrieval preserves cookie metadata."""
        store = SessionStore(db_path=temp_db_path)
        payload = [
            {
                "name": "session",
                "value": "abc123",
                "domain": "example.com",
                "path": "/",
                "secure": True,
                "httpOnly": True,
            }
        ]

        store.save_cookies(payload)
        result = store.get_cookie_records()

        assert result == [
            {
                "name": "session",
                "value": "abc123",
                "domain": "example.com",
                "path": "/",
                "secure": True,
                "http_only": True,
                "expires": None,
                "same_site": None,
            }
        ]

    def test_get_sorted_by_name(self, temp_db_path: Path):
        """Test that cookies are sorted by name."""
        store = SessionStore(db_path=temp_db_path)
        # Save in non-alphabetical order
        store.save_cookies({"z": "last", "a": "first", "m": "middle"})

        result = store.get_cookies()

        # Should be sorted
        assert list(result.keys()) == ["a", "m", "z"]

    def test_get_handles_database_error(self, temp_db_path: Path, monkeypatch):
        """Test that get handles database errors gracefully."""
        store = SessionStore(db_path=temp_db_path)
        store.save_cookies({"test": "value"})

        # Corrupt the database
        def mock_connect(*args, **kwargs):
            raise sqlite3.Error("Database error")

        monkeypatch.setattr(sqlite3, "connect", mock_connect)

        result = store.get_cookies()

        assert result == {}


class TestSessionStoreHasCookies:
    """Tests for has_cookies method."""

    def test_has_cookies_false_when_empty(self, temp_db_path: Path):
        """Test that has_cookies returns False for empty store."""
        store = SessionStore(db_path=temp_db_path)

        assert store.has_cookies() is False

    def test_has_cookies_true_when_data(self, temp_db_path: Path):
        """Test that has_cookies returns True when cookies exist."""
        store = SessionStore(db_path=temp_db_path)
        store.save_cookies({"session": "test"})

        assert store.has_cookies() is True

    def test_has_cookies_no_legacy_fallback(self, temp_db_path: Path, temp_dir: Path):
        """Test has_cookies with legacy fallback disabled."""
        legacy_file = temp_dir / "legacy_cookies.json"
        legacy_file.write_text('{"legacy": "cookie"}')

        store = SessionStore(db_path=temp_db_path, legacy_cookies_file=legacy_file)

        # Should not check legacy when fallback disabled
        assert store.has_cookies(allow_legacy_fallback=False) is False


class TestSessionStoreLegacyMigration:
    """Tests for legacy JSON migration."""

    def test_load_cookies_migrates_legacy(self, temp_db_path: Path, temp_dir: Path):
        """Test that load_cookies migrates from legacy file."""
        legacy_file = temp_dir / "legacy_cookies.json"
        legacy_data = {"session": "legacy_session", "auth": "legacy_auth"}
        legacy_file.write_text(json.dumps(legacy_data))

        store = SessionStore(db_path=temp_db_path, legacy_cookies_file=legacy_file)

        result = store.load_cookies()

        assert result == legacy_data
        # Should now be in database too
        assert store.get_cookies() == legacy_data

    def test_load_cookies_prefers_database(self, temp_db_path: Path, temp_dir: Path):
        """Test that load_cookies prefers database over legacy."""
        legacy_file = temp_dir / "legacy_cookies.json"
        legacy_file.write_text('{"session": "legacy"}')

        store = SessionStore(db_path=temp_db_path, legacy_cookies_file=legacy_file)

        # Save different cookie to database
        store.save_cookies({"session": "database"})

        result = store.load_cookies()

        # Should return database value
        assert result == {"session": "database"}

    def test_load_cookies_no_migration_on_error(self, temp_db_path: Path, temp_dir: Path):
        """Test that load_cookies handles migration errors."""
        legacy_file = temp_dir / "legacy_cookies.json"
        legacy_file.write_text('{"session": "legacy"}')

        store = SessionStore(db_path=temp_db_path, legacy_cookies_file=legacy_file)

        # Break the save operation
        with patch.object(store, "save_cookies", side_effect=sqlite3.Error("DB Error")):
            result = store.load_cookies()

        # Should still return legacy data even if migration failed
        assert result == {"session": "legacy"}

    def test_read_legacy_json_unicode_error(self, temp_db_path: Path, temp_dir: Path):
        """Test handling of UnicodeDecodeError in legacy file."""
        legacy_file = temp_dir / "legacy_cookies.json"
        # Write invalid UTF-8 bytes
        legacy_file.write_bytes(b'\xff\xfe{"session": "test"}')

        store = SessionStore(db_path=temp_db_path, legacy_cookies_file=legacy_file)

        # Should handle gracefully
        result = store._read_legacy_json()

        # May or may not parse depending on recovery
        assert isinstance(result, list)

    def test_load_cookies_migrates_legacy_sqlite_file(self, temp_db_path: Path, temp_dir: Path):
        """Test migrating cookies from a legacy SQLite store file."""
        legacy_file = temp_dir / "cookies.sqlite3"
        with closing(sqlite3.connect(str(legacy_file))) as conn:
            conn.execute(
                """
                CREATE TABLE session_cookies (
                    name TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                "INSERT INTO session_cookies(name, value, updated_at) VALUES (?, ?, ?)",
                ("session", "legacy-sqlite", 123.0),
            )
            conn.commit()

        store = SessionStore(db_path=temp_db_path, legacy_cookies_file=legacy_file)

        result = store.load_cookies()

        assert result == {"session": "legacy-sqlite"}
        assert store.get_cookies() == {"session": "legacy-sqlite"}

    def test_load_cookies_migrates_legacy_table_in_current_database(self, temp_db_path: Path):
        """Test migrating cookies from the legacy table in the current DB."""
        store = SessionStore(db_path=temp_db_path)
        with closing(sqlite3.connect(str(temp_db_path))) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS session_cookies (
                    name TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                "INSERT OR REPLACE INTO session_cookies(name, value, updated_at) VALUES (?, ?, ?)",
                ("session", "from-legacy-table", 456.0),
            )
            conn.execute("DELETE FROM session_cookie_records")
            conn.commit()

        result = store.load_cookies()

        assert result == {"session": "from-legacy-table"}
        assert store.get_cookies() == {"session": "from-legacy-table"}


class TestSessionStoreEdgeCases:
    """Edge case tests for SessionStore."""

    def test_save_unicode_cookies(self, temp_db_path: Path):
        """Test saving cookies with unicode values."""
        store = SessionStore(db_path=temp_db_path)
        cookies = {"session": "测试", "user": "用户"}

        store.save_cookies(cookies)
        result = store.get_cookies()

        assert result == cookies

    def test_save_large_cookies(self, temp_db_path: Path):
        """Test saving cookies with large values."""
        store = SessionStore(db_path=temp_db_path)
        large_value = "x" * 10000
        cookies = {"session": large_value}

        store.save_cookies(cookies)
        result = store.get_cookies()

        assert result == cookies

    def test_save_many_cookies(self, temp_db_path: Path):
        """Test saving many cookies."""
        store = SessionStore(db_path=temp_db_path)
        cookies = {f"cookie_{i}": f"value_{i}" for i in range(100)}

        count = store.save_cookies(cookies)
        result = store.get_cookies()

        assert count == 100
        assert len(result) == 100

    def test_concurrent_access(self, temp_db_path: Path):
        """Test that concurrent access is safe."""
        import threading

        store = SessionStore(db_path=temp_db_path)
        results = []

        def worker(worker_id: int):
            cookies = {f"worker_{worker_id}": str(worker_id)}
            store.save_cookies(cookies)
            result = store.get_cookies()
            results.append((worker_id, result))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All operations should complete without errors
        assert len(results) == 10
