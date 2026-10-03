"""Shared base for the integration's entities."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LifemilesCoordinator


class LifemilesEntity(CoordinatorEntity[LifemilesCoordinator]):
    """Entities named after the device: the main one is simply 'LifeMiles watch'."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LifemilesCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="LifeMiles watch",
            manufacturer="LifeMiles Watch",
            model="Award watcher",
            configuration_url=f"http://{coordinator.host}:{coordinator.port}/status.json",
        )
