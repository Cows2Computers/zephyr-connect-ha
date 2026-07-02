"""Base entity for the Zephyr Hood integration."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER


class ZephyrEntity(CoordinatorEntity):
    """Common base: shadow access + device registry entry, keyed by thing."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, thing_name: str) -> None:
        super().__init__(coordinator)
        self._thing = thing_name
        self._device = coordinator.devices[thing_name]

    @property
    def _reported(self) -> dict[str, Any]:
        """Latest reported shadow state for this hood (empty until first message)."""
        return self.coordinator.data.get(self._thing) or {}

    @property
    def available(self) -> bool:
        return super().available and self._reported.get("isOnline", 1) not in (0, "0", False)

    @property
    def device_info(self) -> DeviceInfo:
        model = self._device.get("modelName") or "Zephyr Hood"
        info = DeviceInfo(
            identifiers={(DOMAIN, self._thing)},
            name=model,
            manufacturer=MANUFACTURER,
            model=model,
        )
        if self._device.get("SN"):
            info["serial_number"] = self._device["SN"]
        if self._device.get("MAC"):
            info["connections"] = {("mac", self._device["MAC"])}
        return info

    async def _async_set(self, field: str, value: Any) -> None:
        """Send a control command, then optimistically refresh."""
        await self.hass.async_add_executor_job(
            self.coordinator.cloud.set_value, self._thing, field, value
        )
