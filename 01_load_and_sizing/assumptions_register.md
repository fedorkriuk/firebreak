# Assumptions Register — Critical Load List

Every figure in `critical_load_list.csv` is either a cited manufacturer specification or a
derived engineering estimate. Nothing is unexplained. This register is the audit trail.

## Source classification

| `source_type` | Count | Meaning |
|---|---|---|
| `datasheet` | 4 | Published manufacturer specification, cited in `source_reference` |
| `derived` | 25 | Engineering estimate built from a stated calculation in `basis_of_estimate` |

Derived is legitimate engineering practice. What makes it defensible is that each one shows
its working — a component count, a rating and an efficiency — so a reader can disagree with
the input rather than the number.

## Cited specifications

| ID | Item | Figure | Source |
|---|---|---|---|
| HC01 | Vaccine refrigerator | 523 W max | Ummac MED890R, 700 L, 230 V/50 Hz |
| HC02 | Medication refrigerator | 104 W, 0.71 kWh/day | American Biotech Supply PH-ABT-HC-UCFS-0104 |
| HC05 | Oxygen concentrator | ~350 W | Philips Respironics EverFlo, 230 V 50 Hz |
| WP02 | Borehole pump motor | 5.5 kW | Grundfos SP5A-60N, MS4000 motor, DOL start |

HC02's duty cycle is derived from the manufacturer's own daily energy figure
(710 Wh / (104 W x 24 h) = 28%), so rating and duty are self-consistent.

## Standing assumptions

- **Cooling COP 3.0** for all air-conditioning loads (TT02, TT05, HC06).
- **LED lighting at 20 W per fitting** throughout; quantities stated per row.
- **Rectifier efficiency 96%**, from the Eltek Flatpack2 HE specification.
- **Night window 12 h, solar window 10 h.** Both should be replaced with figures from
  the PVGIS worst-day data once Nam completes point 1.
- **Duty cycle is a fraction of the window, not of the day.**
  Energy = rated_power_W x quantity x duty_cycle_pct/100 x window_hours.

## Result

| | Value |
|---|---|
| Tier 1 energy | 81.7 kWh/day |
| Tier 1 peak connected | 6.7 kW |
| Tier 2 energy (PV-served) | 30.6 kWh/day |

| Building | Tier 1 kWh/day | Share |
|---|---|---|
| Telecom tower | 47.3 | 58% |
| Health clinic | 20.1 | 25% |
| Fire station | 11.4 | 14% |
| Water pump | 2.9 | 4% |

## TT01 sensitivity — the assumption that matters

TT01 is 46% of Tier 1 energy on its own, and it is derived rather than cited. Battery
nameplate assumes 10% margin for inverter and round-trip losses, and 80% depth of discharge.

| DC site load (kW) | TT01 (kWh/day) | Tier 1 (kWh/day) | Usable (kWh) | Nameplate (kWh) |
|---|---|---|---|---|
| 0.75 | 18.8 | 63.0 | 69.3 | 86.6 |
| 1.00 | 25.0 | 69.2 | 76.1 | 95.2 |
| 1.25 | 31.3 | 75.5 | 83.0 | 103.8 |
| **1.50** | **37.5** | **81.7** | **89.9** | **112.4** |
| 2.00 | 50.0 | 94.2 | 103.6 | 129.5 |
| 2.50 | 62.5 | 106.7 | 117.4 | 146.7 |
| 3.00 | 75.0 | 119.2 | 131.1 | 163.9 |

Everything except TT01 contributes 44.2 kWh/day. Across the plausible range the battery
moves by nearly a factor of two — 87 to 164 kWh. **Verify TT01 before locking sizing.**

Ways to close it: a carrier or tower-company site power specification; an NBN fixed-wireless
site figure; or ask Dr Abuhilaleh whether an industry contact can confirm typical rural
macro-site DC load. Failing all three, carry the sensitivity table into the report and size
against the upper end.

## Rows to upgrade first

Highest energy contribution, so highest value in replacing the estimate with a citation:

1. **TT01** — 37.5 kWh/day, 46% of Tier 1
2. **TT02** — 8.6 kWh/day
3. **HC04** — 6.0 kWh/day
4. **FS02** — 6.0 kWh/day
5. **HC03** — 4.8 kWh/day

Tier 3 rows are excluded from sizing entirely, so their figures barely matter. Do not spend
research time there.

## Reproducing the numbers

`python3 sensitivity.py` recomputes every figure in this document from the CSV. If a row
changes, re-run it rather than editing these tables by hand.
