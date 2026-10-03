"""LifeMiles Watch: shows the status of a LifeMiles award-space watcher."""
from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import LifemilesConfigEntry, LifemilesCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: LifemilesConfigEntry) -> bool:
    coordinator = LifemilesCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()     # raises ConfigEntryNotReady if unreachable
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LifemilesConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
