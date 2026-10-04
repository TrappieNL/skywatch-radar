"""Constants for SkyWatch Radar."""

from __future__ import annotations

DOMAIN = "skywatch_radar"
PLATFORMS = ["sensor"]

CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_RADIUS_KM = "radius_km"

DEFAULT_LATITUDE = 52.10095  # Geografisch middelpunt bij Lunteren
DEFAULT_LONGITUDE = 5.64622
DEFAULT_RADIUS_KM = 150
MIN_RADIUS_KM = 10
MAX_RADIUS_KM = 400  # ADSB.fi accepts 250 NM (about 463 km)
UPDATE_INTERVAL_SECONDS = 10
API_URL = "https://opendata.adsb.fi/api/v3/lat/{lat}/lon/{lon}/dist/{distance_nm}"
USER_AGENT = "SkyWatch-Radar/0.1 (Home Assistant; personal use)"
MAX_TRACK_POINTS = 12
MAX_AIRCRAFT = 1000
