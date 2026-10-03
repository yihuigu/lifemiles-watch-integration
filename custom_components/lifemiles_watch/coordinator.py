"""Polls the watcher's status document."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CannotConnect, InvalidResponse, fetch_status
from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class LifemilesCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """One poll of /status.json every few minutes; all entities share it."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=entry, update_interval=SCAN_INTERVAL)
        self._session = async_get_clientsession(hass)
        self.host: str = entry.data[CONF_HOST]
        self.port: int = entry.data[CONF_PORT]

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await fetch_status(self._session, self.host, self.port)
        except (CannotConnect, InvalidResponse) as err:
            raise UpdateFailed(f"LifeMiles watcher at {self.host}:{self.port}: {err}") from err


type LifemilesConfigEntry = ConfigEntry[LifemilesCoordinator]
