"""Zephyr Hood API client."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import (
    API_BASE_URL,
    API_LOGIN_ENDPOINT,
    API_DEVICES_ENDPOINT,
    API_STATUS_ENDPOINT,
    API_CONTROL_ENDPOINT,
)

_LOGGER = logging.getLogger(__name__)


class ZephyrHoodAPIError(Exception):
    """Exception raised for Zephyr Hood API errors."""


class ZephyrHoodAuthError(ZephyrHoodAPIError):
    """Exception raised for authentication errors."""


class ZephyrHoodAPI:
    """Client for the Zephyr Hood cloud API."""

    def __init__(self, email: str, password: str, session: aiohttp.ClientSession) -> None:
        """Initialize the API client."""
        self._email = email
        self._password = password
        self._session = session
        self._token: str | None = None
        self._device_id: str | None = None

    async def authenticate(self) -> bool:
        """Authenticate with the Zephyr cloud and store token."""
        # NOTE: Endpoint and payload structure TBD after traffic analysis
        try:
            resp = await self._session.post(
                f"{API_BASE_URL}{API_LOGIN_ENDPOINT}",
                json={"email": self._email, "password": self._password},
            )
            if resp.status == 401:
                raise ZephyrHoodAuthError("Invalid credentials")
            resp.raise_for_status()
            data = await resp.json()
            # TODO: Update token key after traffic analysis
            self._token = data.get("token") or data.get("access_token")
            if not self._token:
                raise ZephyrHoodAPIError("No token in response")
            return True
        except aiohttp.ClientError as err:
            raise ZephyrHoodAPIError(f"Connection error: {err}") from err

    async def get_devices(self) -> list[dict[str, Any]]:
        """Return list of registered Zephyr devices."""
        resp = await self._request("GET", API_DEVICES_ENDPOINT)
        # TODO: Update response key after traffic analysis
        return resp.get("devices", [resp]) if isinstance(resp, dict) else resp

    async def get_status(self, device_id: str) -> dict[str, Any]:
        """Return current status of a device."""
        return await self._request("GET", f"{API_STATUS_ENDPOINT}/{device_id}")

    async def set_fan_speed(self, device_id: str, speed: int) -> bool:
        """Set fan speed (0=off, 1-6=speeds)."""
        # TODO: Update payload structure after traffic analysis
        await self._request(
            "POST",
            API_CONTROL_ENDPOINT,
            json={"device_id": device_id, "command": "fan", "value": speed},
        )
        return True

    async def set_light_level(self, device_id: str, level: int) -> bool:
        """Set light level (0=off, 1-3=levels)."""
        # TODO: Update payload structure after traffic analysis
        await self._request(
            "POST",
            API_CONTROL_ENDPOINT,
            json={"device_id": device_id, "command": "light", "value": level},
        )
        return True

    async def set_delay_off(self, device_id: str, minutes: int) -> bool:
        """Set delay-off timer in minutes (0-10)."""
        await self._request(
            "POST",
            API_CONTROL_ENDPOINT,
            json={"device_id": device_id, "command": "delay_off", "value": minutes},
        )
        return True

    async def _request(
        self, method: str, endpoint: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Make an authenticated request to the API."""
        if not self._token:
            await self.authenticate()
        headers = {"Authorization": f"Bearer {self._token}"}
        try:
            resp = await self._session.request(
                method,
                f"{API_BASE_URL}{endpoint}",
                headers=headers,
                **kwargs,
            )
            if resp.status == 401:
                # Token expired — re-authenticate once
                await self.authenticate()
                headers["Authorization"] = f"Bearer {self._token}"
                resp = await self._session.request(
                    method,
                    f"{API_BASE_URL}{endpoint}",
                    headers=headers,
                    **kwargs,
                )
            resp.raise_for_status()
            return await resp.json()
        except aiohttp.ClientError as err:
            raise ZephyrHoodAPIError(f"Request failed: {err}") from err
