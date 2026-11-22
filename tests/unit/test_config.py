"""How environment variables and ``.env`` files map onto the settings."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

import config

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("clean_settings_environment")]


def load(tmp_path: Path, dotenv: str = "") -> config.Settings:
    env_file = tmp_path / ".env"
    env_file.write_text(dotenv, encoding="utf-8")
    return config.Settings(_env_file=env_file)


@pytest.mark.parametrize(
    "name",
    ["RYLIOX_TRUSTED_HOSTS", "ALLOWED_HOSTS", "RYLIOX_SECURITY__ALLOWED_HOSTS"],
)
def test_host_lists_accept_comma_separated_values(monkeypatch, tmp_path, name):
    monkeypatch.setenv(name, "localhost, 127.0.0.1,ryliox-dev")

    assert load(tmp_path).security.allowed_hosts == ["localhost", "127.0.0.1", "ryliox-dev"]


def test_lists_still_accept_json(monkeypatch, tmp_path):
    monkeypatch.setenv("CORS_ORIGINS", '["https://a.example", "https://b.example"]')

    assert load(tmp_path).security.cors_origins == ["https://a.example", "https://b.example"]


def test_documented_short_names_are_read_from_the_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("PORT", "9001")
    monkeypatch.setenv("REQUEST_DELAY", "3.5")
    monkeypatch.setenv("RATE_LIMIT_MAX_REQUESTS", "9")
    monkeypatch.setenv("CACHE_TTL_SEARCH", "7")

    settings = load(tmp_path)

    assert settings.server.port == 9001
    assert settings.http.delay == 3.5
    assert settings.rate_limit.max_requests == 9
    assert settings.cache.search_ttl == 7


def test_prefixed_names_reach_every_group(monkeypatch, tmp_path):
    monkeypatch.setenv("RYLIOX_QUEUE__MAX_QUEUED_JOBS", "7")
    monkeypatch.setenv("RYLIOX_HTTP__EXTRA_HEADERS", '{"Trace": "enabled"}')

    settings = load(tmp_path)

    assert settings.queue.max_queued_jobs == 7
    assert config.request_headers(settings.http)["X-Trace"] == "enabled"


def test_dotenv_file_is_honoured(tmp_path):
    settings = load(tmp_path, "PORT=9100\nLOG_LEVEL=DEBUG\nRYLIOX_QUEUE__MAX_QUEUED_JOBS=3\n")

    assert settings.server.port == 9100
    assert settings.logging.level == "DEBUG"
    assert settings.queue.max_queued_jobs == 3


def test_environment_wins_over_dotenv(monkeypatch, tmp_path):
    monkeypatch.setenv("PORT", "9001")

    assert load(tmp_path, "PORT=9100\n").server.port == 9001


def test_prefixed_name_wins_over_short_name(monkeypatch, tmp_path):
    monkeypatch.setenv("PORT", "9001")
    monkeypatch.setenv("RYLIOX_SERVER__PORT", "9002")

    assert load(tmp_path).server.port == 9002


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("TIMEOUT", "66"),
        ("DELAY", "6.5"),
        ("ENABLED", "false"),
        ("LEVEL", "ERROR"),
        ("DB_NAME", "other.sqlite3"),
    ],
)
def test_generic_names_are_not_settings(monkeypatch, tmp_path, name, value):
    baseline = load(tmp_path)
    monkeypatch.setenv(name, value)

    assert load(tmp_path) == baseline


def test_group_values_from_before_the_prefix_still_load(monkeypatch, tmp_path):
    monkeypatch.setenv("SERVER", '{"host": "0.0.0.0", "port": 9004}')
    monkeypatch.setenv("QUEUE__MAX_QUEUED_JOBS", "7")

    settings = load(tmp_path)

    assert (settings.server.host, settings.server.port) == ("0.0.0.0", 9004)
    assert settings.queue.max_queued_jobs == 7


def test_unrelated_variable_sharing_a_group_name_is_ignored(monkeypatch, tmp_path):
    monkeypatch.setenv("SERVER", "build-host-01")

    assert load(tmp_path).server == config.ServerSettings()


def test_out_of_range_port_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setenv("PORT", "70000")

    with pytest.raises(ValidationError):
        load(tmp_path)


def test_every_state_file_follows_the_data_directory(tmp_path):
    data_dir = tmp_path / "state"
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("RYLIOX_") and key not in config.SHORT_NAMES
    }
    env.update({"DATA_DIR": str(data_dir), "RYLIOX_ENV_FILE": str(tmp_path / "none.env")})
    probe = (
        "import json, config; print(json.dumps([str(p) for p in (config.DOWNLOAD_QUEUE_DB,"
        " config.DOWNLOAD_ERROR_LOG_DIR, config.COOKIES_FILE, config.SESSION_DB_FILE,"
        " config.AUDIT_LOG_FILE)]))"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=Path(config.__file__).parent,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    paths = [Path(p) for p in json.loads(result.stdout)]
    assert all(path.is_relative_to(data_dir) for path in paths), paths


ENV_EXAMPLE = Path(config.__file__).parent / ".env.example"
LAUNCHER_VARIABLES = {
    "RYLIOX_VENV",
    "RYLIOX_TIMEOUT_UV",
    "RYLIOX_TIMEOUT_BUN",
    "RYLIOX_TIMEOUT_DOCKER",
    "RYLIOX_TIMEOUT_SUBPROCESS",
    "RYLIOX_MAX_SERVER_LOG_BYTES",
    "RYLIOX_MAX_SERVER_LOG_BACKUPS",
}


def test_env_example_names_only_variables_that_have_an_effect():
    names = re.findall(r"^#? ?([A-Z][A-Z0-9_]+)=", ENV_EXAMPLE.read_text(encoding="utf-8"), re.M)

    def has_effect(name: str) -> bool:
        if name in config.SHORT_NAMES or name in LAUNCHER_VARIABLES:
            return True
        group = re.match(r"RYLIOX_([A-Z_]+?)__", name)
        return group is not None and group.group(1).lower() in config.Settings.model_fields

    assert names
    assert [name for name in names if not has_effect(name)] == []


def test_env_example_matches_the_defaults():
    assert config.Settings(_env_file=ENV_EXAMPLE) == config.Settings(_env_file=None)
