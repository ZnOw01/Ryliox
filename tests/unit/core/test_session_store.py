from __future__ import annotations

import json

import pytest

from core.session_store import SessionStore, normalize_cookies_payload

pytestmark = pytest.mark.unit


def test_normalize_cookies_payload_supports_nested_cookie_dict():
    payload = {"cookies": {"sessionid": "abc", "csrftoken": "def"}}

    assert normalize_cookies_payload(payload) == {
        "sessionid": "abc",
        "csrftoken": "def",
    }


def test_normalize_cookies_payload_supports_nested_cookie_header():
    payload = {"cookies": "sessionid=abc; csrftoken=def"}

    assert normalize_cookies_payload(payload) == {
        "sessionid": "abc",
        "csrftoken": "def",
    }


def test_session_store_persists_cookies_with_fresh_connections(tmp_path):
    store = SessionStore(
        db_path=tmp_path / "session.sqlite3",
        legacy_cookies_file=tmp_path / "legacy-cookies.json",
    )

    payload = {"sessionid": "abc", "csrftoken": "def"}

    assert store.save_cookies(payload) == 2
    assert store.get_cookies() == payload
    assert store.has_cookies() is True

    reopened = SessionStore(
        db_path=tmp_path / "session.sqlite3",
        legacy_cookies_file=tmp_path / "legacy-cookies.json",
    )

    assert reopened.get_cookies() == payload


def test_session_store_loads_and_migrates_legacy_cookies(tmp_path):
    legacy_file = tmp_path / "legacy-cookies.json"
    legacy_payload = {"cookies": "sessionid=abc; csrftoken=def"}
    legacy_file.write_text(json.dumps(legacy_payload), encoding="utf-8")

    store = SessionStore(
        db_path=tmp_path / "session.sqlite3",
        legacy_cookies_file=legacy_file,
    )

    assert store.get_cookies() == {}

    loaded = store.load_cookies(migrate_legacy=True)

    expected = {
        "sessionid": "abc",
        "csrftoken": "def",
    }
    assert loaded == expected
    assert store.get_cookies() == expected
    assert store.has_cookies() is True
