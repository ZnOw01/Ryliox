"""Authentication plugin: validate the user is logged in to O'Reilly."""

from __future__ import annotations

import logging

from .base import Plugin

logger = logging.getLogger(__name__)


class AuthPlugin(Plugin):
    async def validate_session(self) -> bool:
        """Return True if the current cookie jar authenticates successfully."""
        status = await self.get_status()
        return bool(status.get("valid"))

    async def get_status(self) -> dict:
        """Return a structured session status.

        Returns a dict with at least ``valid`` and ``reason`` keys.
        """
        jwt_status = self._safe_jwt_status()
        if jwt_status is not None:
            if not jwt_status["valid"] and self.http.has_refresh_cookie():
                response = await self.http.get("/profile/", allow_redirects=False)
                return self._parse_profile_response(response)
            return jwt_status
        response = await self.http.get("/profile/", allow_redirects=False)
        return self._parse_profile_response(response)

    def _safe_jwt_status(self) -> dict | None:
        """Call ``http.get_jwt_status`` defensively — may not exist on mocks."""
        get_jwt = getattr(self.http, "get_jwt_status", None)
        if get_jwt is None:
            return None
        try:
            return get_jwt()
        except Exception:
            return None

    @staticmethod
    def _parse_profile_response(response) -> dict:
        url_attr = getattr(response, "url", "") or ""
        url = str(url_attr)
        text = getattr(response, "text", "") or ""
        status_code = getattr(response, "status_code", 0)

        if "login" in url or "signin" in url:
            return {"valid": False, "reason": "not_authenticated"}
        if status_code != 200:
            return {
                "valid": False,
                "reason": "not_authenticated",
                "status_code": status_code,
            }

        # Prefer the structured JSON payload when available. The new O'Reilly
        # profile endpoint returns a JSON object with ``user_type``; an old
        # session returns HTML and ``response.json()`` raises.
        payload = None
        json_call = getattr(response, "json", None)
        if callable(json_call):
            try:
                payload = json_call()
            except (ValueError, TypeError):
                payload = None

        if isinstance(payload, dict):
            if payload.get("user_type") == "Expired":
                return {"valid": False, "reason": "subscription_expired"}
            return {"valid": True, "reason": None}

        if '"user_type":"Expired"' in text:
            return {"valid": False, "reason": "subscription_expired"}

        # If the body is HTML and mentions the login page markers, treat as
        # not authenticated; otherwise the HTML 200 page is the legacy
        # authenticated profile page.
        if "<html" in text.lower() or "<!doctype html" in text.lower():
            lowered = text.lower()
            if "login" in lowered or "signin" in lowered:
                return {"valid": False, "reason": "not_authenticated"}
            return {"valid": True, "reason": None}

        return {"valid": False, "reason": "not_authenticated"}
