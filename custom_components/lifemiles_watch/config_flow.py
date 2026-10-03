"""Set-up dialog: the watcher's address, checked before anything is created."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CannotConnect, InvalidResponse, fetch_status
from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class LifemilesConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input[CONF_PORT]
            if not host or "/" in host or "://" in host:
                errors[CONF_HOST] = "invalid_host"
            else:
                await self.async_set_unique_id(f"{host}:{port}")
                self._abort_if_unique_id_configured()
                try:
                    await fetch_status(async_get_clientsession(self.hass), host, port)
                except CannotConnect:
                    errors["base"] = "cannot_connect"
                except InvalidResponse:
                    errors["base"] = "invalid_response"
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Unexpected error while checking the watcher")
                    errors["base"] = "unknown"
                else:
                    return self.async_create_entry(
                        title=f"LifeMiles watch ({host})", data={CONF_HOST: host, CONF_PORT: port}
                    )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=(user_input or {}).get(CONF_HOST, "")): str,
                    vol.Required(CONF_PORT, default=(user_input or {}).get(CONF_PORT, DEFAULT_PORT)): cv.port,
                }
            ),
            errors=errors,
        )
