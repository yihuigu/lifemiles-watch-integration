from unittest.mock import patch

import aiohttp
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lifemiles_watch.const import CONF_API_TOKEN, DOMAIN

from .conftest import BASE, TOKEN, calls, mock_watcher

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
    assert result["data"] == {**USER, CONF_API_TOKEN: None}               # no token: read-only
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


async def test_a_token_is_checked_and_stored(hass, aioclient_mock, status):
    mock_watcher(aioclient_mock, status)
    result = await start(hass)
    with patch("custom_components.lifemiles_watch.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {**USER, CONF_API_TOKEN: f"  {TOKEN} "})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_API_TOKEN] == TOKEN                              # trimmed
    assert calls(aioclient_mock, "GET")[-1] == ("/auth", None, f"Bearer {TOKEN}")


async def test_a_wrong_token_is_rejected_and_the_form_keeps_the_address(hass, aioclient_mock, status):
    mock_watcher(aioclient_mock, status)
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{BASE}/status.json", json=status)
    aioclient_mock.get(f"{BASE}/auth", status=401, json={"error": "missing or wrong token"})
    result = await start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {**USER, CONF_API_TOKEN: "nope"})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert result["data_schema"]({CONF_HOST: "10.0.0.5", CONF_PORT: 8099})[CONF_HOST] == "10.0.0.5"


async def test_a_token_for_a_read_only_watcher_is_explained(hass, aioclient_mock, status):
    aioclient_mock.get(f"{BASE}/status.json", json=status)
    aioclient_mock.get(f"{BASE}/auth", status=403, json={"error": "read-only"})
    result = await start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {**USER, CONF_API_TOKEN: TOKEN})
    assert result["errors"] == {"base": "read_only"}


async def test_an_old_watcher_without_the_auth_endpoint(hass, aioclient_mock, status):
    aioclient_mock.get(f"{BASE}/status.json", json=status)
    aioclient_mock.get(f"{BASE}/auth", status=404, text="not found")
    result = await start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {**USER, CONF_API_TOKEN: TOKEN})
    assert result["errors"] == {"base": "watcher_outdated"}


async def test_reconfigure_adds_the_token_to_an_existing_entry(hass, aioclient_mock, status):
    mock_watcher(aioclient_mock, status)
    entry = MockConfigEntry(domain=DOMAIN, data={**USER, CONF_API_TOKEN: None}, unique_id="10.0.0.5:8099")
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "reconfigure"
    with patch("custom_components.lifemiles_watch.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {**USER, CONF_API_TOKEN: TOKEN})
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_API_TOKEN] == TOKEN


async def test_reconfigure_with_a_wrong_token_changes_nothing(hass, aioclient_mock, status):
    aioclient_mock.get(f"{BASE}/status.json", json=status)
    aioclient_mock.get(f"{BASE}/auth", status=401, json={"error": "wrong"})
    entry = MockConfigEntry(domain=DOMAIN, data={**USER, CONF_API_TOKEN: None}, unique_id="10.0.0.5:8099")
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {**USER, CONF_API_TOKEN: "bad"})
    assert result["errors"] == {"base": "invalid_auth"}
    assert entry.data[CONF_API_TOKEN] is None


async def test_reconfigure_can_point_at_a_new_address(hass, aioclient_mock, status):
    aioclient_mock.get("http://10.0.0.9:8099/status.json", json=status)
    entry = MockConfigEntry(domain=DOMAIN, data={**USER, CONF_API_TOKEN: None}, unique_id="10.0.0.5:8099")
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    with patch("custom_components.lifemiles_watch.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: "10.0.0.9", CONF_PORT: 8099})
        await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"
    assert (entry.data[CONF_HOST], entry.unique_id) == ("10.0.0.9", "10.0.0.9:8099")
