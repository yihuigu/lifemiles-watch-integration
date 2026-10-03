from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lifemiles_watch.const import CONF_API_TOKEN, DOMAIN

from .conftest import BASE, HOST, PORT, TOKEN, WATCHES, calls, mock_watcher, view

NEW = {"name": "Tokyo", "from": ["SYD"], "to": ["HND", "HKG"], "start": "2027-05-10", "end": "2027-05-20"}


async def setup_entry(hass, aioclient_mock, status, token=TOKEN, **view_kw):
    mock_watcher(aioclient_mock, status, **view_kw)
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: HOST, CONF_PORT: PORT, CONF_API_TOKEN: token},
                            unique_id=f"{HOST}:{PORT}")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def open_menu(hass, entry):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU, result
    return result


async def choose(hass, result, step):
    return await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": step})


async def submit(hass, result, data):
    return await hass.config_entries.options.async_configure(result["flow_id"], data)


# ---- the menu ----

async def test_menu_offers_what_makes_sense(hass, aioclient_mock, status):
    entry = await setup_entry(hass, aioclient_mock, status)
    assert (await open_menu(hass, entry))["menu_options"] == ["add", "edit", "remove"]       # defaults: no reset

    aioclient_mock.clear_requests()
    mock_watcher(aioclient_mock, status, source="home-assistant")
    assert (await open_menu(hass, entry))["menu_options"] == ["add", "edit", "remove", "reset"]

    aioclient_mock.clear_requests()
    mock_watcher(aioclient_mock, status, watches=[])
    assert (await open_menu(hass, entry))["menu_options"] == ["add"]                          # nothing to edit


async def test_the_menu_is_read_from_the_watcher_every_time(hass, aioclient_mock, status):
    entry = await setup_entry(hass, aioclient_mock, status)
    before = len(calls(aioclient_mock, "GET"))
    await open_menu(hass, entry)
    await open_menu(hass, entry)
    assert len(calls(aioclient_mock, "GET")) >= before + 2


# ---- add ----

async def test_add_a_route(hass, aioclient_mock, status):
    entry = await setup_entry(hass, aioclient_mock, status)
    result = await choose(hass, await open_menu(hass, entry), "add")
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "add"
    polls = len(calls(aioclient_mock, "GET"))
    result = await submit(hass, result, NEW)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    [(path, body, auth)] = calls(aioclient_mock, "PUT")
    assert (path, auth) == ("/config", f"Bearer {TOKEN}")
    assert body == {"watches": [*WATCHES, NEW]}                  # the existing routes are kept, the new one appended
    assert len(calls(aioclient_mock, "GET")) > polls              # the sensor refreshed straight away


