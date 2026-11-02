"""
relay_settings.py — overcurrent relay settings for the microgrid feeder.

Reads fault_levels.csv (from fault_study.py), params.json and the load list,
then proposes IDMT settings for:
    R1  incomer at the PCC (LV side of the transformer)
    R2..R5  one feeder relay per building

Two setting groups:
    group 1  grid-connected  — fault current in the kA range
    group 2  islanded        — fault current limited to the inverter limit (~94 A)
             switched in by the PCC breaker auxiliary contact (52b)

Method (IEC 60255 standard inverse, IEC 60909 fault levels)
    t = TMS × 0.14 / (M^0.02 − 1),   M = I_fault / I_pickup

    feeder pickup   = max(1.3 × full-load current, 1.1 × motor inrush)      [group 1]
                    = 1.3 × full-load current, pump start blocked            [group 2]
    feeder TMS      = 0.05 (minimum; feeders are the fastest device)
    incomer pickup  = 1.3 × max current through the PCC (import or PV export)
    incomer TMS     = chosen so t_R1 ≥ t_feeder + GRADING_MARGIN at the maximum
                      fault current the feeder relay can see (a fault just below it)

Outputs
    relay_settings.json — the settings plot_tcc.py reads
    console tables      — settings, operate times, grading margins, sensitivity

These are PROPOSED settings. The engineering decision — which to adopt, and how
to handle the islanded case — is in islanded_protection.md.
"""

import json
import math
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path

import pandas as pd

from network import load_params, BUILDINGS

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"

# ---------------------------------------------------------------- constants
GRADING_MARGIN_S = 0.30   # typical for numerical relays (0.4 for electromechanical)
FEEDER_TMS = 0.05         # minimum TMS on most numerical relays
PICKUP_LOAD_FACTOR = 1.30
PICKUP_INRUSH_FACTOR = 1.10
MOTOR_INRUSH_MULT = 6.0   # DOL start, locked-rotor multiple of FLC
MIN_SENSITIVITY = 2.0     # I_fault,min / I_pickup must exceed this
IEC_SI = (0.14, 0.02)     # standard inverse constants (k, alpha)
VN_KV = 0.4
PF = 0.9
MOTOR_EFF = 0.90


def idmt_time(i_fault, pickup, tms, k=IEC_SI[0], a=IEC_SI[1]):
    m = i_fault / pickup
    if m <= 1.0:
        return math.inf
    return tms * k / (m ** a - 1)


def amps(p_kw, pf=PF):
    return p_kw * 1000 / (math.sqrt(3) * VN_KV * 1000 * pf)


# ------------------------------------------------------------ load currents
def feeder_currents():
    """Connected (not average) load per building, tiers 1+2, plus motor inrush."""
    df = pd.read_csv(DATA / "critical_load_list.csv")
    num = pd.to_numeric(df.rated_power_W, errors="coerce").fillna(0)
    qty = pd.to_numeric(df.quantity, errors="coerce").fillna(1)
    df["kw"] = num * qty / 1000
    df = df[df.tier.astype(str).isin(["1", "2"])]
    out = {}
    for b in BUILDINGS:
        sub = df[df.building == b]
        flc = amps(sub.kw.sum())
        inrush = 0.0
        # the only DOL motor large enough to matter is the pump (WP02)
        pump = sub[sub.load_id == "WP02"]
        if not pump.empty:
            motor_flc = amps(pump.kw.iloc[0] / MOTOR_EFF, pf=0.85)
            inrush = MOTOR_INRUSH_MULT * motor_flc
        out[b] = dict(flc_a=flc, inrush_a=inrush)
    return out


def pcc_max_current(p):
    """Worst case through the PCC: import at full load or PV export at full sun."""
    loads = feeder_currents()
    import_a = sum(v["flc_a"] for v in loads.values())
    export_a = (p["pv"]["p_mw"] * 1000) / (math.sqrt(3) * VN_KV)
    return max(import_a, export_a), import_a, export_a


