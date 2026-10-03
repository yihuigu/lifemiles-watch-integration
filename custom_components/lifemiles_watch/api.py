"""Fetching and checking the watcher's /status.json."""
from __future__ import annotations

from typing import Any

import aiohttp

from .const import REQUEST_TIMEOUT


class CannotConnect(Exception):
    """The watcher did not answer."""


class InvalidResponse(Exception):
    """The address answered, but not with a LifeMiles watcher status document."""


def status_url(host: str, port: int) -> str:
    host = f"[{host}]" if ":" in host and not host.startswith("[") else host   # IPv6 literal
    return f"http://{host}:{port}/status.json"


def validate(data: Any) -> dict[str, Any]:
    """The document must look like the watcher's: a count plus the three lists."""
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("count"), int)
        or not all(isinstance(data.get(k), list) for k in ("runs", "current", "history"))
    ):
        raise InvalidResponse("not a LifeMiles watcher status document")
    return data


async def fetch_status(session: aiohttp.ClientSession, host: str, port: int) -> dict[str, Any]:
    try:
        async with session.get(
            status_url(host, port), timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        ) as resp:
            if resp.status != 200:
                raise CannotConnect(f"HTTP {resp.status}")
            data = await resp.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError) as err:
        raise CannotConnect(str(err)) from err
    except ValueError as err:                     # the body was not JSON
        raise InvalidResponse(str(err)) from err
    return validate(data)
