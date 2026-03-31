"""Authentication plugin."""

import logging
from collections.abc import Mapping
from typing import Any

from .base import Plugin

logger = logging.getLogger(__name__)


def _is_expired_profile_payload(payload: Any) -> bool:
    """Return True when the profile payload explicitly marks the account expired."""
    if not isinstance(payload, Mapping):
        return False

    user_type = payload.get("user_type")
    if not isinstance(user_type, str):
        return False

    return user_type.strip().casefold() == "expired"


def _html_indicates_authenticated_session(content: str) -> bool:
    normalized = str(content or "").casefold()
    authenticated_markers = (
        "sign out",
        "logout",
        "/logout",
        "data-testid=\"logout\"",
    )
    unauthenticated_markers = (
        "sign in",
        "log in",
        "/login",
        "data-testid=\"login\"",
    )

    if any(marker in normalized for marker in authenticated_markers):
        return True
    if any(marker in normalized for marker in unauthenticated_markers):
        return False
    return False


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

        try:
            data = response.json()
        except (ValueError, KeyError, TypeError, AttributeError):
            if _html_indicates_authenticated_session(getattr(response, "text", "")):
                logger.info("HTML /profile/ response accepted as authenticated session.")
                return {"valid": True, "reason": None}
            logger.warning("Unexpected non-JSON /profile/ response while checking session.")
            return {"valid": False, "reason": "not_authenticated"}

        if _is_expired_profile_payload(data):
            return {"valid": False, "reason": "subscription_expired"}

        if not isinstance(data, Mapping):
            return {"valid": False, "reason": "not_authenticated"}

        return {"valid": True, "reason": None}

    async def validate_session(self) -> bool:
        """Return True when the current session is valid."""
        status = await self.get_status()
        return bool(status.get("valid"))