# -------------------------------------------------------------- settings
def main():
    p = load_params()
    fl = pd.read_csv(HERE / "fault_levels.csv")

    def ik(bus, state, fault="3ph"):
        r = fl[(fl.bus == bus) & (fl.state == state) & (fl.fault == fault)]
        return float(r.ikss_a.iloc[0]) if not r.empty and pd.notna(r.ikss_a.iloc[0]) else math.nan

    loads = feeder_currents()
    pcc_max, pcc_import, pcc_export = pcc_max_current(p)

    # --- feeder relays, group 1 (grid) and group 2 (island) ---------------
    relays = {}
    for i, b in enumerate(BUILDINGS, start=2):
        L = loads[b]
        pu_g1 = max(PICKUP_LOAD_FACTOR * L["flc_a"], PICKUP_INRUSH_FACTOR * L["inrush_a"])
        pu_g2 = PICKUP_LOAD_FACTOR * L["flc_a"]          # pump start blocked in island
        relays[f"R{i}"] = dict(
            location=f"feeder_{b}", bus_protected=b,
            flc_a=round(L["flc_a"], 1), inrush_a=round(L["inrush_a"], 1),
            group1=dict(pickup_a=round(pu_g1, 1), tms=FEEDER_TMS, curve="IEC_SI"),
            group2=dict(pickup_a=round(pu_g2, 1), tms=FEEDER_TMS, curve="IEC_SI"),
        )

    # --- incomer R1, group 1 only (it is on the dead side when islanded) ----
    pu_r1 = PICKUP_LOAD_FACTOR * pcc_max
    # coordinate against the slowest feeder relay at the maximum current it can see,
    # which is a fault at the microgrid bus end of its feeder
    i_coord = ik("microgrid_bus", "grid_connected")
    t_feeder_max = max(idmt_time(i_coord, r["group1"]["pickup_a"], FEEDER_TMS)
                       for r in relays.values())
    t_r1_required = t_feeder_max + GRADING_MARGIN_S
    m = i_coord / pu_r1
    tms_r1 = t_r1_required * (m ** IEC_SI[1] - 1) / IEC_SI[0]
    tms_r1 = math.ceil(tms_r1 * 100) / 100       # round UP to the next 0.01
    relays["R1"] = dict(
        location="pcc_incomer", bus_protected="microgrid_bus",
        pcc_import_a=round(pcc_import, 1), pcc_export_a=round(pcc_export, 1),
        group1=dict(pickup_a=round(pu_r1, 1), tms=tms_r1, curve="IEC_SI"),
        group2=None,
    )

    # --- checks --------------------------------------------------------------
    rows = []
    for name, r in relays.items():
        bus = r["bus_protected"]
        for grp, state in (("group1", "grid_connected"), ("group2", "islanded")):
            g = r.get(grp)
            if g is None:
                continue
            i_max = ik(bus if name != "R1" else "microgrid_bus", state)
            i_min = ik(bus if name != "R1" else "microgrid_bus", state, "1ph")
            i_min = min(i_min, i_max) if not math.isnan(i_min) else i_max
            rows.append(dict(
                relay=name, group=grp, state=state,
                pickup_a=g["pickup_a"], tms=g["tms"],
                i_fault_max_a=round(i_max, 0),
                t_at_max_s=round(idmt_time(i_max, g["pickup_a"], g["tms"]), 3),
                i_fault_min_a=round(i_min, 0),
                sensitivity=round(i_min / g["pickup_a"], 2),
                sens_ok=(i_min / g["pickup_a"]) >= MIN_SENSITIVITY,
            ))
    checks = pd.DataFrame(rows)

    # grading R1 vs each feeder at the feeder's max fault (bus fault)
    grading = []
    for name, r in relays.items():
        if name == "R1":
            continue
        t_f = idmt_time(i_coord, r["group1"]["pickup_a"], r["group1"]["tms"])
        t_1 = idmt_time(i_coord, relays["R1"]["group1"]["pickup_a"], relays["R1"]["group1"]["tms"])
        grading.append(dict(downstream=name, upstream="R1", i_coord_a=round(i_coord),
                            t_down_s=round(t_f, 3), t_up_s=round(t_1, 3),
                            margin_s=round(t_1 - t_f, 3),
                            ok=(t_1 - t_f) >= GRADING_MARGIN_S - 1e-9))
    grading = pd.DataFrame(grading)

    # --- output --------------------------------------------------------------
    pd.set_option("display.width", 160)
    print("\n=== Load basis ===")
    for b, L in loads.items():
        print(f"  {b:<15} FLC {L['flc_a']:6.1f} A   inrush {L['inrush_a']:6.1f} A")
    print(f"  PCC: import {pcc_import:.1f} A, PV export {pcc_export:.1f} A → design {pcc_max:.1f} A")

    print("\n=== Proposed settings ===")
    tbl = []
    for name in ["R1"] + [f"R{i}" for i in range(2, 6)]:
        r = relays[name]
        tbl.append(dict(relay=name, location=r["location"],
                        g1_pickup_a=r["group1"]["pickup_a"], g1_tms=r["group1"]["tms"],
                        g2_pickup_a=(r["group2"] or {}).get("pickup_a", "—"),
                        g2_tms=(r["group2"] or {}).get("tms", "—")))
    print(pd.DataFrame(tbl).to_string(index=False))

    print("\n=== Operate time and sensitivity at each relay's own bus ===")
    print(checks.to_string(index=False))

    print(f"\n=== Grading R1 vs feeders at I = {i_coord:.0f} A (bus fault), margin ≥ {GRADING_MARGIN_S} s ===")
    print(grading.to_string(index=False))

    bad = checks[~checks.sens_ok]
    if not bad.empty:
        print("\nSENSITIVITY WARNING — these settings will not reliably see the minimum fault:")
        print(bad[["relay", "group", "pickup_a", "i_fault_min_a", "sensitivity"]].to_string(index=False))
    if not grading.ok.all():
        print("\nGRADING FAILURE — raise R1 TMS or lower feeder settings.")

    out = dict(constants=dict(grading_margin_s=GRADING_MARGIN_S, curve="IEC standard inverse",
                              k=IEC_SI[0], alpha=IEC_SI[1], min_sensitivity=MIN_SENSITIVITY),
               coordination_current_a=round(i_coord), relays=relays)
    with open(HERE / "relay_settings.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\nWritten relay_settings.json")


if __name__ == "__main__":
    main()