async def test_add_a_route_with_its_return_direction(hass, aioclient_mock, status):
    entry = await setup_entry(hass, aioclient_mock, status)
    result = await choose(hass, await open_menu(hass, entry), "add")
    result = await submit(hass, result, {**NEW, "return_start": "2027-05-17", "return_end": "2027-05-30"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    [(_, body, _)] = calls(aioclient_mock, "PUT")
    out, back = body["watches"][-2:]
    assert out == NEW
    assert back == {"name": "Back: Tokyo", "from": ["HND", "HKG"], "to": ["SYD"], "start": "2027-05-17", "end": "2027-05-30"}


async def test_half_a_return_range_is_an_error_and_nothing_is_sent(hass, aioclient_mock, status):
    entry = await setup_entry(hass, aioclient_mock, status)
    result = await choose(hass, await open_menu(hass, entry), "add")
    result = await submit(hass, result, {**NEW, "return_start": "2027-05-17"})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "return_dates"}
    assert calls(aioclient_mock, "PUT") == []


async def test_a_route_the_watcher_rejects_shows_why_and_can_be_fixed(hass, aioclient_mock, status):
    entry = await setup_entry(hass, aioclient_mock, status)
    aioclient_mock.clear_requests()
    mock_watcher(aioclient_mock, status, put=(400, {
        "error": "invalid watch list",
        "errors": ["watches[2]: end is before start", "watches[2].to: 'X' is not a 3-letter airport code"]}))
    result = await choose(hass, await open_menu(hass, entry), "add")
    result = await submit(hass, result, {**NEW, "end": "2027-05-01"})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_watches"}
    assert "end is before start" in result["description_placeholders"]["details"]
    assert "3-letter airport code" in result["description_placeholders"]["details"]

    aioclient_mock.clear_requests()                              # the user fixes it and resubmits
    mock_watcher(aioclient_mock, status)
    result = await submit(hass, result, NEW)
    assert result["type"] is FlowResultType.CREATE_ENTRY


# ---- edit ----

async def test_edit_a_route(hass, aioclient_mock, status):
    entry = await setup_entry(hass, aioclient_mock, status)
    result = await choose(hass, await open_menu(hass, entry), "edit")
    assert result["step_id"] == "edit"
    result = await submit(hass, result, {"block": "1"})
    assert result["step_id"] == "edit_block"
    defaults = result["data_schema"]({"from": ["PVG"], "to": ["SYD"], "start": "2027-05-17", "end": "2027-05-30"})
    assert defaults["from"] == ["PVG"]
    changed = {"name": "Back", "from": ["PVG", "HGH", "HKG"], "to": ["SYD"], "start": "2027-05-18", "end": "2027-05-31"}
    result = await submit(hass, result, changed)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    [(_, body, _)] = calls(aioclient_mock, "PUT")
    assert body["watches"] == [WATCHES[0], changed]              # only the chosen block changed


# ---- remove / reset ----

async def test_remove_routes(hass, aioclient_mock, status):
    entry = await setup_entry(hass, aioclient_mock, status)
    result = await choose(hass, await open_menu(hass, entry), "remove")
    result = await submit(hass, result, {"blocks": ["0"]})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert calls(aioclient_mock, "PUT")[0][1] == {"watches": [WATCHES[1]]}


async def test_removing_every_route_is_allowed(hass, aioclient_mock, status):
    entry = await setup_entry(hass, aioclient_mock, status)
    result = await choose(hass, await open_menu(hass, entry), "remove")
    await submit(hass, result, {"blocks": ["0", "1"]})
    assert calls(aioclient_mock, "PUT")[0][1] == {"watches": []}


async def test_reset_needs_confirmation(hass, aioclient_mock, status):
    entry = await setup_entry(hass, aioclient_mock, status, source="home-assistant")
    result = await choose(hass, await open_menu(hass, entry), "reset")
    result = await submit(hass, result, {"confirm": False})
    assert result["type"] is FlowResultType.MENU                 # back to the menu, nothing deleted
    assert calls(aioclient_mock, "DELETE") == []

    result = await choose(hass, result, "reset")
    result = await submit(hass, result, {"confirm": True})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert calls(aioclient_mock, "DELETE") == [("/config", None, f"Bearer {TOKEN}")]


# ---- when editing is not possible ----

async def test_no_token_means_no_editing(hass, aioclient_mock, status):
    entry = await setup_entry(hass, aioclient_mock, status, token=None)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert (result["type"], result["reason"]) == (FlowResultType.ABORT, "no_token")


async def test_a_read_only_watcher_cannot_be_edited(hass, aioclient_mock, status):
    entry = await setup_entry(hass, aioclient_mock, status, editable=False)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["reason"] == "watcher_read_only"


async def test_an_unreachable_watcher(hass, aioclient_mock, status):
    entry = await setup_entry(hass, aioclient_mock, status)
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{BASE}/config", status=500)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["reason"] == "cannot_connect"


async def test_an_old_watcher_without_the_config_endpoint(hass, aioclient_mock, status):
    entry = await setup_entry(hass, aioclient_mock, status)
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{BASE}/config", status=404, text="not found")
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["reason"] == "watcher_outdated"


async def test_a_token_that_stopped_working_aborts_with_advice(hass, aioclient_mock, status):
    entry = await setup_entry(hass, aioclient_mock, status)
    result = await choose(hass, await open_menu(hass, entry), "add")
    aioclient_mock.clear_requests()
    aioclient_mock.put(f"{BASE}/config", status=401, json={"error": "wrong"})
    result = await submit(hass, result, NEW)
    assert (result["type"], result["reason"]) == (FlowResultType.ABORT, "invalid_auth")


async def test_the_watcher_losing_its_token_aborts(hass, aioclient_mock, status):
    entry = await setup_entry(hass, aioclient_mock, status)
    result = await choose(hass, await open_menu(hass, entry), "remove")
    aioclient_mock.clear_requests()
    aioclient_mock.put(f"{BASE}/config", status=403, json={"error": "read-only"})
    result = await submit(hass, result, {"blocks": ["0"]})
    assert result["reason"] == "watcher_read_only"
