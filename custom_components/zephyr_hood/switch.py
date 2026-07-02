"""Switch platform for the Zephyr Hood integration (mode toggles)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CTRL_CLEANAIR, CTRL_RECIRCULATING, DOMAIN
from .entity import ZephyrEntity


@dataclass(frozen=True, kw_only=True)
class ZephyrSwitchDescription:
    key: str
    name: str
    field: str
    icon: str | None = None


SWITCHES: tuple[ZephyrSwitchDescription, ...] = (
    ZephyrSwitchDescription(
        key="recirculating",
        name="Recirculating mode",
        field=CTRL_RECIRCULATING,
        icon="mdi:air-purifier",
    ),
    ZephyrSwitchDescription(
        key="clean_air",
        name="Clean air",
        field=CTRL_CLEANAIR,
        icon="mdi:weather-windy",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        ZephyrSwitch(coordinator, thing, desc)
        for thing in coordinator.devices
        for desc in SWITCHES
    )


class ZephyrSwitch(ZephyrEntity, SwitchEntity):
    """A boolean hood mode (recirculating, clean-air)."""

    def __init__(self, coordinator, thing: str, desc: ZephyrSwitchDescription) -> None:
        super().__init__(coordinator, thing)
        self._desc = desc
        self._attr_name = desc.name
        self._attr_icon = desc.icon
        self._attr_unique_id = f"{thing}_{desc.key}"

    @property
    def is_on(self) -> bool:
        return int(self._reported.get(self._desc.field, 0) or 0) > 0

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_set(self._desc.field, 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set(self._desc.field, 0)
