"""The main sensor (awards available now, plus everything the card shows) and two timestamps."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import ATTRIBUTES
from .coordinator import LifemilesConfigEntry, LifemilesCoordinator
from .entity import LifemilesEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: LifemilesConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            LifemilesAwardsSensor(coordinator),
            LifemilesTimeSensor(coordinator, "last_run", "Last run"),
            LifemilesTimeSensor(coordinator, "next_run", "Next run"),
        ]
    )


class LifemilesAwardsSensor(LifemilesEntity, SensorEntity):
    """State = awards available now. The attributes are what the dashboard card draws."""

    _attr_name = None                                   # entity id: sensor.lifemiles_watch
    _attr_icon = "mdi:airplane-search"
    _attr_native_unit_of_measurement = "awards"
    # large and rewritten on every run: live in the state machine, but not worth the database
    _unrecorded_attributes = frozenset({"config", "runs", "current", "history"})

    def __init__(self, coordinator: LifemilesCoordinator) -> None:
        super().__init__(coordinator, "awards")

    @property
    def native_value(self) -> int:
        return self.coordinator.data["count"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {key: self.coordinator.data.get(key) for key in ATTRIBUTES}


class LifemilesTimeSensor(LifemilesEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: LifemilesCoordinator, key: str, name: str) -> None:
        super().__init__(coordinator, key)
        self._key = key
        self._attr_name = name

    @property
    def native_value(self) -> datetime | None:
        value = self.coordinator.data.get(self._key)
        return dt_util.parse_datetime(value) if value else None      # next_run is null mid-run
