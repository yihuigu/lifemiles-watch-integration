"""On while at least one award is available: handy for automations."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import LifemilesConfigEntry, LifemilesCoordinator
from .entity import LifemilesEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: LifemilesConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([LifemilesAvailableSensor(entry.runtime_data)])


class LifemilesAvailableSensor(LifemilesEntity, BinarySensorEntity):
    _attr_name = "Award available"
    _attr_icon = "mdi:airplane-check"

    def __init__(self, coordinator: LifemilesCoordinator) -> None:
        super().__init__(coordinator, "available")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data["count"] > 0
