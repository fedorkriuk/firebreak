"""
size_system.py — PV and battery sizing for the islanding microgrid.

Design case (see design_basis.md):
    Grid fails at dusk on the lowest-irradiance day of the year.
    Tier 1 must be served continuously for 24 hours.
    Tier 2 is deferred into the following solar window.
    Tier 3 is shed.

Usage:
    python3 size_system.py                       # uses synthetic irradiance (PLACEHOLDER)
    python3 size_system.py --pvgis pvgis.csv     # uses real PVGIS hourly export

The synthetic generator exists so the method can be built and tested before
point 1 delivers real data. Results from it are INDICATIVE ONLY.
"""

import argparse
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"

# ----------------------------------------------------------------------
# Assumptions — change here, not inline
# ----------------------------------------------------------------------
ROUND_TRIP_EFF   = 0.90   # battery charge/discharge round trip
INVERTER_EFF     = 0.96
DEPTH_OF_DISCHARGE = 0.80
DUSK_HOUR        = 17     # island event starts here
SITE_LAT         = -34.5  # Southern Tablelands NSW, representative site

PV_RANGE_KW      = np.arange(10, 65, 5)
BATT_RANGE_KWH   = np.arange(40, 220, 10)


# ----------------------------------------------------------------------
# Load profile
# ----------------------------------------------------------------------
def build_load_profiles(path=DATA / "critical_load_list.csv"):
    """Return hourly kW arrays (24 values) for Tier 1 and Tier 2."""
    df = pd.read_csv(path)
    num  = pd.to_numeric(df.rated_power_W, errors="coerce").fillna(0)
    qty  = pd.to_numeric(df.quantity, errors="coerce").fillna(1)
    duty = pd.to_numeric(df.duty_cycle_pct, errors="coerce").fillna(0)
    df["avg_W"] = num * qty * duty / 100.0

    t1 = np.zeros(24)
    t2 = np.zeros(24)

    for _, r in df.iterrows():
        w, when, tier = r.avg_W, r.runs_when, str(r.tier)
        if w <= 0 or tier not in ("1", "2"):
            continue
        if when == "continuous_24h" or when == "on_demand":
            hours = range(24)
        elif when == "night_only":
            hours = list(range(18, 24)) + list(range(0, 6))
        elif when == "daylight_only":
            hours = range(7, 17)
        else:
            continue
        target = t1 if tier == "1" else t2
        for h in hours:
            target[h] += w / 1000.0   # kW

    return t1, t2


# ----------------------------------------------------------------------
# Irradiance
# ----------------------------------------------------------------------
def synthetic_worst_day(lat=SITE_LAT, seed=42):
    """
    PLACEHOLDER. Clear-sky model with winter cloud derating.
    Returns 24 hourly values of PV output per kW installed (kW/kWp).
    Replace with real PVGIS data as soon as point 1 lands.
    """
    rng = np.random.default_rng(seed)
    hours = np.arange(24)
    # winter solstice declination
    decl = np.radians(-23.45 * np.cos(np.radians(360 * (355 + 10) / 365)))
    latr = np.radians(lat)
    hour_angle = np.radians(15 * (hours - 12))
    elev = np.arcsin(np.sin(latr) * np.sin(decl)
                     + np.cos(latr) * np.cos(decl) * np.cos(hour_angle))
    clear = np.clip(np.sin(elev), 0, None)          # normalised clear-sky
    cloud = 0.35 + 0.10 * rng.random(24)            # heavy overcast worst day
    return clear * cloud * 0.85                     # 0.85 system derate


def pvgis_worst_day(path):
    """Read a PVGIS hourly CSV export and return the worst day's kW/kWp profile."""
    df = pd.read_csv(path, skiprows=10)
    df.columns = [c.strip() for c in df.columns]
    time_col = [c for c in df.columns if "time" in c.lower()][0]
    p_col    = [c for c in df.columns if c.upper().startswith("P")][0]
    df["ts"] = pd.to_datetime(df[time_col], format="%Y%m%d:%H%M")
    df["kw_per_kwp"] = df[p_col] / 1000.0
    daily = df.groupby(df.ts.dt.date).kw_per_kwp.sum()
    worst = daily.idxmin()
    day = df[df.ts.dt.date == worst].sort_values("ts")
    print(f"Worst day found: {worst}  ({daily.min():.2f} kWh/kWp)")
    return day.kw_per_kwp.to_numpy()[:24]


