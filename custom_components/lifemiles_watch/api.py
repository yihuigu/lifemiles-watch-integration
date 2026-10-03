"""Talking to the watcher: its status document and its route-list endpoints."""
from __future__ import annotations

from typing import Any

import aiohttp

from .const import REQUEST_TIMEOUT


class CannotConnect(Exception):
    """The watcher did not answer."""


class InvalidResponse(Exception):
    """The address answered, but not with a LifeMiles watcher status document."""


class InvalidAuth(Exception):
    """The watcher rejected the token (HTTP 401)."""


class ReadOnly(Exception):
    """The watcher has no token set, so it cannot be edited (HTTP 403)."""


class Unsupported(Exception):
    """An older watcher without the route-list endpoints (HTTP 404)."""


class InvalidConfig(Exception):
    """The watcher refused the route list; `errors` says why."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


def base_url(host: str, port: int) -> str:
    host = f"[{host}]" if ":" in host and not host.startswith("[") else host   # IPv6 literal
    return f"http://{host}:{port}"


def status_url(host: str, port: int) -> str:
    return f"{base_url(host, port)}/status.json"


def validate(data: Any) -> dict[str, Any]:
    """The document must look like the watcher's: a count plus the three lists."""
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("count"), int)
        or not all(isinstance(data.get(k), list) for k in ("runs", "current", "history"))
    ):
        raise InvalidResponse("not a LifeMiles watcher status document")
    return data


async def _call(
    session: aiohttp.ClientSession, method: str, host: str, port: int, path: str,
    token: str | None = None, body: Any = None,
) -> Any:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        async with session.request(
            method, f"{base_url(host, port)}{path}", json=body, headers=headers,
            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
        ) as resp:
            try:
                data = await resp.json(content_type=None)
            except ValueError:
                data = None
            status = resp.status
    except (aiohttp.ClientError, TimeoutError) as err:
        raise CannotConnect(str(err)) from err
    if status == 200:
        return data
    if status == 400 and isinstance(data, dict):
        raise InvalidConfig(data.get("errors") or [data.get("error", "rejected")])
    if status == 401:
        raise InvalidAuth("wrong token")
    if status == 403:
        raise ReadOnly("the watcher has no token set")
    if status == 404:
        raise Unsupported("the watcher does not support editing routes")
    raise CannotConnect(f"HTTP {status}")


async def fetch_status(session: aiohttp.ClientSession, host: str, port: int) -> dict[str, Any]:
    try:
        return validate(await _call(session, "GET", host, port, "/status.json"))
    except Unsupported as err:                       # /status.json missing: not a watcher at all
        raise CannotConnect("no status document at that address") from err


async def get_config(session: aiohttp.ClientSession, host: str, port: int) -> dict[str, Any]:
    """{"source", "editable", "watches": [...], "combos", "limits"}"""
    data = await _call(session, "GET", host, port, "/config")
    if not isinstance(data, dict) or not isinstance(data.get("watches"), list):
        raise InvalidResponse("unexpected /config document")
    return data


async def check_token(session: aiohttp.ClientSession, host: str, port: int, token: str) -> None:
    await _call(session, "GET", host, port, "/auth", token=token)


async def put_config(
    session: aiohttp.ClientSession, host: str, port: int, token: str, watches: list[dict[str, Any]]
) -> dict[str, Any]:
    return await _call(session, "PUT", host, port, "/config", token=token, body={"watches": watches})


async def delete_config(session: aiohttp.ClientSession, host: str, port: int, token: str) -> dict[str, Any]:
    return await _call(session, "DELETE", host, port, "/config", token=token)
