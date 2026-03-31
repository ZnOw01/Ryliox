from __future__ import annotations

import json

import pytest

from core.session_store import (
    SessionStore,
    normalize_cookie_records_payload,
    normalize_cookies_payload,
)

pytestmark = pytest.mark.unit


def test_normalize_cookie_records_payload_supports_nested_cookie_dict():
    payload = {"cookies": {"sessionid": "abc", "csrftoken": "def"}}

    assert normalize_cookie_records_payload(payload) == [
        {
            "name": "sessionid",
            "value": "abc",
            "domain": None,
            "path": "/",
            "secure": False,
            "http_only": False,
            "expires": None,
            "same_site": None,
        },
        {
            "name": "csrftoken",
            "value": "def",
            "domain": None,
            "path": "/",
            "secure": False,
            "http_only": False,
            "expires": None,
            "same_site": None,
        },
    ]


def test_normalize_cookies_payload_supports_nested_cookie_header():
    payload = {"cookies": "sessionid=abc; csrftoken=def"}

    assert normalize_cookies_payload(payload) == {
        "sessionid": "abc",
        "csrftoken": "def",
    }


def test_session_store_persists_cookie_records_with_domains_and_paths(tmp_path):
    store = SessionStore(
        db_path=tmp_path / "session.sqlite3",
        legacy_cookies_file=tmp_path / "legacy-cookies.json",
    )

    payload = [
        {
            "name": "sessionid",
            "value": "root",
            "domain": "learning.oreilly.com",
            "path": "/",
            "secure": True,
            "httpOnly": True,
        },
        {
            "name": "sessionid",
            "value": "library",
            "domain": "learning.oreilly.com",
            "path": "/library",
        },
    ]

    assert store.save_cookies(payload) == 2
    assert store.has_cookies() is True

    records = store.get_cookie_records()
    assert len(records) == 2
    assert records[0]["name"] == "sessionid"
    assert {record["path"] for record in records} == {"/", "/library"}


def test_session_store_loads_and_migrates_legacy_cookie_records(tmp_path):
    legacy_file = tmp_path / "legacy-cookies.json"
    legacy_payload = [
        {
            "name": "sessionid",
            "value": "abc",
            "domain": "learning.oreilly.com",
            "path": "/",
            "secure": True,
            "httpOnly": True,
        }
    ]
    legacy_file.write_text(json.dumps(legacy_payload), encoding="utf-8")

    store = SessionStore(
        db_path=tmp_path / "session.sqlite3",
        legacy_cookies_file=legacy_file,
    )

    loaded = store.load_cookie_records(migrate_legacy=True)

    assert loaded[0]["domain"] == "learning.oreilly.com"
    assert loaded[0]["http_only"] is True
    assert store.get_cookies() == {"sessionid": "abc"}


def test_session_store_has_cookies_ignores_invalid_legacy_file(tmp_path):
    legacy_file = tmp_path / "legacy-cookies.json"
    legacy_file.write_text("{not-json", encoding="utf-8")
    store = SessionStore(
        db_path=tmp_path / "session.sqlite3",
        legacy_cookies_file=legacy_file,
    )

    assert store.has_cookies() is False
