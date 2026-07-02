"""Sensor platform for the Zephyr Hood integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEFAULT_MAX_CHARCOAL_HOURS,
    DEFAULT_MAX_GREASE_HOURS,
    DOMAIN,
    KEY_MAX_CHARCOAL,
    KEY_MAX_GREASE,
)
from .entity import ZephyrEntity


@dataclass(frozen=True, kw_only=True)
class FilterDesc:
    key: str
    name: str
    use_field: str
    max_device_key: str
    default_max_hours: int


# Filter life remaining, matching the Zephyr app: it tracks accumulated minutes
# of use and shows the % of life left vs the device's max (hours -> *60 minutes).
FILTERS: tuple[FilterDesc, ...] = (
    FilterDesc(
        key="grease_filter_life",
        name="Grease filter life",
        use_field="usegreasefiltertime",
        max_device_key=KEY_MAX_GREASE,
        default_max_hours=DEFAULT_MAX_GREASE_HOURS,
    ),
    FilterDesc(
        key="charcoal_filter_life",
        name="Charcoal filter life",
        use_field="usecharcoalfiltertime",
        max_device_key=KEY_MAX_CHARCOAL,
        default_max_hours=DEFAULT_MAX_CHARCOAL_HOURS,
    ),
)


@dataclass(frozen=True, kw_only=True)
class RuntimeDesc:
    key: str
    name: str
    field: str
    icon: str


RUNTIMES: tuple[RuntimeDesc, ...] = (
    RuntimeDesc(key="fan_runtime", name="Fan runtime", field="usefantime", icon="mdi:fan-clock"),
    RuntimeDesc(key="light_runtime", name="Light runtime", field="uselighttime", icon="mdi:lightbulb-on-outline"),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []
    for thing in coordinator.devices:
        entities.extend(ZephyrFilterLifeSensor(coordinator, thing, d) for d in FILTERS)
        entities.extend(ZephyrRuntimeSensor(coordinator, thing, d) for d in RUNTIMES)
        entities.append(ZephyrFaultSensor(coordinator, thing))
    async_add_entities(entities)


def _used_fraction(reported, device, desc: FilterDesc) -> float | None:
    """Fraction of filter life consumed (0..1), or None if unknown."""
    use = reported.get(desc.use_field)
    if use is None:
        return None
    max_hours = int(device.get(desc.max_device_key) or desc.default_max_hours)
    if max_hours <= 0:
        return None
    return min(1.0, int(use) / (max_hours * 60))


class ZephyrFilterLifeSensor(ZephyrEntity, SensorEntity):
    """Percentage of filter life remaining (100% = fresh, 0% = replace)."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:air-filter"

    def __init__(self, coordinator, thing: str, desc: FilterDesc) -> None:
        super().__init__(coordinator, thing)
        self._desc = desc
        self._attr_name = desc.name
        self._attr_unique_id = f"{thing}_{desc.key}"

    @property
    def native_value(self) -> int | None:
        frac = _used_fraction(self._reported, self._device, self._desc)
        if frac is None:
            return None
        return 100 - round(frac * 100)

    @property
    def extra_state_attributes(self) -> dict:
        use = self._reported.get(self._desc.use_field)
        max_hours = int(self._device.get(self._desc.max_device_key) or self._desc.default_max_hours)
        attrs: dict = {"max_life_hours": max_hours}
        if use is not None:
            attrs["used_minutes"] = int(use)
        return attrs


class ZephyrRuntimeSensor(ZephyrEntity, SensorEntity):
    """Cumulative fan/light on-time, in minutes (diagnostic)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(self, coordinator, thing: str, desc: RuntimeDesc) -> None:
        super().__init__(coordinator, thing)
        self._desc = desc
        self._attr_name = desc.name
        self._attr_icon = desc.icon
        self._attr_unique_id = f"{thing}_{desc.key}"

    @property
    def native_value(self) -> int | None:
        value = self._reported.get(self._desc.field)
        return None if value is None else int(value)


class ZephyrFaultSensor(ZephyrEntity, SensorEntity):
    """Reported fault code(s); 'OK' when the hood reports none."""

    _attr_name = "Fault code"
    _attr_icon = "mdi:alert-circle-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, thing: str) -> None:
        super().__init__(coordinator, thing)
        self._attr_unique_id = f"{thing}_fault_code"

    @property
    def native_value(self) -> str | None:
        fault = self._reported.get("faultCode")
        if fault is None:
            return None
        if isinstance(fault, (list, tuple)):
            return ", ".join(str(f) for f in fault) if fault else "OK"
        return "OK" if fault in (0, "0", "") else str(fault)
