"""Status and count entities for SkyWatch Radar."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SkyWatchRadarCoordinator


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator: SkyWatchRadarCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SkyWatchRadarStatus(coordinator), SkyWatchRadarCount(coordinator)])


class _Base(CoordinatorEntity[SkyWatchRadarCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: SkyWatchRadarCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, coordinator.entry.entry_id)}, name="SkyWatch Radar", manufacturer="SkyWatch", model="ADSB.fi radar")


class SkyWatchRadarStatus(_Base):
    _attr_translation_key = "status"

    def __init__(self, coordinator: SkyWatchRadarCoordinator) -> None:
        super().__init__(coordinator, "status")

    @property
    def native_value(self) -> str:
        return "online" if self.coordinator.data and self.coordinator.data["status"]["online"] else "degraded"

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        return {**data.get("status", {}), "aircraft_count": len(data.get("aircraft", [])), "center": data.get("center", {})}


class SkyWatchRadarCount(_Base):
    _attr_translation_key = "aircraft"
    _attr_native_unit_of_measurement = "aircraft"
    _attr_icon = "mdi:airplane"

    def __init__(self, coordinator: SkyWatchRadarCoordinator) -> None:
        super().__init__(coordinator, "aircraft")

    @property
    def native_value(self) -> int:
        return len((self.coordinator.data or {}).get("aircraft", []))
