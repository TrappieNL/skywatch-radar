"""Configuration flow for SkyWatch Radar."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS_KM,
    DEFAULT_LATITUDE,
    DEFAULT_LONGITUDE,
    DEFAULT_RADIUS_KM,
    DOMAIN,
    MAX_RADIUS_KM,
    MIN_RADIUS_KM,
)


def _schema(defaults: dict | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_LATITUDE, default=defaults.get(CONF_LATITUDE, DEFAULT_LATITUDE)): vol.Coerce(float),
            vol.Required(CONF_LONGITUDE, default=defaults.get(CONF_LONGITUDE, DEFAULT_LONGITUDE)): vol.Coerce(float),
            vol.Required(CONF_RADIUS_KM, default=defaults.get(CONF_RADIUS_KM, DEFAULT_RADIUS_KM)): vol.All(
                vol.Coerce(int), vol.Range(min=MIN_RADIUS_KM, max=MAX_RADIUS_KM)
            ),
        }
    )


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an initial SkyWatch Radar setup."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        if user_input is not None:
            if not -90 <= user_input[CONF_LATITUDE] <= 90 or not -180 <= user_input[CONF_LONGITUDE] <= 180:
                return self.async_show_form(step_id="user", data_schema=_schema(user_input), errors={"base": "invalid_coordinates"})
            await self.async_set_unique_id("skywatch_radar")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="SkyWatch Radar", data=user_input)
        return self.async_show_form(step_id="user", data_schema=_schema())

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> OptionsFlowHandler:
        # Home Assistant 2026 injects ``config_entry`` into OptionsFlow.
        # Passing it to the constructor raises a TypeError on this version.
        return OptionsFlowHandler()


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Expose radar location and range in Home Assistant settings."""

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        if user_input is not None:
            if not -90 <= user_input[CONF_LATITUDE] <= 90 or not -180 <= user_input[CONF_LONGITUDE] <= 180:
                return self.async_show_form(step_id="init", data_schema=_schema(user_input), errors={"base": "invalid_coordinates"})
            return self.async_create_entry(title="", data=user_input)
        values = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(step_id="init", data_schema=_schema(values))
