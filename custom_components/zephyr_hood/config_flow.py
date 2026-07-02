"""Config flow for the Zephyr Hood integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import ZephyrApiError, ZephyrAuthError, ZephyrCloud
from .const import CONF_EMAIL, CONF_PASSWORD, CONF_REFRESH_TOKEN, DOMAIN, MANUFACTURER

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

STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
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

    def __init__(self) -> None:
        self._reauth_entry: ConfigEntry | None = None

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
                    # Store the refresh token, not the password: the password
                    # is only ever used transiently to obtain the token.
                    return self.async_create_entry(
                        title=f"{MANUFACTURER} Hood",
                        data={
                            CONF_EMAIL: user_input[CONF_EMAIL],
                            CONF_REFRESH_TOKEN: cloud.refresh_token,
                        },
                    )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> FlowResult:
        """Handle re-authentication when the stored refresh token has expired."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Prompt for the password again and mint a fresh refresh token."""
        errors: dict[str, str] = {}
        assert self._reauth_entry is not None

        if user_input is not None:
            cloud = ZephyrCloud(
                self._reauth_entry.data[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
            try:
                await self.hass.async_add_executor_job(cloud.authenticate)
            except ZephyrAuthError as err:
                _LOGGER.warning("Zephyr re-authentication failed: %s", err)
                errors["base"] = "invalid_auth"
            except ZephyrApiError as err:
                _LOGGER.warning("Zephyr cloud connection failed: %s", err)
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error validating Zephyr credentials")
                errors["base"] = "unknown"
            else:
                new_data = {
                    k: v for k, v in self._reauth_entry.data.items() if k != CONF_PASSWORD
                }
                new_data[CONF_REFRESH_TOKEN] = cloud.refresh_token
                return self.async_update_reload_and_abort(
                    self._reauth_entry, data=new_data
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"email": self._reauth_entry.data[CONF_EMAIL]},
        )
