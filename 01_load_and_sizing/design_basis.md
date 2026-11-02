# Critical Load Classification — Design Basis

Companion to `critical_load_list.csv`. Team 1 (Fedor, Nam) own this,
but the `tier` column needs sign-off from all six.

## Design basis

Supply the Tier 1 load for **24 hours with no grid supply**, starting at dusk on the
lowest-irradiance day of the year. The battery carries the full night before any solar returns.

## Tier definitions

| Tier | Meaning | Sizing consequence |
|---|---|---|
| 1 | Runs through the full 24 h | Battery is sized against this |
| 2 | Must happen, timing flexible — scheduled into the solar window | Served by PV; minimal battery impact |
| 3 | Off for the duration | Excluded from sizing |

## Column meanings

- `runs_when` — `continuous_24h`, `night_only`, `daylight_only`, `on_demand`, `off`
- `window_hours` — hours the load is available to run, derived from `runs_when`
- `duty_cycle_pct` — fraction of the **window**, not of the day.
  Energy = rated_power_W x quantity x duty_cycle_pct/100 x window_hours
- `source_type` — `datasheet` (published spec, cited) or `ESTIMATE-verify` (engineering
  estimate, must be replaced with a cited figure before submission)

## What the current numbers give

Tier 1 total is roughly **82 kWh/day**, peak connected Tier 1 about **6.7 kW**.

| Building | kWh/day |
|---|---|
| Telecom tower | 47.3 |
| Health clinic | 20.1 |
| Fire station | 11.4 |
| Water pump | 2.9 |

**The telecom tower is 58% of the entire load** and TT01 alone is 46%. That single
assumption — 1.5 kW of DC site loading — moves the battery size more than everything
else combined. Verify it before anything else.

## Sourced vs estimated

Four rows carry published datasheet figures: HC01, HC02, HC05, WP02. Everything else
is an engineering estimate flagged `ESTIMATE-verify` and needs a real citation.

Estimates are sequenced deliberately — the highest-energy rows matter most:
TT01, TT02, HC04, FS02, HC03. Rows tiered 3 barely matter, since they are excluded
from sizing entirely.

## Open decisions

**WP02 — main pump motor.** Provisionally Tier 2, scheduled into daylight. Assumes
reservoir or tank storage covers 24 h of town demand — normal water-utility practice,
but it must be stated as an assumption. Tier 1 instead makes the battery very large.
Excluding pumping entirely is worse: water demand rises during a bushfire, so a design
where the fire station and the water supply both go dark is exactly the failure the
project claims to prevent.

**HC06 — clinic cooling.** Marked CONTESTED. On a 40 C fire day, medication ambient
limits make a case for Tier 1 at reduced capacity. Needs an explicit decision.

## Notes carried forward

- **FS01 roller doors** size the inverter, not the battery — 0.36 kWh/day but 1.5 kW instantaneous.
- **WP02** is DOL started, so starting current is roughly 6x full-load. This is an inverter
  and protection constraint, not an energy one.
- **FS09 vehicle fast charging** is shed deliberately. At 7.4 kW it would dominate the battery.
- **TT03 tower obstruction lighting** is an aviation safety requirement, not a comfort load.

## Freeze

Once signed off, this list is frozen. Changes after the Week 5 integration checkpoint force
re-sizing (Team 1) and re-modelling (Team 2), so late changes need group agreement.
