"""Set-up dialog (address and optional token) and the Configure dialog for the watched routes."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    DateSelector,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    CannotConnect,
    InvalidAuth,
    InvalidConfig,
    InvalidResponse,
    ReadOnly,
    Unsupported,
    check_token,
    delete_config,
    fetch_status,
    get_config,
    put_config,
)
from .const import AIRPORTS, CONF_API_TOKEN, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

TOKEN_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


async def _check(hass, host: str, port: int, token: str | None) -> str | None:
    """None when the watcher answers (and accepts the token, if one was given); else an error key."""
    session = async_get_clientsession(hass)
    try:
        await fetch_status(session, host, port)
        if token:
            await check_token(session, host, port, token)
    except CannotConnect:
        return "cannot_connect"
    except InvalidResponse:
        return "invalid_response"
    except InvalidAuth:
        return "invalid_auth"
    except ReadOnly:
        return "read_only"
    except Unsupported:
        return "watcher_outdated"
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Unexpected error while checking the watcher")
        return "unknown"
    return None


def _connection_schema(host: str = "", port: int = DEFAULT_PORT, token: str = "") -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=host): str,
            vol.Required(CONF_PORT, default=port): cv.port,
            vol.Optional(CONF_API_TOKEN, default=token): TOKEN_SELECTOR,
        }
    )


class LifemilesConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> LifemilesOptionsFlow:
        return LifemilesOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host, port = user_input[CONF_HOST].strip(), user_input[CONF_PORT]
            token = (user_input.get(CONF_API_TOKEN) or "").strip()
            if not host or "/" in host or "://" in host:
                errors[CONF_HOST] = "invalid_host"
            else:
                await self.async_set_unique_id(f"{host}:{port}")
                self._abort_if_unique_id_configured()
                if error := await _check(self.hass, host, port, token):
                    errors["base"] = error
                else:
                    return self.async_create_entry(
                        title=f"LifeMiles watch ({host})",
                        data={CONF_HOST: host, CONF_PORT: port, CONF_API_TOKEN: token or None},
                    )
        u = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=_connection_schema(u.get(CONF_HOST, ""), u.get(CONF_PORT, DEFAULT_PORT), u.get(CONF_API_TOKEN, "")),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Change the address, or add the token that switches route editing on."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host, port = user_input[CONF_HOST].strip(), user_input[CONF_PORT]
            token = (user_input.get(CONF_API_TOKEN) or "").strip()
            if not host or "/" in host or "://" in host:
                errors[CONF_HOST] = "invalid_host"
            elif error := await _check(self.hass, host, port, token):
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=f"{host}:{port}",
                    title=f"LifeMiles watch ({host})",
                    data={CONF_HOST: host, CONF_PORT: port, CONF_API_TOKEN: token or None},
                )
        d = user_input or entry.data
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_connection_schema(d.get(CONF_HOST, ""), d.get(CONF_PORT, DEFAULT_PORT), d.get(CONF_API_TOKEN) or ""),
            errors=errors,
        )


def _airports() -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=[SelectOptionDict(value=c, label=f"{n} ({c})") for c, n in AIRPORTS.items()],
            multiple=True,
            custom_value=True,
            sort=True,
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def _describe(w: dict[str, Any]) -> str:
    where = f"{', '.join(w['from'])} → {', '.join(w['to'])}"
    return f"{w['name']}: {where} ({w['start']} – {w['end']})" if w.get("name") else f"{where} ({w['start']} – {w['end']})"


def _block_schema(d: dict[str, Any] | None = None, adding: bool = False) -> vol.Schema:
    """The form for one route block; `d` prefills it when editing."""
    d = d or {}
    fields: dict[Any, Any] = {
        vol.Optional("name", description={"suggested_value": d.get("name", "")}): TextSelector(),
        vol.Required("from", default=d.get("from", [])): _airports(),
        vol.Required("to", default=d.get("to", [])): _airports(),
    }
    fields[vol.Required("start", **({"default": d["start"]} if d.get("start") else {}))] = DateSelector()
    fields[vol.Required("end", **({"default": d["end"]} if d.get("end") else {}))] = DateSelector()
    if adding:                                      # optional: also search the way back
        fields[vol.Optional("return_start")] = DateSelector()
        fields[vol.Optional("return_end")] = DateSelector()
    return vol.Schema(fields)


def _block(user_input: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": (user_input.get("name") or "").strip(),
        "from": list(user_input["from"]),
        "to": list(user_input["to"]),
        "start": user_input["start"],
        "end": user_input["end"],
    }


class LifemilesOptionsFlow(OptionsFlow):
    """Add, edit, remove or reset the routes. The watcher holds the list; this only edits it."""

    def __init__(self) -> None:
        self._watches: list[dict[str, Any]] = []
        self._source = ""
        self._index = 0

    @property
    def _conn(self) -> tuple[str, int, str | None]:
        d = self.config_entry.data
        return d[CONF_HOST], d[CONF_PORT], d.get(CONF_API_TOKEN) or None

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        host, port, token = self._conn
        try:
            view = await get_config(async_get_clientsession(self.hass), host, port)
        except Unsupported:
            return self.async_abort(reason="watcher_outdated")
        except (CannotConnect, InvalidResponse):
            return self.async_abort(reason="cannot_connect")
        if not token:
            return self.async_abort(reason="no_token")
        if not view.get("editable"):
            return self.async_abort(reason="watcher_read_only")
        self._watches, self._source = view["watches"], view.get("source", "")
        menu = ["add"]
        if self._watches:
            menu += ["edit", "remove"]
        if self._source == "home-assistant":
            menu.append("reset")
        return self.async_show_menu(step_id="init", menu_options=menu)

    # -- saving --

    async def _save(self, watches: list[dict[str, Any]]) -> tuple[ConfigFlowResult | None, str, str]:
        """(abort result | None, form error key | '', details). One of the first two is set on failure."""
        host, port, token = self._conn
        try:
            await put_config(async_get_clientsession(self.hass), host, port, token, watches)
        except InvalidConfig as err:
            return None, "invalid_watches", "; ".join(err.errors)
        except InvalidAuth:
            return self.async_abort(reason="invalid_auth"), "", ""
        except ReadOnly:
            return self.async_abort(reason="watcher_read_only"), "", ""
        except (CannotConnect, Unsupported):
            return self.async_abort(reason="cannot_connect"), "", ""
        return None, "", ""

    async def _done(self) -> ConfigFlowResult:
        coordinator = getattr(self.config_entry, "runtime_data", None)
        if coordinator is not None:
            await coordinator.async_request_refresh()           # the card shows the change at once
        return self.async_create_entry(data=dict(self.config_entry.options))

    # -- add --

    async def async_step_add(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        details = ""
        if user_input is not None:
            new = [*self._watches, _block(user_input)]
            ret_start, ret_end = user_input.get("return_start"), user_input.get("return_end")
            if bool(ret_start) != bool(ret_end):
                errors["base"] = "return_dates"
            else:
                if ret_start:
                    name = (user_input.get("name") or "").strip()
                    new.append({"name": f"Back: {name}" if name else "", "from": list(user_input["to"]),
                                "to": list(user_input["from"]), "start": ret_start, "end": ret_end})
                aborted, key, details = await self._save(new)
                if aborted:
                    return aborted
                if key:
                    errors["base"] = key
                else:
                    return await self._done()
        return self.async_show_form(
            step_id="add",
            data_schema=self.add_suggested_values_to_schema(_block_schema(adding=True), user_input or {}),
            errors=errors,
            description_placeholders={"details": details},
        )

    # -- edit --

    def _picker(self, multiple: bool) -> SelectSelector:
        return SelectSelector(
            SelectSelectorConfig(
                options=[SelectOptionDict(value=str(i), label=_describe(w)) for i, w in enumerate(self._watches)],
                multiple=multiple,
                mode=SelectSelectorMode.LIST,
            )
        )

    async def async_step_edit(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._index = int(user_input["block"])
            return await self.async_step_edit_block()
        return self.async_show_form(step_id="edit", data_schema=vol.Schema({vol.Required("block"): self._picker(False)}))

    async def async_step_edit_block(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        details = ""
        if user_input is not None:
            new = list(self._watches)
            new[self._index] = _block(user_input)
            aborted, key, details = await self._save(new)
            if aborted:
                return aborted
            if key:
                errors["base"] = key
            else:
                return await self._done()
        return self.async_show_form(
            step_id="edit_block",
            data_schema=_block_schema(user_input or self._watches[self._index]),
            errors=errors,
            description_placeholders={"details": details},
        )

    # -- remove / reset --

    async def async_step_remove(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            drop = {int(i) for i in user_input["blocks"]}
            aborted, _, _ = await self._save([w for i, w in enumerate(self._watches) if i not in drop])
            return aborted or await self._done()
        return self.async_show_form(step_id="remove", data_schema=vol.Schema({vol.Required("blocks"): self._picker(True)}))

    async def async_step_reset(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            if not user_input["confirm"]:
                return await self.async_step_init()
            host, port, token = self._conn
            try:
                await delete_config(async_get_clientsession(self.hass), host, port, token)
            except InvalidAuth:
                return self.async_abort(reason="invalid_auth")
            except ReadOnly:
                return self.async_abort(reason="watcher_read_only")
            except (CannotConnect, Unsupported):
                return self.async_abort(reason="cannot_connect")
            return await self._done()
        return self.async_show_form(
            step_id="reset", data_schema=vol.Schema({vol.Required("confirm", default=False): BooleanSelector()})
        )
