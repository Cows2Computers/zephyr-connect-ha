"""Fan platform for the Zephyr Hood integration (blower)."""
from __future__ import annotations

import math
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CTRL_FAN, DEFAULT_MAX_FAN, DOMAIN
from .entity import ZephyrEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(ZephyrFan(coordinator, thing) for thing in coordinator.devices)


class ZephyrFan(ZephyrEntity, FanEntity):
    """The hood blower."""

    _attr_name = "Fan"
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator, thing: str) -> None:
        super().__init__(coordinator, thing)
        self._attr_unique_id = f"{thing}_fan"

    @property
    def _max(self) -> int:
        return int(
            self._device.get("maxFanSpeed")
            or self._reported.get("maxFanSpeed")
            or DEFAULT_MAX_FAN
        )

    @property
    def speed_count(self) -> int:
        return self._max

    @property
    def is_on(self) -> bool:
        return int(self._reported.get(CTRL_FAN, 0) or 0) > 0

    @property
    def percentage(self) -> int:
        speed = int(self._reported.get(CTRL_FAN, 0) or 0)
        if speed <= 0:
            return 0
        return min(100, round(speed / self._max * 100))

    async def async_set_percentage(self, percentage: int) -> None:
        speed = 0 if percentage == 0 else max(1, math.ceil(percentage / 100 * self._max))
        await self._async_set(CTRL_FAN, speed)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        if percentage:
            await self.async_set_percentage(percentage)
        else:
            await self._async_set(CTRL_FAN, 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set(CTRL_FAN, 0)
