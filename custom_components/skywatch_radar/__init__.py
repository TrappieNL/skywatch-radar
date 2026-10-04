"""SkyWatch Radar integration."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.components import websocket_api

from .const import CONF_LATITUDE, CONF_LONGITUDE, DOMAIN, PLATFORMS
from .coordinator import SkyWatchRadarCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a SkyWatch Radar config entry."""
    # Register commands before any platform is forwarded. If this fails, HA
    # must not retain a half-created sensor platform for a later retry.
    await _async_register_static_paths(hass)
    _register_websocket_api(hass)
    coordinator = SkyWatchRadarCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_register_static_paths(hass: HomeAssistant) -> None:
    """Expose bundled Lovelace assets for a single HACS installation."""
    key = f"{DOMAIN}_static_paths_registered"
    if hass.data.get(key):
        return
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                "/skywatch-radar-assets",
                str(Path(__file__).parent / "static"),
                True,
            )
        ]
    )
    hass.data[key] = True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration after a configuration change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a SkyWatch Radar config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


@callback
def _register_websocket_api(hass: HomeAssistant) -> None:
    """Register one cache-only WebSocket endpoint for all entries."""
    if hass.data.get(f"{DOMAIN}_websocket_registered"):
        return
    hass.data[f"{DOMAIN}_websocket_registered"] = True

    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/aircraft",
            vol.Optional("entry_id"): cv.string,
        }
    )
    @websocket_api.async_response
    async def websocket_aircraft(
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict,
    ) -> None:
        """Return the most recent validated cache; never trigger a poll."""
        coordinators = hass.data.get(DOMAIN, {})
        entry_id = msg.get("entry_id")
        coordinator = coordinators.get(entry_id) if entry_id else next(iter(coordinators.values()), None)
        if coordinator is None:
            connection.send_error(msg["id"], "not_found", "SkyWatch Radar is not configured")
            return
        connection.send_result(msg["id"], coordinator.websocket_payload())

    websocket_api.async_register_command(hass, websocket_aircraft)

    @websocket_api.require_admin
    @websocket_api.async_response
    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/set_center",
            vol.Optional("entry_id"): cv.string,
            vol.Required("latitude"): vol.Coerce(float),
            vol.Required("longitude"): vol.Coerce(float),
        }
    )
    async def websocket_set_center(
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict,
    ) -> None:
        """Persist a user-confirmed radar centre and let the entry reload."""
        latitude = msg["latitude"]
        longitude = msg["longitude"]
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            connection.send_error(msg["id"], "invalid_center", "Latitude or longitude is outside its valid range")
            return

        rate_key = f"{DOMAIN}_last_center_change"
        now = time.monotonic()
        if now - hass.data.get(rate_key, 0.0) < 2.0:
            connection.send_error(msg["id"], "rate_limited", "Wait before changing the radar centre again")
            return

        coordinators = hass.data.get(DOMAIN, {})
        entry_id = msg.get("entry_id")
        coordinator = coordinators.get(entry_id) if entry_id else next(iter(coordinators.values()), None)
        if coordinator is None:
            connection.send_error(msg["id"], "not_found", "SkyWatch Radar is not configured")
            return

        options = {
            **coordinator.entry.options,
            CONF_LATITUDE: latitude,
            CONF_LONGITUDE: longitude,
        }
        hass.config_entries.async_update_entry(coordinator.entry, options=options)
        hass.data[rate_key] = now
        connection.send_result(msg["id"], {"center": {"lat": latitude, "lon": longitude}})

    websocket_api.async_register_command(hass, websocket_set_center)
