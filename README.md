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

## Editing the watched routes

With the watcher's token you can change what it searches without touching its config files:
**Settings -> Devices & services -> LifeMiles Watch -> Configure**.

- **Add a route**: airports From and To (pick from the list or type any 3-letter code) and a date
  range. Every From airport is searched to every To airport, one way, for each date. Fill the
  optional return dates to also add the opposite direction.
- **Edit a route**, **Remove routes**, or **Reset** to the watcher's own defaults.
- Changes apply at the watcher's next daily batch, and the route list shown on the card updates at
  once. The watcher rejects anything that would be too much traffic for your LifeMiles account
  (at most 20 route blocks, 120 days per block, 400 searches in total) and tells you why.

It needs the watcher's `WATCH_API_TOKEN`: enter it when you add the integration, or later with
**Reconfigure**. Without a token the integration only reads, and **Configure** says so. The token is
sent to the watcher as a bearer token over plain HTTP on your network, so keep the watcher on a
network you trust.

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
config               {pax, min_seats, max_miles_pp, interval_hours, source, editable,
                      watches: [{name, from: [...], to: [...], start, end}]}
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
