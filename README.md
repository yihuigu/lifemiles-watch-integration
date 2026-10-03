# LifeMiles Watch (Home Assistant integration)

Connects Home Assistant to a LifeMiles award-space watcher: you add the watcher's address in the
UI and the integration creates the sensors. No YAML, no restart. It is the companion of the
[LifeMiles Watch Card](https://github.com/yihuigu/lifemiles-watch-card) dashboard card, which
draws the main sensor's attributes.

> This repository holds only the integration. It needs the watcher app, which serves its status
> at `http://HOST:8099/status.json`; the watcher itself is not part of this repository.

## Install (custom repository, not the HACS store)

This integration is **not in the HACS default store**: it does not appear when you search HACS.
Add it by hand as a custom repository:

1. HACS -> three dots -> **Custom repositories**.
2. Repository `https://github.com/yihuigu/lifemiles-watch-integration`, category **Integration**.
3. Open **LifeMiles Watch** in HACS, click **Download**, then restart Home Assistant.
4. Settings -> Devices & services -> **Add integration** -> *LifeMiles Watch*, and enter the
   watcher's host and port (default 8099). The address is checked before anything is created.

## What you get

One device, "LifeMiles watch", polled every 5 minutes:

| Entity | Meaning |
|---|---|
| `sensor.lifemiles_watch` | number of awards available right now; its attributes feed the card |
| `binary_sensor.lifemiles_watch_award_available` | on while at least one award is available (for automations) |
| `sensor.lifemiles_watch_last_run` | when the watcher last ran (timestamp) |
| `sensor.lifemiles_watch_next_run` | when it runs next; unknown while a batch is running |

If the watcher cannot be reached the entities become unavailable and recover by themselves.

### Attributes of `sensor.lifemiles_watch`

```text
last_run, next_run   ISO 8601 timestamps (next_run may be null while a run is in progress)
config               {pax, min_seats, max_miles_pp, interval_hours, watches: [...]}
runs                 newest first: {at, ok, secs, attempts, errors, alerts, found, note?}
current              {origin, dest, depart, flights, miles_pp, taxes_usd, seats, first_seen}
history              the same plus gone_at, newest first
```

`config`, `runs`, `current` and `history` are large and change on every run, so they are kept out
of the Home Assistant database (they stay available in the live state for the card).

## Requirements

Home Assistant 2025.1 or newer, and a reachable watcher. The watcher's status is read-only and
holds only flights, miles and run results.

## Development

```bash
pip install -r requirements_test.txt
pytest
```

The tests run the integration inside a real Home Assistant core (setup flow, entities, outage and
recovery, unload).
