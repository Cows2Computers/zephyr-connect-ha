"""The Zephyr Hood integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import ZephyrApiError, ZephyrAuthError, ZephyrCloud
from .const import CONF_EMAIL, CONF_PASSWORD, DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


class ZephyrCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Push coordinator: shadow state arrives via MQTT, not polling."""

    def __init__(self, hass: HomeAssistant, cloud: ZephyrCloud, devices: list[dict]) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=None)
        self.cloud = cloud
        self.devices = {d["thingName"]: d for d in devices if d.get("thingName")}
        self.data = {thing: {} for thing in self.devices}

    @callback
    def _apply(self, thing: str, reported: dict[str, Any]) -> None:
        merged = {**self.data.get(thing, {}), **reported}
        self.async_set_updated_data({**self.data, thing: merged})

    def on_shadow(self, thing: str, reported: dict[str, Any]) -> None:
        """MQTT callback (paho thread) -> marshal onto the event loop."""
        self.hass.loop.call_soon_threadsafe(self._apply, thing, reported)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Zephyr Hood from a config entry."""
    cloud = ZephyrCloud(entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])

    try:
        await hass.async_add_executor_job(cloud.authenticate)
    except ZephyrAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except ZephyrApiError as err:
        raise ConfigEntryNotReady(str(err)) from err

    try:
        devices = await hass.async_add_executor_job(cloud.get_devices)
    except ZephyrApiError as err:
        raise ConfigEntryNotReady(str(err)) from err

    if not devices:
        raise ConfigEntryNotReady("No Zephyr hoods are bound to this account")

    # Merge each hood's static capabilities (authoritative per-device maxes) from
    # /discoverdevice. Non-fatal: entities fall back to sensible defaults if it fails.
    for device in devices:
        thing = device.get("thingName")
        if not thing:
            continue
        try:
            details = await hass.async_add_executor_job(cloud.get_device_details, thing)
        except ZephyrApiError as err:
            _LOGGER.debug("discoverdevice failed for %s: %s", thing, err)
            continue
        for key in ("maxFanSpeed", "maxLightLevel", "maxGreasefilterTimer", "maxCharcoalfilterTimer"):
            if details.get(key) is not None:
                device[key] = details[key]

    coordinator = ZephyrCoordinator(hass, cloud, devices)

    try:
        await hass.async_add_executor_job(cloud.connect, coordinator.on_shadow)
    except ZephyrApiError as err:
        raise ConfigEntryNotReady(f"MQTT connect failed: {err}") from err
    for thing in coordinator.devices:
        cloud.watch_thing(thing)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: ZephyrCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await hass.async_add_executor_job(coordinator.cloud.disconnect)
    return unload_ok
