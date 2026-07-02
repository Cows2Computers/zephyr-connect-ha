"""Button platform for the Zephyr Hood integration (filter resets)."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CTRL_RESET_CHARCOAL, CTRL_RESET_GREASE, DOMAIN
from .entity import ZephyrEntity


@dataclass(frozen=True, kw_only=True)
class ResetDesc:
    key: str
    name: str
    field: str


# Press after physically cleaning/replacing a filter — resets the hood's usage
# counter (writes resetgreasefilter/resetcharcoalfilter = 1, same as the app).
RESETS: tuple[ResetDesc, ...] = (
    ResetDesc(key="reset_grease_filter", name="Reset grease filter", field=CTRL_RESET_GREASE),
    ResetDesc(key="reset_charcoal_filter", name="Reset charcoal filter", field=CTRL_RESET_CHARCOAL),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        ZephyrResetButton(coordinator, thing, desc)
        for thing in coordinator.devices
        for desc in RESETS
    )


class ZephyrResetButton(ZephyrEntity, ButtonEntity):
    """Reset a filter's usage counter."""

    _attr_icon = "mdi:restart"

    def __init__(self, coordinator, thing: str, desc: ResetDesc) -> None:
        super().__init__(coordinator, thing)
        self._desc = desc
        self._attr_name = desc.name
        self._attr_unique_id = f"{thing}_{desc.key}"

    async def async_press(self) -> None:
        await self._async_set(self._desc.field, 1)
