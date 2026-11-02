"""
fault_study.py — IEC 60909 short-circuit study for the microgrid feeder.

Runs three-phase and single-phase-to-ground faults at every bus, twice:
    grid-connected  — external grid is the dominant source
    islanded        — PCC open; inverters are the only source, current-limited

Islanded inverter representation
    The battery inverter is grid-forming and is modelled as a weak external grid
    whose fault level equals √3 × V × I_limit, where I_limit is the combined PV +
    battery current limit at fault_k × rated (params.json). This is the Thévenin
    equivalent of a current-limited source and is the assumption the whole islanded
    result depends on. See assumptions in params.json.

Outputs
    fault_levels.csv   — one row per (bus, fault type, operating state)
    console summary    — minimum fault current per bus across both states,
                         which is the ceiling for any overcurrent relay pickup

Usage
    python3 fault_study.py
"""

import warnings
warnings.filterwarnings("ignore")
from pathlib import Path

import numpy as np
import pandas as pd
import pandapower as pp
import pandapower.shortcircuit as sc

from network import build_network, load_params, BUILDINGS

HERE = Path(__file__).resolve().parent
STUDY_BUSES = ["pcc", "microgrid_bus"] + BUILDINGS
FAULTS = {"3ph": "three-phase", "1ph": "single-phase-to-ground"}


def run_case(p: dict, islanded: bool, fault: str) -> pd.DataFrame:
    net = build_network(p, islanded=islanded, tiers=("1",))
    sc.calc_sc(net, fault=fault, case="max", ip=True, ith=False,
               branch_results=False, check_connectivity=True)
    res = net.res_bus_sc.copy()
    res.insert(0, "bus", net.bus.name.values)
    res = res[res.bus.isin(STUDY_BUSES)]
    res["fault"] = fault
    res["state"] = "islanded" if islanded else "grid_connected"
    keep = ["bus", "fault", "state", "ikss_ka", "ip_ka"]
    return res[keep].reset_index(drop=True)


def main():
    p = load_params()
    frames = []
    for islanded in (False, True):
        for fault in FAULTS:
            frames.append(run_case(p, islanded, fault))
    df = pd.concat(frames, ignore_index=True)

    # convert to amps for readability, keep kA columns too
    df["ikss_a"] = (df.ikss_ka * 1000).round(1)
    df["ip_a"] = (df.ip_ka * 1000).round(1)

    # ratio grid-connected / islanded, per bus and fault type
    piv = df.pivot_table(index=["bus", "fault"], columns="state", values="ikss_a")
    piv["ratio_grid_to_island"] = (piv["grid_connected"] / piv["islanded"]).round(1)
    piv = piv.reset_index()

    df = df.merge(piv[["bus", "fault", "ratio_grid_to_island"]], on=["bus", "fault"])
    order = {b: i for i, b in enumerate(STUDY_BUSES)}
    df["_o"] = df.bus.map(order)
    df = df.sort_values(["_o", "fault", "state"]).drop(columns="_o").reset_index(drop=True)
    df.to_csv(HERE / "fault_levels.csv", index=False)

    # ---- console summary -------------------------------------------------
    pd.set_option("display.width", 140)
    print("\n=== IEC 60909 fault levels (max case)  —  I''k in amps ===")
    show = piv.copy()
    show.columns.name = None
    show = show.rename(columns={"grid_connected": "grid_connected_A", "islanded": "islanded_A"})
    show["_o"] = show.bus.map(order)
    show = show.sort_values(["_o", "fault"]).drop(columns="_o")
    print(show.round(1).to_string(index=False))

    print("\n=== Minimum fault current per bus across BOTH states ===")
    print("    (any overcurrent pickup must sit below this, with margin)")
    mins = df.groupby("bus").ikss_a.min().reindex(STUDY_BUSES)
    for b, v in mins.items():
        print(f"    {b:<15} {v:>8.1f} A")

    i_lim = 1000 * sum(p[k]["fault_k"] * p[k]["sn_mva"] for k in ("pv", "battery")) \
        / (np.sqrt(3) * p["lv"]["vn_kv"])
    print(f"\nInverter current limit used for islanded case: {i_lim:.1f} A "
          f"(PV + battery at {p['pv']['fault_k']}× rated)")
    print("Full results written to fault_levels.csv")


if __name__ == "__main__":
    main()
