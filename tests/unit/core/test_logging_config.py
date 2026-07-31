from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from core.logging_config import JSONLogFormatter


def test_json_log_timestamp_is_real_iso8601() -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="message",
        args=(),
        exc_info=None,
    )
    record.created = 1_700_000_000.123456

    timestamp = json.loads(JSONLogFormatter().format(record))["timestamp"]

    assert "%f" not in timestamp
    assert datetime.fromisoformat(timestamp.replace("Z", "+00:00")).tzinfo == UTC
