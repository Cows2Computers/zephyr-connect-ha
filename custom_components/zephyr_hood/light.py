"""Light platform for Zephyr Hood."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import LightEntity, ColorMode, ATTR_BRIGHTNESS
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LIGHT_LEVEL_HIGH, LIGHT_LEVEL_LOW, MANUFACTURER

_LOGGER = logging.getLogger(__name__)

# Map HA brightness (0-255) to Zephyr light levels (1-3)
BRIGHTNESS_TO_LEVEL = {
    1: 85,   # Level 1 = ~33%
    2: 170,  # Level 2 = ~67%
    3: 255,  # Level 3 = 100%
}


def brightness_to_level(brightness: int) -> int:
    """Convert HA brightness (0-255) to Zephyr level (1-3)."""
    if brightness <= 85:
        return 1
    if brightness <= 170:
        return 2
    return 3


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Zephyr Hood light entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    api = data["api"]
    devices = data["devices"]

    async_add_entities(
        ZephyrHoodLight(coordinator, api, device) for device in devices
    )


class ZephyrHoodLight(CoordinatorEntity, LightEntity):
    """Representation of the Zephyr Hood light."""

    _attr_has_entity_name = True
    _attr_name = "Light"
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(self, coordinator, api, device: dict) -> None:
        """Initialize the light entity."""
        super().__init__(coordinator)
        self._api = api
        self._device = device
        self._device_id = device.get("id") or device.get("device_id")
        self._attr_unique_id = f"{self._device_id}_light"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._device.get("name", "Zephyr Hood"),
            manufacturer=MANUFACTURER,
            model=self._device.get("model", "Lux Connect"),
        )

    @property
    def _status(self) -> dict:
        """Return current device status from coordinator."""
        return self.coordinator.data.get("statuses", {}).get(self._device_id, {})

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        # TODO: Update key after traffic analysis
        level = self._status.get("light_level", 0)
        return int(level) > 0

    @property
    def brightness(self) -> int | None:
        """Return current brightness."""
        level = int(self._status.get("light_level", 0))
        return BRIGHTNESS_TO_LEVEL.get(level, 0)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
        level = brightness_to_level(brightness)
        await self._api.set_light_level(self._device_id, level)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._api.set_light_level(self._device_id, 0)
        await self.coordinator.async_request_refresh()
