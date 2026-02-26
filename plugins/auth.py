"""Authentication plugin."""

import logging
from typing import Any

from .base import Plugin

logger = logging.getLogger(__name__)


class AuthPlugin(Plugin):
    """Handle and validate session status."""

    async def get_status(self) -> dict[str, Any]:
        """Return session status with keys: valid and reason."""
        try:
            response = await self.http.get("/profile/", allow_redirects=False)
        except Exception as exc:
            logger.error("Network error while checking session: %s", exc)
            return {"valid": False, "reason": "network_error"}

        if response.status_code != 200:
            return {"valid": False, "reason": "not_authenticated"}

        if '"user_type":"Expired"' in response.text:
            return {"valid": False, "reason": "subscription_expired"}

        return {"valid": True, "reason": None}

    async def validate_session(self) -> bool:
        """Return True when the current session is valid."""
        status = await self.get_status()
        return bool(status.get("valid"))
