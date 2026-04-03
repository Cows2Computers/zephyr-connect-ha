"""The Zephyr Hood integration."""
from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ZephyrHoodAPI, ZephyrHoodAPIError, ZephyrHoodAuthError
from .const import CONF_EMAIL, CONF_PASSWORD, DOMAIN, PLATFORMS, SCAN_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Zephyr Hood from a config entry."""
    session = async_get_clientsession(hass)
    api = ZephyrHoodAPI(
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        session=session,
    )

    try:
        await api.authenticate()
        devices = await api.get_devices()
    except ZephyrHoodAuthError as err:
        _LOGGER.error("Authentication failed: %s", err)
        return False
    except ZephyrHoodAPIError as err:
        raise ConfigEntryNotReady(f"Cannot connect to Zephyr API: {err}") from err

    async def async_update_data() -> dict:
        """Fetch latest data from Zephyr API."""
        try:
            statuses = {}
            for device in devices:
                device_id = device.get("id") or device.get("device_id")
                statuses[device_id] = await api.get_status(device_id)
            return {"devices": devices, "statuses": statuses}
        except ZephyrHoodAPIError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "api": api,
        "devices": devices,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
