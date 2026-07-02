"""Light platform for the Zephyr Hood integration (cooktop light)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CTRL_LIGHT, DEFAULT_MAX_LIGHT, DOMAIN
from .entity import ZephyrEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(ZephyrLight(coordinator, thing) for thing in coordinator.devices)


class ZephyrLight(ZephyrEntity, LightEntity):
    """The hood's cooktop light (multi-level, mapped to brightness)."""

    _attr_name = "Light"
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(self, coordinator, thing: str) -> None:
        super().__init__(coordinator, thing)
        self._attr_unique_id = f"{thing}_light"

    @property
    def _max(self) -> int:
        return int(
            self._device.get("maxLightLevel")
            or self._reported.get("maxLightLevel")
            or DEFAULT_MAX_LIGHT
        )

    @property
    def is_on(self) -> bool:
        return int(self._reported.get(CTRL_LIGHT, 0) or 0) > 0

    @property
    def brightness(self) -> int:
        level = int(self._reported.get(CTRL_LIGHT, 0) or 0)
        if level <= 0:
            return 0
        return min(255, round(level / self._max * 255))

    async def async_turn_on(self, **kwargs: Any) -> None:
        if ATTR_BRIGHTNESS in kwargs:
            level = max(1, round(kwargs[ATTR_BRIGHTNESS] / 255 * self._max))
        else:
            level = self._max
        await self._async_set(CTRL_LIGHT, level)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set(CTRL_LIGHT, 0)
