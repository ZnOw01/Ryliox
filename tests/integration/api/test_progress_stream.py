from __future__ import annotations

import asyncio

import pytest
from fastapi.responses import StreamingResponse

from web.routes.downloads import progress_stream

pytestmark = pytest.mark.integration


def test_progress_stream_returns_sse_response(app_client):
    queue = app_client.app.state.download_queue
    response = asyncio.run(progress_stream(job_id=None, download_queue=queue))
    assert isinstance(response, StreamingResponse)
    assert response.media_type == "text/event-stream"
