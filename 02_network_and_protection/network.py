"""
network.py — pandapower model of the islanding microgrid feeder.

Topology
    ext_grid (11 kV) ── trafo 11/0.4 kV ── PCC bus ──[switch]── microgrid bus
                                                                  ├── PV (sgen)
                                                                  ├── Battery (sgen, or slack when islanded)
                                                                  ├── line ── fire_station
                                                                  ├── line ── water_pump
                                                                  ├── line ── health_clinic
                                                                  └── line ── telecom_tower

Every numeric parameter comes from params.json. Loads come from critical_load_list.csv.

Usage
    from network import build_network, load_params
    net = build_network(load_params(), islanded=False, tiers=("1",))
"""

import json
import warnings
warnings.filterwarnings("ignore")
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pandapower as pp

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"          # shared parameters and load list
BUILDINGS = ["fire_station", "water_pump", "health_clinic", "telecom_tower"]


# ----------------------------------------------------------------------
# Inputs
# ----------------------------------------------------------------------
def load_params(path: Path = DATA / "params.json") -> dict:
    with open(path) as f:
        return json.load(f)


def building_loads(tiers=("1",), path: Path = DATA / "critical_load_list.csv") -> dict:
    """
    Average real power per building in MW, for the requested tiers.
    avg_W = rated_power_W × quantity × duty_cycle_pct / 100
    """
    df = pd.read_csv(path)
    num = pd.to_numeric(df.rated_power_W, errors="coerce").fillna(0)
    qty = pd.to_numeric(df.quantity, errors="coerce").fillna(1)
    duty = pd.to_numeric(df.duty_cycle_pct, errors="coerce").fillna(0)
    df["avg_mw"] = num * qty * duty / 100 / 1e6
    df = df[df.tier.astype(str).isin(tiers)]
    out = df.groupby("building").avg_mw.sum().to_dict()
    return {b: float(out.get(b, 0.0)) for b in BUILDINGS}


def inverter_fault_current_ka(p: dict, vn_kv: float) -> float:
    """
    Combined inverter contribution to a fault, current-limited at fault_k × rated.
    I = fault_k × S / (√3 × V)
    """
    total = 0.0
    for key in ("pv", "battery"):
        total += p[key]["fault_k"] * p[key]["sn_mva"]
    return total / (math.sqrt(3) * vn_kv)  # kA