# ----------------------------------------------------------------------
# 24-hour island simulation
# ----------------------------------------------------------------------
def simulate(pv_kw, batt_kwh, t1, t2, pv_shape):
    """
    Run the 24 h island starting at DUSK_HOUR.
    Returns (unserved_t1_kwh, unserved_t2_kwh, min_soc_frac).
    """
    usable = batt_kwh * DEPTH_OF_DISCHARGE
    soc = usable
    unserved_1 = unserved_2 = 0.0
    min_soc = soc

    order = [(DUSK_HOUR + i) % 24 for i in range(24)]
    for h in order:
        gen = pv_shape[h] * pv_kw * INVERTER_EFF      # kWh in this hour
        demand_1 = t1[h]
        demand_2 = t2[h]

        # Tier 1 first: PV, then battery
        net = gen - demand_1
        if net >= 0:
            surplus = net
        else:
            need = -net
            draw = min(need, soc)
            soc -= draw
            if draw < need:
                unserved_1 += need - draw
            surplus = 0.0

        # Tier 2 next: PV surplus only, never the battery
        if surplus > 0 and demand_2 > 0:
            served = min(surplus, demand_2)
            surplus -= served
            unserved_2 += demand_2 - served
        else:
            unserved_2 += demand_2

        # remaining surplus recharges
        if surplus > 0:
            soc = min(usable, soc + surplus * ROUND_TRIP_EFF)

        min_soc = min(min_soc, soc)

    return unserved_1, unserved_2, (min_soc / usable if usable else 0)


# ----------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pvgis", help="PVGIS hourly CSV export")
    ap.add_argument("--loads", default=str(DATA / "critical_load_list.csv"))
    args = ap.parse_args()

    t1, t2 = build_load_profiles(args.loads)
    print(f"Tier 1 energy : {t1.sum():.1f} kWh/day   peak {t1.max():.2f} kW")
    print(f"Tier 2 energy : {t2.sum():.1f} kWh/day   peak {t2.max():.2f} kW")

    if args.pvgis:
        pv_shape = pvgis_worst_day(args.pvgis)
        source = f"PVGIS ({args.pvgis})"
    else:
        pv_shape = synthetic_worst_day()
        source = "SYNTHETIC PLACEHOLDER — replace with PVGIS"
    print(f"Irradiance source: {source}")
    print(f"Worst-day yield  : {pv_shape.sum():.2f} kWh per kWp installed\n")

    rows = []
    for pv in PV_RANGE_KW:
        for bat in BATT_RANGE_KWH:
            u1, u2, msoc = simulate(pv, bat, t1, t2, pv_shape)
            rows.append(dict(pv_kw=pv, batt_kwh=bat,
                             unserved_t1_kwh=round(u1, 2),
                             unserved_t2_kwh=round(u2, 2),
                             min_soc_pct=round(msoc * 100, 1)))
    res = pd.DataFrame(rows)
    res.to_csv(HERE / "sizing_sweep.csv", index=False)

    feasible = res[res.unserved_t1_kwh < 0.01]
    if feasible.empty:
        print("No combination in the sweep range serves Tier 1 fully.")
        return

    # smallest battery that works, then smallest PV at that battery
    best_batt = feasible.batt_kwh.min()
    cand = feasible[feasible.batt_kwh == best_batt]
    best = cand.loc[cand.pv_kw.idxmin()]

    print("FEASIBLE MINIMUM (Tier 1 fully served)")
    print(f"  PV        : {best.pv_kw:.0f} kWp")
    print(f"  Battery   : {best.batt_kwh:.0f} kWh nameplate "
          f"({best.batt_kwh * DEPTH_OF_DISCHARGE:.0f} kWh usable at {DEPTH_OF_DISCHARGE:.0%} DoD)")
    print(f"  Min SoC   : {best.min_soc_pct:.1f}% of usable")
    print(f"  Tier 2 unserved: {best.unserved_t2_kwh:.1f} kWh/day")

    # recommend one step up on each axis for margin
    rec_pv = best.pv_kw + 10
    rec_bat = best.batt_kwh + 20
    u1, u2, msoc = simulate(rec_pv, rec_bat, t1, t2, pv_shape)
    print("\nRECOMMENDED (one margin step on each axis)")
    print(f"  PV        : {rec_pv:.0f} kWp")
    print(f"  Battery   : {rec_bat:.0f} kWh nameplate")
    print(f"  Min SoC   : {msoc * 100:.1f}%   Tier 2 unserved: {u2:.1f} kWh/day")

    # inverter sizing — peak instantaneous, not average
    df = pd.read_csv(args.loads)
    num = pd.to_numeric(df.rated_power_W, errors="coerce").fillna(0)
    qty = pd.to_numeric(df.quantity, errors="coerce").fillna(1)
    t1_connected = (num[df.tier.astype(str) == "1"] * qty[df.tier.astype(str) == "1"]).sum()
    print(f"\nINVERTER")
    print(f"  Tier 1 connected load     : {t1_connected/1000:.2f} kW")
    print(f"  Roller door surge (FS01)  : included above, 1.5 kW instantaneous")
    print(f"  WP02 DOL start (Tier 2)   : 5.5 kW x ~6 = 33 kW inrush if started while islanded")
    print(f"  -> size for Tier 1 peak plus soft-start on WP02, or block WP02 start in island mode")

    print("\nFull sweep written to sizing_sweep.csv")


if __name__ == "__main__":
    main()
