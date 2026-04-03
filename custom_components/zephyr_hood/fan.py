"""Fan platform for Zephyr Hood."""
from __future__ import annotations

import logging
import math
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, FAN_SPEED_MAX, FAN_SPEED_MIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Zephyr Hood fan entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    api = data["api"]
    devices = data["devices"]

    async_add_entities(
        ZephyrHoodFan(coordinator, api, device) for device in devices
    )


class ZephyrHoodFan(CoordinatorEntity, FanEntity):
    """Representation of a Zephyr Hood fan."""

    _attr_has_entity_name = True
    _attr_name = "Fan"
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED | FanEntityFeature.TURN_OFF | FanEntityFeature.TURN_ON
    )

    def __init__(self, coordinator, api, device: dict) -> None:
        """Initialize the fan entity."""
        super().__init__(coordinator)
        self._api = api
        self._device = device
        self._device_id = device.get("id") or device.get("device_id")
        self._attr_unique_id = f"{self._device_id}_fan"

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
        """Return true if fan is on."""
        # TODO: Update key after traffic analysis
        speed = self._status.get("fan_speed", 0)
        return int(speed) > 0

    @property
    def percentage(self) -> int | None:
        """Return current speed as a percentage."""
        speed = int(self._status.get("fan_speed", 0))
        if speed == 0:
            return 0
        return math.ceil((speed / FAN_SPEED_MAX) * 100)

    @property
    def speed_count(self) -> int:
        """Return number of speeds."""
        return FAN_SPEED_MAX

    async def async_turn_on(self, percentage: int | None = None, **kwargs: Any) -> None:
        """Turn on the fan."""
        speed = FAN_SPEED_MIN
        if percentage:
            speed = max(FAN_SPEED_MIN, math.ceil((percentage / 100) * FAN_SPEED_MAX))
        await self._api.set_fan_speed(self._device_id, speed)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        await self._api.set_fan_speed(self._device_id, 0)
        await self.coordinator.async_request_refresh()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set fan speed by percentage."""
        if percentage == 0:
            await self.async_turn_off()
            return
        speed = max(FAN_SPEED_MIN, math.ceil((percentage / 100) * FAN_SPEED_MAX))
        await self._api.set_fan_speed(self._device_id, speed)
        await self.coordinator.async_request_refresh()
