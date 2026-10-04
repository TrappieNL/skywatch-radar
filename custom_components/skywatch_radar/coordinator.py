"""Single-flight ADSB.fi polling, validation and track cache."""

from __future__ import annotations

from collections import deque
from datetime import timedelta
import asyncio
import logging
import math
import time
from typing import Any

from aiohttp import ClientError, ClientTimeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    API_URL,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS_KM,
    DOMAIN,
    MAX_AIRCRAFT,
    MAX_TRACK_POINTS,
    UPDATE_INTERVAL_SECONDS,
    USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)


def _finite_number(value: Any) -> float | None:
    """Return a finite numeric value, otherwise None."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance, used to keep client filtering deterministic."""
    radius = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi, d_lambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class SkyWatchRadarCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Own all provider I/O: one request each 10 seconds, one shared cache."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self._tracks: dict[str, deque[tuple[float, float]]] = {}
        self._last_request_monotonic = 0.0
        self._request_lock = asyncio.Lock()
        self._last_success: float | None = None
        self._last_error: str | None = None
        self._consecutive_failures = 0
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
            always_update=True,
        )

    @property
    def settings(self) -> dict[str, Any]:
        return {**self.entry.data, **self.entry.options}

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch, validate and cache aircraft. Previous valid cache survives failure."""
        async with self._request_lock:
            elapsed = time.monotonic() - self._last_request_monotonic
            if elapsed < 1.0:
                await asyncio.sleep(1.0 - elapsed)
            self._last_request_monotonic = time.monotonic()
            settings = self.settings
            latitude = float(settings[CONF_LATITUDE])
            longitude = float(settings[CONF_LONGITUDE])
            radius_km = int(settings[CONF_RADIUS_KM])
            distance_nm = min(250, max(1, math.ceil(radius_km / 1.852)))
            url = API_URL.format(lat=f"{latitude:.6f}", lon=f"{longitude:.6f}", distance_nm=distance_nm)
            try:
                session = async_get_clientsession(self.hass)
                async with session.get(
                    url,
                    headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                    timeout=ClientTimeout(total=8),
                ) as response:
                    if response.status == 429:
                        raise UpdateFailed("ADSB.fi rate limit reached; retaining the last valid cache")
                    if response.status != 200:
                        raise UpdateFailed(f"ADSB.fi returned HTTP {response.status}")
                    payload = await response.json(content_type=None)
                aircraft = self._validate_aircraft(payload, latitude, longitude, radius_km)
            except (ClientError, asyncio.TimeoutError, ValueError, TypeError, UpdateFailed) as error:
                self._consecutive_failures += 1
                self._last_error = str(error)
                if self.data:
                    cached = {**self.data, "status": self._status(online=False), "stale": True}
                    return cached
                raise UpdateFailed(str(error)) from error

            self._consecutive_failures = 0
            self._last_error = None
            self._last_success = time.time()
            return {
                "aircraft": aircraft,
                "center": {"lat": latitude, "lon": longitude, "radius_km": radius_km},
                "status": self._status(online=True),
                "stale": False,
            }

    def _status(self, online: bool) -> dict[str, Any]:
        return {
            "online": online,
            "source": "ADSB.fi Open Data",
            "poll_interval_seconds": UPDATE_INTERVAL_SECONDS,
            "last_success": self._last_success,
            "last_error": self._last_error,
            "consecutive_failures": self._consecutive_failures,
        }

    def _validate_aircraft(self, payload: Any, center_lat: float, center_lon: float, radius_km: int) -> list[dict[str, Any]]:
        """Reject malformed records and only publish bounded, presentation-safe fields."""
        raw_aircraft = payload.get("ac") if isinstance(payload, dict) else None
        if not isinstance(raw_aircraft, list):
            raise UpdateFailed("ADSB.fi response does not contain an aircraft list")
        aircraft: list[dict[str, Any]] = []
        for raw in raw_aircraft[:MAX_AIRCRAFT]:
            if not isinstance(raw, dict):
                continue
            hex_code = str(raw.get("hex", "")).strip().lower()
            lat, lon = _finite_number(raw.get("lat")), _finite_number(raw.get("lon"))
            if len(hex_code) not in (6, 7) or lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
                continue
            distance = _distance_km(center_lat, center_lon, lat, lon)
            if distance > radius_km * 1.05:
                continue
            track = self._tracks.setdefault(hex_code, deque(maxlen=MAX_TRACK_POINTS))
            point = (round(lat, 6), round(lon, 6))
            if not track or track[-1] != point:
                track.append(point)
            altitude = _finite_number(raw.get("alt_baro"))
            groundspeed = _finite_number(raw.get("gs"))
            heading = _finite_number(raw.get("track"))
            aircraft.append(
                {
                    "hex": hex_code,
                    "flight": str(raw.get("flight") or "").strip(),
                    "registration": str(raw.get("r") or "").strip(),
                    "type": str(raw.get("t") or "").strip(),
                    "description": str(raw.get("desc") or "").strip(),
                    "lat": point[0],
                    "lon": point[1],
                    "altitude_ft": round(altitude) if altitude is not None else None,
                    "altitude_geom_ft": round(_finite_number(raw.get("alt_geom"))) if _finite_number(raw.get("alt_geom")) is not None else None,
                    "groundspeed_kt": round(groundspeed) if groundspeed is not None else None,
                    "track_deg": round(heading % 360, 1) if heading is not None else None,
                    "true_heading_deg": round(_finite_number(raw.get("true_heading")) % 360, 1) if _finite_number(raw.get("true_heading")) is not None else None,
                    "vertical_rate_fpm": round(_finite_number(raw.get("baro_rate"))) if _finite_number(raw.get("baro_rate")) is not None else None,
                    "geom_rate_fpm": round(_finite_number(raw.get("geom_rate"))) if _finite_number(raw.get("geom_rate")) is not None else None,
                    "ias_kt": round(_finite_number(raw.get("ias"))) if _finite_number(raw.get("ias")) is not None else None,
                    "tas_kt": round(_finite_number(raw.get("tas"))) if _finite_number(raw.get("tas")) is not None else None,
                    "mach": round(_finite_number(raw.get("mach")), 3) if _finite_number(raw.get("mach")) is not None else None,
                    "squawk": str(raw.get("squawk") or "").strip(),
                    "category": str(raw.get("category") or "").strip(),
                    "nav_altitude_ft": round(_finite_number(raw.get("nav_altitude_mcp"))) if _finite_number(raw.get("nav_altitude_mcp")) is not None else None,
                    "nav_heading_deg": round(_finite_number(raw.get("nav_heading")) % 360, 1) if _finite_number(raw.get("nav_heading")) is not None else None,
                    "nav_qnh_hpa": round(_finite_number(raw.get("nav_qnh")), 1) if _finite_number(raw.get("nav_qnh")) is not None else None,
                    "wind_speed_kt": round(_finite_number(raw.get("ws"))) if _finite_number(raw.get("ws")) is not None else None,
                    "wind_direction_deg": round(_finite_number(raw.get("wd")) % 360, 1) if _finite_number(raw.get("wd")) is not None else None,
                    "signal_dbfs": round(_finite_number(raw.get("rssi")), 1) if _finite_number(raw.get("rssi")) is not None else None,
                    "messages": int(raw["messages"]) if isinstance(raw.get("messages"), int | float) else None,
                    "distance_km": round(distance, 1),
                    "emergency": str(raw.get("emergency") or "none"),
                    "seen_seconds": _finite_number(raw.get("seen")),
                    "seen_position_seconds": _finite_number(raw.get("seen_pos")),
                    "track": [[p[0], p[1]] for p in track],
                }
            )
        return aircraft

    def websocket_payload(self) -> dict[str, Any]:
        """Serve a snapshot from RAM: WebSocket requests never call ADSB.fi."""
        data = self.data or {"aircraft": [], "center": {}, "status": self._status(online=False), "stale": True}
        # DataUpdateCoordinator no longer exposes ``last_update_success_time``
        # in Home Assistant 2026.10. Keep our own timestamp so this endpoint is
        # compatible while still making no outbound request.
        return {**data, "updated_at": self._last_success}
