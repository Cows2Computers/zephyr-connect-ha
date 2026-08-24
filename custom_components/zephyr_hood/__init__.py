"""The Zephyr Hood integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import ZephyrApiError, ZephyrAuthError, ZephyrCloud
from .const import (
    CONF_COGNITO_USERNAME,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_REFRESH_TOKEN,
    DOMAIN,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)


class ZephyrCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Push coordinator: shadow state arrives via MQTT, not polling."""

    def __init__(
        self, hass: HomeAssistant, cloud: ZephyrCloud, devices: list[dict], entry: ConfigEntry
    ) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=None)
        self.cloud = cloud
        self.entry = entry
        self._reauth_started = False
        self.devices = {d["thingName"]: d for d in devices if d.get("thingName")}
        self.data = {thing: {} for thing in self.devices}

    @callback
    def _apply(self, thing: str, reported: dict[str, Any]) -> None:
        merged = {**self.data.get(thing, {}), **reported}
        self.async_set_updated_data({**self.data, thing: merged})

    def on_shadow(self, thing: str, reported: dict[str, Any]) -> None:
        """MQTT callback (paho thread) -> marshal onto the event loop."""
        self.hass.loop.call_soon_threadsafe(self._apply, thing, reported)

    def on_connection_health(self, connected: bool) -> None:
        """MQTT callback (paho thread) -> marshal onto the event loop."""
        self.hass.loop.call_soon_threadsafe(self._set_connected, connected)

    @callback
    def _set_connected(self, connected: bool) -> None:
        if self.last_update_success == connected:
            return
        self.last_update_success = connected
        self.async_update_listeners()

    def on_auth_failed(self) -> None:
        """MQTT/background-thread callback -> marshal onto the event loop."""
        self.hass.loop.call_soon_threadsafe(self._start_reauth)

    @callback
    def _start_reauth(self) -> None:
        if self._reauth_started:
            return
        self._reauth_started = True
        self.hass.async_create_task(
            self.hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_REAUTH, "entry_id": self.entry.entry_id},
                data=self.entry.data,
            )
        )

    def on_command_failed(self, thing: str, field: str, value: Any, reason: str) -> None:
        """MQTT/background-thread callback -> marshal onto the event loop."""
        self.hass.loop.call_soon_threadsafe(self._notify_command_failed, thing, field, value, reason)

    @callback
    def _notify_command_failed(self, thing: str, field: str, value: Any, reason: str) -> None:
        name = self.devices.get(thing, {}).get("modelName") or thing
        persistent_notification.async_create(
            self.hass,
            f"Setting **{field}** to `{value}` on **{name}** failed: {reason}",
            title="Zephyr Hood command failed",
            notification_id=f"zephyr_hood_cmd_{thing}_{field}",
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Zephyr Hood from a config entry."""
    cloud = ZephyrCloud(
        entry.data[CONF_EMAIL],
        password=entry.data.get(CONF_PASSWORD),
        refresh_token=entry.data.get(CONF_REFRESH_TOKEN),
        cognito_username=entry.data.get(CONF_COGNITO_USERNAME),
    )

    try:
        await hass.async_add_executor_job(cloud.authenticate)
    except ZephyrAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except ZephyrApiError as err:
        raise ConfigEntryNotReady(str(err)) from err

    # Once we have a working refresh token, persist that instead of the
    # plaintext password (migrates existing entries that predate this).
    if cloud.refresh_token and (
        entry.data.get(CONF_REFRESH_TOKEN) != cloud.refresh_token
        or entry.data.get(CONF_COGNITO_USERNAME) != cloud.cognito_username
        or CONF_PASSWORD in entry.data
    ):
        new_data = {k: v for k, v in entry.data.items() if k != CONF_PASSWORD}
        new_data[CONF_REFRESH_TOKEN] = cloud.refresh_token
        if cloud.cognito_username:
            new_data[CONF_COGNITO_USERNAME] = cloud.cognito_username
        hass.config_entries.async_update_entry(entry, data=new_data)

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

    coordinator = ZephyrCoordinator(hass, cloud, devices, entry)

    try:
        await hass.async_add_executor_job(
            cloud.connect,
            coordinator.on_shadow,
            coordinator.on_connection_health,
            coordinator.on_auth_failed,
            coordinator.on_command_failed,
        )
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
