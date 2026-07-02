"""Binary sensor platform for the Zephyr Hood integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEFAULT_MAX_CHARCOAL_HOURS,
    DEFAULT_MAX_GREASE_HOURS,
    DOMAIN,
    FILTER_REPLACE_FRACTION,
    KEY_MAX_CHARCOAL,
    KEY_MAX_GREASE,
)
from .entity import ZephyrEntity


@dataclass(frozen=True, kw_only=True)
class FilterAlarmDesc:
    key: str
    name: str
    use_field: str
    max_device_key: str
    default_max_hours: int


# "Needs cleaning" is computed from usage vs the device max (app threshold: >=85%
# used), NOT from the shadow's alarm* flags — the app ignores those and they can
# be stale.
FILTER_ALARMS: tuple[FilterAlarmDesc, ...] = (
    FilterAlarmDesc(
        key="grease_filter",
        name="Grease filter",
        use_field="usegreasefiltertime",
        max_device_key=KEY_MAX_GREASE,
        default_max_hours=DEFAULT_MAX_GREASE_HOURS,
    ),
    FilterAlarmDesc(
        key="charcoal_filter",
        name="Charcoal filter",
        use_field="usecharcoalfiltertime",
        max_device_key=KEY_MAX_CHARCOAL,
        default_max_hours=DEFAULT_MAX_CHARCOAL_HOURS,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[BinarySensorEntity] = []
    for thing in coordinator.devices:
        entities.append(ZephyrOnline(coordinator, thing))
        entities.extend(ZephyrFilterAlarm(coordinator, thing, d) for d in FILTER_ALARMS)
    async_add_entities(entities)


class ZephyrOnline(ZephyrEntity, BinarySensorEntity):
    """Cloud connectivity of the hood (reported by the device shadow)."""

    _attr_name = "Online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, thing: str) -> None:
        super().__init__(coordinator, thing)
        self._attr_unique_id = f"{thing}_online"

    @property
    def available(self) -> bool:
        # Must report online/offline, so it can't gate on isOnline itself.
        return super(ZephyrEntity, self).available

    @property
    def is_on(self) -> bool:
        return self._reported.get("isOnline", 0) not in (0, "0", False, None)


class ZephyrFilterAlarm(ZephyrEntity, BinarySensorEntity):
    """Filter needs cleaning/replacing (problem) — derived from usage."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:air-filter"

    def __init__(self, coordinator, thing: str, desc: FilterAlarmDesc) -> None:
        super().__init__(coordinator, thing)
        self._desc = desc
        self._attr_name = desc.name
        self._attr_unique_id = f"{thing}_{desc.key}_alarm"

    @property
    def is_on(self) -> bool:
        use = self._reported.get(self._desc.use_field)
        if use is None:
            return False
        max_hours = int(self._device.get(self._desc.max_device_key) or self._desc.default_max_hours)
        if max_hours <= 0:
            return False
        return int(use) / (max_hours * 60) >= FILTER_REPLACE_FRACTION
