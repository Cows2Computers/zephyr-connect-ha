"""Sensor platform for Zephyr Hood."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Zephyr Hood sensor entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    devices = data["devices"]

    entities = []
    for device in devices:
        entities.append(ZephyrHoodFilterSensor(coordinator, device))
        entities.append(ZephyrHoodFanSpeedSensor(coordinator, device))
    async_add_entities(entities)


class ZephyrHoodBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for Zephyr Hood sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, device: dict) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device = device
        self._device_id = device.get("id") or device.get("device_id")

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


class ZephyrHoodFilterSensor(ZephyrHoodBaseSensor):
    """Sensor for filter status."""

    _attr_name = "Filter Status"
    _attr_icon = "mdi:air-filter"

    def __init__(self, coordinator, device: dict) -> None:
        """Initialize filter sensor."""
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{self._device_id}_filter_status"

    @property
    def native_value(self) -> str:
        """Return filter status."""
        # TODO: Update key after traffic analysis
        return self._status.get("filter_status", "unknown")


class ZephyrHoodFanSpeedSensor(ZephyrHoodBaseSensor):
    """Sensor showing current fan speed as a number."""

    _attr_name = "Fan Speed"
    _attr_icon = "mdi:fan"
    _attr_native_unit_of_measurement = "speed"

    def __init__(self, coordinator, device: dict) -> None:
        """Initialize fan speed sensor."""
        super().__init__(coordinator, device)
        self._attr_unique_id = f"{self._device_id}_fan_speed"

    @property
    def native_value(self) -> int:
        """Return current fan speed (0-6)."""
        # TODO: Update key after traffic analysis
        return int(self._status.get("fan_speed", 0))
