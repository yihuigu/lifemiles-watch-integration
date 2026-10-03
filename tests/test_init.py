from datetime import timedelta

import aiohttp
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.lifemiles_watch.const import DOMAIN, SCAN_INTERVAL

URL = "http://10.0.0.5:8099/status.json"
MAIN = "sensor.lifemiles_watch"


async def setup_entry(hass, aioclient_mock, payload):
    aioclient_mock.get(URL, json=payload)
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "10.0.0.5", CONF_PORT: 8099}, unique_id="10.0.0.5:8099")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_entities_show_the_watcher_status(hass, aioclient_mock, status):
    entry = await setup_entry(hass, aioclient_mock, status)
    assert entry.state is ConfigEntryState.LOADED

    main = hass.states.get(MAIN)
    assert main.state == str(status["count"]) == "2"
    assert main.attributes["unit_of_measurement"] == "awards"
    assert main.attributes["friendly_name"] == "LifeMiles watch"
    # exactly what the dashboard card reads
    for key in ("last_run", "next_run", "config", "runs", "current", "history"):
        assert main.attributes[key] == status[key], key
    assert main.attributes["current"][0]["seats"] in (1, 2)

    assert hass.states.get("binary_sensor.lifemiles_watch_award_available").state == STATE_ON
    assert hass.states.get("sensor.lifemiles_watch_last_run").state.startswith(status["last_run"][:16])
    assert hass.states.get("sensor.lifemiles_watch_next_run").state.startswith(status["next_run"][:16])
    assert hass.states.get("sensor.lifemiles_watch_last_run").attributes["device_class"] == "timestamp"


async def test_nothing_available(hass, aioclient_mock, status):
    status.update(count=0, current=[])
    await setup_entry(hass, aioclient_mock, status)
    assert hass.states.get(MAIN).state == "0"
    assert hass.states.get("binary_sensor.lifemiles_watch_award_available").state == STATE_OFF


async def test_a_single_award_counts_as_available(hass, aioclient_mock, status):
    status.update(count=1, current=status["current"][:1])
    await setup_entry(hass, aioclient_mock, status)
    assert hass.states.get(MAIN).state == "1"
    assert hass.states.get("binary_sensor.lifemiles_watch_award_available").state == STATE_ON


async def test_next_run_is_unknown_while_a_batch_is_running(hass, aioclient_mock, status):
    status["next_run"] = None
    await setup_entry(hass, aioclient_mock, status)
    assert hass.states.get("sensor.lifemiles_watch_next_run").state == STATE_UNKNOWN
    assert hass.states.get(MAIN).attributes["next_run"] is None


async def test_one_device_with_stable_unique_ids(hass, aioclient_mock, status):
    entry = await setup_entry(hass, aioclient_mock, status)
    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert [d.name for d in devices] == ["LifeMiles watch"]
    ids = {e.unique_id for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)}
    assert ids == {f"{entry.entry_id}_{k}" for k in ("awards", "last_run", "next_run", "available")}


async def test_unreachable_watcher_retries_setup(hass, aioclient_mock):
    aioclient_mock.get(URL, exc=aiohttp.ClientError("down"))
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "10.0.0.5", CONF_PORT: 8099}, unique_id="10.0.0.5:8099")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_outage_and_recovery(hass, aioclient_mock, status, freezer):
    await setup_entry(hass, aioclient_mock, status)
    assert hass.states.get(MAIN).state == "2"

    aioclient_mock.clear_requests()
    aioclient_mock.get(URL, exc=aiohttp.ClientError("down"))
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(MAIN).state == STATE_UNAVAILABLE

    status.update(count=1, current=status["current"][:1])
    aioclient_mock.clear_requests()
    aioclient_mock.get(URL, json=status)
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(MAIN).state == "1"
    assert len(hass.states.get(MAIN).attributes["current"]) == 1
    assert hass.states.get("binary_sensor.lifemiles_watch_award_available").state == STATE_ON


async def test_unload(hass, aioclient_mock, status):
    entry = await setup_entry(hass, aioclient_mock, status)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get(MAIN).state == STATE_UNAVAILABLE
