"""Number platform for the Zephyr Hood integration (delay-off timer)."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CTRL_DELAY_TIMER, DEFAULT_MAX_DELAY, DOMAIN
from .entity import ZephyrEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(ZephyrDelayTimer(coordinator, thing) for thing in coordinator.devices)


class ZephyrDelayTimer(ZephyrEntity, NumberEntity):
    """Delayed shut-off timer, in minutes (0 = off)."""

    _attr_name = "Delay off"
    _attr_icon = "mdi:timer-outline"
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = 0
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(self, coordinator, thing: str) -> None:
        super().__init__(coordinator, thing)
        self._attr_unique_id = f"{thing}_delay_off"

    @property
    def native_max_value(self) -> float:
        return float(self._reported.get("maxDelayTimer") or DEFAULT_MAX_DELAY)

    @property
    def native_value(self) -> float | None:
        value = self._reported.get(CTRL_DELAY_TIMER, self._reported.get("delaytimer"))
        return None if value is None else float(value)

    async def async_set_native_value(self, value: float) -> None:
        await self._async_set(CTRL_DELAY_TIMER, int(value))
