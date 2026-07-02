"""Config flow for the Zephyr Hood integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import ZephyrApiError, ZephyrAuthError, ZephyrCloud
from .const import CONF_EMAIL, CONF_PASSWORD, DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD, autocomplete="current-password"
            )
        ),
    }
)


class ZephyrHoodConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the Zephyr Hood config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Prompt for Zephyr Connect credentials and validate them."""
        errors: dict[str, str] = {}

        if user_input is not None:
            cloud = ZephyrCloud(user_input[CONF_EMAIL], user_input[CONF_PASSWORD])
            try:
                await self.hass.async_add_executor_job(cloud.authenticate)
                devices = await self.hass.async_add_executor_job(cloud.get_devices)
            except ZephyrAuthError as err:
                _LOGGER.warning("Zephyr authentication failed: %s", err)
                errors["base"] = "invalid_auth"
            except ZephyrApiError as err:
                _LOGGER.warning("Zephyr cloud connection failed: %s", err)
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error validating Zephyr credentials")
                errors["base"] = "unknown"
            else:
                if not devices:
                    errors["base"] = "no_devices"
                else:
                    await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"{MANUFACTURER} Hood", data=user_input
                    )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
