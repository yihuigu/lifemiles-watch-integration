from unittest.mock import patch

import aiohttp
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lifemiles_watch.const import DOMAIN

URL = "http://10.0.0.5:8099/status.json"
USER = {CONF_HOST: "10.0.0.5", CONF_PORT: 8099}


async def start(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "user"
    return result


async def test_creates_an_entry_for_a_working_watcher(hass, aioclient_mock, status):
    aioclient_mock.get(URL, json=status)
    result = await start(hass)
    with patch("custom_components.lifemiles_watch.async_setup_entry", return_value=True) as setup:
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER)
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "LifeMiles watch (10.0.0.5)"
    assert result["data"] == USER
    assert result["result"].unique_id == "10.0.0.5:8099"
    assert len(setup.mock_calls) == 1


async def test_unreachable_watcher_then_recovery(hass, aioclient_mock, status):
    aioclient_mock.get(URL, exc=aiohttp.ClientError("nope"))
    result = await start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    aioclient_mock.clear_requests()
    aioclient_mock.get(URL, json=status)
    with patch("custom_components.lifemiles_watch.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_http_error_is_cannot_connect(hass, aioclient_mock):
    aioclient_mock.get(URL, status=500)
    result = await start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER)
    assert result["errors"] == {"base": "cannot_connect"}


async def test_something_that_is_not_a_watcher_is_rejected(hass, aioclient_mock):
    result = await start(hass)
    for kwargs in ({"json": {"hello": "world"}}, {"text": "<html>router login</html>"}, {"json": {"count": "3"}}):
        aioclient_mock.clear_requests()
        aioclient_mock.get(URL, **kwargs)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER)
        assert result["errors"] == {"base": "invalid_response"}, kwargs


async def test_a_pasted_url_is_not_a_host(hass, aioclient_mock):
    result = await start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "http://10.0.0.5:8099/", CONF_PORT: 8099}
    )
    assert result["errors"] == {CONF_HOST: "invalid_host"}
    assert aioclient_mock.call_count == 0                       # rejected before any request


async def test_the_same_watcher_cannot_be_added_twice(hass, aioclient_mock, status):
    aioclient_mock.get(URL, json=status)
    MockConfigEntry(domain=DOMAIN, data=USER, unique_id="10.0.0.5:8099").add_to_hass(hass)
    result = await start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
