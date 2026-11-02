# Pair 1 (Site & Sizing): Week 12 roadshow demo

Team 10, Firebreak Energy Systems, 41086 Studio, Spring 2026.
Scope: Pair 1 deliverables only (load list/profiles, PV/BESS sizing, shared parameters,
energy balance, pandapower fault study, CT/VT ratios). The Simulink plant, relay settings,
LoM detection and classifier belong to Pairs 2 and 3 and are not in this folder.

## Run

```
pip install -r requirements.txt
python run_all.py          # ~15 s, plots saved as PNG
python run_all.py --open   # also opens the 4 roadshow plots
```

Tested: Python 3.10 (Linux) with pandapower 3.5.6. Ken's PC: Python 3.14.7, pandapower 3.5.4.

## Files

| Step | File | Does | Main outputs |
|---|---|---|---|
| - | `pvgis.py` | Loads PVGIS 2023 hourly data, converts UTC to AEST | (used by 2 and 5) |
| 1 | `load_profiles.py` | Builds 15-min load profile per building from `equipment.csv` | `cluster_load_profiles_15min.csv`, `load_summary.json`, `cluster_stacked_load_profile.png` |
| 2 | `size_system.py` | Sweeps PV size; battery from worst observed 1/3/7-day windows; x1.15 margin | `sizing_table.csv`, `design_params.json`, `sizing_results.png` |
| 3 | `params.py` | Single source of truth; exports values for Pair 2 | `outputs/params.json`, `outputs/params.m` |
| 4 | `fault_study.py` | IEC 60909 short circuit (pandapower): grid/island x day/night x max/min; CT/VT selection | `outputs/fault_table*.csv`, `outputs/ct_vt_table.csv`, `outputs/fault_study.png` |
| 5 | `check_energy_balance.py` | Islands every evening of 2023 at the installed size; year-long island stress test | `outputs/energy_balance_year.csv`, `outputs/energy_balance.png` |

## Key results (run 20 Oct 2026)

- Load: 104.7 kWh/day cluster, 60 kWh/day Tier 1, 10.2 kW peak after diversity
- Sizing: 30 kWp / 110 kWh design (worst 3-day window, 13-15 Aug 2023) -> installed 35.2 kWp / 130 kWh
- Fault: grid 3ph at PCC 3.80 kA (c_max); island 3ph 104 A (day) / 52 A (night)
- CTs: R_PCC 75/1, R1 75/1, R2 40/1, R3 25/1, all 5P20
- Energy: 362/362 evenings survive islanding (worst min SoC 64.8 %); 0 kWh Tier 1 unserved all year

## Assumptions (set in `params.py`)

Grid fault level 50/20 MVA (max/min), 100 kVA 4 % transformer, feeder lengths 0.3/0.4/0.5 km,
BESS modelled as a voltage source with a current limit (k = 1.2). Single year of PVGIS data (2023).
