import aiohttp
import pytest
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.lifemiles_watch import api

from .conftest import BASE, HOST, PORT, TOKEN, WATCHES, calls, view


async def test_urls_handle_ipv6_literals():
    assert api.status_url("10.0.0.5", 8099) == "http://10.0.0.5:8099/status.json"
    assert api.status_url("fd00::5", 8099) == "http://[fd00::5]:8099/status.json"
    assert api.status_url("[fd00::5]", 8099) == "http://[fd00::5]:8099/status.json"


@pytest.mark.parametrize("status,exc", [(401, api.InvalidAuth), (403, api.ReadOnly), (404, api.Unsupported),
                                        (500, api.CannotConnect), (502, api.CannotConnect)])
async def test_http_statuses_become_exceptions(hass, aioclient_mock, status, exc):
    aioclient_mock.put(f"{BASE}/config", status=status, json={"error": "x"})
    with pytest.raises(exc):
        await api.put_config(async_get_clientsession(hass), HOST, PORT, TOKEN, [])


async def test_a_400_carries_the_watchers_reasons(hass, aioclient_mock):
    aioclient_mock.put(f"{BASE}/config", status=400, json={"error": "invalid watch list", "errors": ["a", "b"]})
    with pytest.raises(api.InvalidConfig) as err:
        await api.put_config(async_get_clientsession(hass), HOST, PORT, TOKEN, [])
    assert err.value.errors == ["a", "b"]
    aioclient_mock.clear_requests()
    aioclient_mock.put(f"{BASE}/config", status=400, json={"error": "body must be JSON"})
    with pytest.raises(api.InvalidConfig) as err:
        await api.put_config(async_get_clientsession(hass), HOST, PORT, TOKEN, [])
    assert err.value.errors == ["body must be JSON"]


async def test_network_errors_are_cannot_connect(hass, aioclient_mock):
    aioclient_mock.get(f"{BASE}/config", exc=aiohttp.ClientError("down"))
    with pytest.raises(api.CannotConnect):
        await api.get_config(async_get_clientsession(hass), HOST, PORT)


async def test_get_config_rejects_other_documents(hass, aioclient_mock):
    for body in ({"hello": 1}, {"watches": "x"}, [1]):
        aioclient_mock.clear_requests()
        aioclient_mock.get(f"{BASE}/config", json=body)
        with pytest.raises(api.InvalidResponse):
            await api.get_config(async_get_clientsession(hass), HOST, PORT)
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{BASE}/config", text="<html>router</html>")
    with pytest.raises(api.InvalidResponse):
        await api.get_config(async_get_clientsession(hass), HOST, PORT)


async def test_the_token_is_sent_as_a_bearer_header_and_only_when_given(hass, aioclient_mock):
    aioclient_mock.get(f"{BASE}/config", json=view())
    aioclient_mock.put(f"{BASE}/config", json=view())
    session = async_get_clientsession(hass)
    await api.get_config(session, HOST, PORT)
    await api.put_config(session, HOST, PORT, TOKEN, WATCHES)
    assert calls(aioclient_mock, "GET")[0][2] is None
    assert calls(aioclient_mock, "PUT") == [("/config", {"watches": WATCHES}, f"Bearer {TOKEN}")]
