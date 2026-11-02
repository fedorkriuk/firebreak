# Protection design — settings and the islanded decision

Team 1 contribution to the week 8–9 protection phase. Settings in `relay_settings.json`,
curves in `tcc_grid.png` / `tcc_island.png`, numerical check in `tcc_check.txt`.

---

## 1. The problem in one table

| Bus | Grid-connected 3ph | Islanded 3ph | Ratio |
|---|---|---|---|
| Microgrid bus | 6 614 A | 95 A | 70× |
| Fire station | 4 916 A | 95 A | 52× |
| Water pump | 3 909 A | 94 A | 42× |
| Health clinic | 5 281 A | 95 A | 56× |
| Telecom tower | 4 294 A | 94 A | 46× |

Grid-connected, the upstream network pushes kiloamps into a fault. Islanded, the only
sources are inverters, which are current-limited at about 1.2 × rated — 95 A for our
PV + battery combined. Every bus sees roughly the same 94–95 A because the limit is at
the source, not in the cable.

One set of relay settings has to be sensitive enough to see a 95 A fault *and* selective
enough not to trip on 62 A of pump inrush. Those two requirements conflict on the pump
feeder. That conflict is the whole design problem.

---

## 2. Relay scheme

Five numerical overcurrent relays, IEC standard inverse (k = 0.14, α = 0.02):

| Relay | Location | Protects |
|---|---|---|
| R1 | PCC incomer (transformer LV terminals) | Microgrid bus and everything downstream |
| R2 | Fire station feeder | Fire station |
| R3 | Water pump feeder | Water pump |
| R4 | Health clinic feeder | Health clinic |
| R5 | Telecom tower feeder | Telecom tower |

No separate relay on the microgrid bus — R1 covers it grid-connected, and the battery
inverter's own protection covers it islanded (section 5).

---

## 3. Setting method

**Feeder pickups.** 1.3 × full-load current, or 1.1 × motor inrush if a DOL motor is
on the feeder. The 1.3 covers load growth and CT error; the 1.1 clears inrush. Only the
water pump has inrush that matters (WP02, 5.5 kW DOL, ≈ 6 × FLC = 62 A).

**Feeder TMS.** 0.05, the minimum on most numerical relays. Feeders are the last device
before the fault, so they should be the fastest.

**Incomer pickup.** 1.3 × the largest current that can legitimately flow through the PCC.
That is *PV export at full sun* (43 A), not load import (32 A) — the PCC is bidirectional.
Missing this is a classic microgrid error.

**Incomer TMS.** Chosen so that at a fault on the microgrid bus (6 614 A — the most any
feeder relay can see), R1 operates at least 0.3 s after the slowest feeder relay. 0.3 s
is the standard margin for numerical relays: it covers breaker clearing time, relay
overshoot and CT error. Solving the IDMT equation for TMS and rounding up gives 0.27.

---

## 4. Results

### Group 1 — grid-connected

| Relay | Pickup (A) | TMS | t at own-bus fault (s) |
|---|---|---|---|
| R1 | 56.3 | 0.27 | 0.378 |
| R2 | 13.2 | 0.05 | 0.056 |
| R3 | 68.5 | 0.05 | 0.083 |
| R4 | 10.1 | 0.05 | 0.052 |
| R5 | 5.4 | 0.05 | 0.049 |

Grading check at 6 614 A: R1 − feeder margins are 0.305–0.332 s, all ≥ 0.3. **Pass.**

Feeder faults clear in 50–80 ms. The incomer backs them up in 380 ms. Sensitivity to the
minimum (single-phase) fault is never below 40×. Comfortable.

### Group 2 — islanded

| Relay | Pickup (A) | TMS | Sensitivity at 95 A | t (s) |
|---|---|---|---|---|
| R2 | 13.2 | 0.05 | 7.2× | 0.174 |
| R3 | 13.2 | 0.05 | 7.2× | 0.174 |
| R4 | 10.1 | 0.05 | 9.4× | 0.152 |
| R5 | 5.4 | 0.05 | 17.6× | 0.118 |

R1 has no group 2 — it sits on the dead side of the open PCC.