# ----------------------------------------------------------------------
# Network
# ----------------------------------------------------------------------
def build_network(p: dict, islanded: bool = False, tiers=("1",)) -> pp.pandapowerNet:
    """
    Build the feeder.

    islanded=False : grid-connected. External grid is the slack.
    islanded=True  : PCC switch open, external grid out of service.
                     The battery inverter becomes the slack (grid-forming) and is
                     represented as a weak ext_grid whose fault level equals the
                     combined current-limited inverter contribution.
    """
    net = pp.create_empty_network(name="firebreak_microgrid", sn_mva=1.0)
    g, t, lv = p["grid"], p["transformer"], p["lv"]

    # --- buses ----------------------------------------------------------
    b_hv = pp.create_bus(net, vn_kv=g["vn_kv"], name="hv_11kv")
    b_pcc = pp.create_bus(net, vn_kv=lv["vn_kv"], name="pcc")
    b_mg = pp.create_bus(net, vn_kv=lv["vn_kv"], name="microgrid_bus")
    b_load = {b: pp.create_bus(net, vn_kv=lv["vn_kv"], name=b) for b in BUILDINGS}

    # --- upstream grid + transformer -------------------------------------
    pp.create_ext_grid(
        net, bus=b_hv, vm_pu=1.0, name="grid_11kv",
        s_sc_max_mva=g["s_sc_max_mva"], s_sc_min_mva=g["s_sc_min_mva"],
        rx_max=g["rx_max"], rx_min=g["rx_min"],
        x0x_max=g["x0x_max"], r0x0_max=g["r0x0_max"],
        in_service=not islanded,
    )
    pp.create_transformer_from_parameters(
        net, hv_bus=b_hv, lv_bus=b_pcc, name="dist_trafo",
        sn_mva=t["sn_mva"], vn_hv_kv=t["vn_hv_kv"], vn_lv_kv=t["vn_lv_kv"],
        vk_percent=t["vk_percent"], vkr_percent=t["vkr_percent"],
        pfe_kw=t["pfe_kw"], i0_percent=t["i0_percent"],
        vector_group=t["vector_group"], vk0_percent=t["vk0_percent"],
        vkr0_percent=t["vkr0_percent"], mag0_percent=t["mag0_percent"],
        mag0_rx=t["mag0_rx"], si0_hv_partial=t["si0_hv_partial"],
        in_service=not islanded,
    )

    # --- PCC switch -------------------------------------------------------
    # A short tie line so the switch can sit between two real buses.
    tie = pp.create_line(net, from_bus=b_pcc, to_bus=b_mg,
                         length_km=p["feeders"]["pcc_to_bus"]["length_km"],
                         std_type=lv["line_type"], name="pcc_tie")
    pp.create_switch(net, bus=b_pcc, element=tie, et="l",
                     closed=not islanded, name="pcc_switch")

    # --- LV feeders to each building -------------------------------------
    for b in BUILDINGS:
        pp.create_line(net, from_bus=b_mg, to_bus=b_load[b],
                       length_km=p["feeders"][b]["length_km"],
                       std_type=lv["line_type"], name=f"line_{b}")

    # zero-sequence line data (needed for single-phase faults)
    net.line["r0_ohm_per_km"] = net.line["r_ohm_per_km"] * lv["r0_factor"]
    net.line["x0_ohm_per_km"] = net.line["x_ohm_per_km"] * lv["x0_factor"]
    net.line["c0_nf_per_km"] = net.line["c_nf_per_km"] * lv["c0_factor"]
    net.line["endtemp_degree"] = 80.0

    # --- loads ------------------------------------------------------------
    pf = p["load_defaults"]["power_factor"]
    for b, p_mw in building_loads(tiers).items():
        q_mvar = p_mw * math.tan(math.acos(pf))
        pp.create_load(net, bus=b_load[b], p_mw=p_mw, q_mvar=q_mvar, name=f"load_{b}")

    # --- generation -------------------------------------------------------
    pv, bat = p["pv"], p["battery"]
    pp.create_sgen(net, bus=b_mg, p_mw=pv["p_mw"], q_mvar=0.0, sn_mva=pv["sn_mva"],
                   name="pv", k=pv["fault_k"], current_source=True)

    if islanded:
        # Battery inverter is grid-forming: it is the slack AND the fault source.
        # Fault level = √3 × V × I_limit, where I_limit is the combined inverter
        # current limit. This is the Thévenin equivalent of a current-limited source.
        i_lim_ka = inverter_fault_current_ka(p, lv["vn_kv"])
        s_sc = math.sqrt(3) * lv["vn_kv"] * i_lim_ka
        pp.create_ext_grid(
            net, bus=b_mg, vm_pu=1.0, name="battery_grid_forming",
            s_sc_max_mva=s_sc, s_sc_min_mva=s_sc,
            rx_max=1.0, rx_min=1.0,      # inverter output is roughly resistive-inductive
            x0x_max=1.0, r0x0_max=1.0,
        )
        # PV stays as a current source; the ext_grid already includes its share,
        # so take it out of the sc contribution to avoid double counting.
        net.sgen.loc[net.sgen.name == "pv", "k"] = 0.0
    else:
        pp.create_sgen(net, bus=b_mg, p_mw=0.0, q_mvar=0.0, sn_mva=bat["sn_mva"],
                       name="battery", k=bat["fault_k"], current_source=True)

    net.islanded = islanded
    return net


# ----------------------------------------------------------------------
# Load flow
# ----------------------------------------------------------------------
def run_loadflow(net: pp.pandapowerNet) -> pd.DataFrame:
    pp.runpp(net, calculate_voltage_angles=True, init="flat")
    if not net.converged:
        raise RuntimeError("Load flow did not converge — check params.json and the load list.")
    out = net.res_bus[["vm_pu", "va_degree", "p_mw", "q_mvar"]].copy()
    out.insert(0, "bus", net.bus.name.values)
    out["p_kw"] = out.p_mw * 1000
    out["q_kvar"] = out.q_mvar * 1000
    return out.drop(columns=["p_mw", "q_mvar"]).round(4)


# ----------------------------------------------------------------------
if __name__ == "__main__":
    p = load_params()
    for islanded in (False, True):
        net = build_network(p, islanded=islanded, tiers=("1",))
        state = "ISLANDED" if islanded else "GRID-CONNECTED"
        print(f"\n=== Load flow — {state} — Tier 1 loads ===")
        print(run_loadflow(net).to_string(index=False))
        loads_kw = (net.load.p_mw * 1000).round(2).tolist()
        print(f"Total Tier 1 load: {sum(loads_kw):.2f} kW  (per building: {loads_kw})")