R3 drops from 68.5 A to 13.2 A because **pump starting is blocked in island mode**
(section 6). With the inrush gone, the pickup can follow the load.

Every feeder relay sees the 95 A fault at 7× or better and clears in under 0.2 s. **Pass.**

---

## 5. The islanded decision

Three options were on the table.

**A — One setting group, tuned for both.** Doesn't work. R3 needs a pickup above 68 A to
ride through pump inrush, and a 68 A pickup against a 95 A fault is 1.4× sensitivity —
below the 2× minimum, and it would take 1.1 s to operate (the gold cross on `tcc_island.png`).
Meanwhile the inverter's own overcurrent protection would trip at around 0.2–0.5 s and
collapse the whole island before R3 acted. Discarded.

**B — Undervoltage-supervised overcurrent.** A fault on an inverter-fed system drags the
bus voltage down hard. Add a 27 (undervoltage) element that lowers the overcurrent pickup
when voltage falls below, say, 0.7 pu. Works, and it's how some commercial microgrids do
it. But it adds a dependency on the VT and a second element to coordinate, and it does
not solve the pump-start problem on its own.

**C — Two setting groups, switched by PCC breaker status.** Numerical relays store
several setting groups and switch between them on a binary input. Wire the PCC breaker's
52b (breaker-open) auxiliary contact to each feeder relay. Breaker opens → group 2 active
within one cycle. Breaker recloses → group 1 restored.

**We chose C**, with the pump-start block from section 6 as a necessary companion.

Why C over B: it is simpler to explain, simpler to test, and it uses a feature every
modern feeder relay already has. The one real weakness — if the 52b wiring fails, the
relay stays on group 1 and is blind in island mode — is addressed by having the relay
alarm on loss of the status input, and by the inverter's own protection as a backstop.

Why not both: B on top of C would be a legitimate belt-and-braces design. We left it out
of the base case to keep the coordination study readable. It's a recommended enhancement
in the report.

---

## 6. The pump-start interlock

The pump is DOL started: 62 A inrush for roughly a second. In island mode, the inverter
limit is 95 A and the running load is about 32 A. 32 + 62 = 94 A. The pump start alone
would take the inverter to its current limit, the voltage would sag, and every
undervoltage element on site would see something indistinguishable from a fault.

**Decision:** block pump starts while islanded. Tier 2 already defers the pump to the
solar window, so this is enforcing a decision already made, not a new restriction. The
interlock is a 52b contact from the PCC breaker into the pump starter's control circuit.

**Consequence:** the Tier 2 assumption — that tank reserve covers 24 h of town demand —
is now load-bearing for protection as well as for sizing. If that assumption fails, the
alternative is a soft starter or VSD on the pump (inrush drops to ~1.5–2 × FLC), and the
interlock could be removed. That's a capex trade-off for the report, not a protection
problem.

---

## 7. What the inverter has to do

Group 2 relies on the inverters holding 95 A into a fault for at least 0.2 s so the feeder
relay can act. That's a procurement requirement:

- Battery inverter: grid-forming, fault current ≥ 1.2 × rated for ≥ 0.5 s before
  its own protection intervenes.
- PV inverter: current-limited contribution, must not trip on undervoltage inside
  0.2 s (AS/NZS 4777.2 low-voltage ride-through settings handle this).

Both are standard specifications. Write them into the inverter spec in the design pack.

---

## 8. Open items

- **Single-phase faults islanded.** pandapower's islanded 1ph result (~94 A) assumes the
  inverter contributes symmetrically. Real inverters behave differently under unbalanced
  faults. Needs a manufacturer's fault contribution curve to confirm.
- **Earth fault protection.** Not covered here. A 50N/51N element on each feeder at
  roughly 20 % of phase pickup would be standard. Add in week 10 if time allows.
- **CT ratios.** Feeder CTs 50/5, incomer 100/5. Group 2 pickups of 5–13 A primary sit at
  10–26 % of CT rating — above the 5 % floor where CT accuracy class matters.
- **Relay model.** Settings assume a numerical relay with ≥ 2 setting groups and a binary
  input. Any SEL-751, ABB REF615 or Schneider P14x class device qualifies.
