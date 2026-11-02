"""
verify.py — cross-check pandapower against the hand calculation for the PCC bus.

The hand calculation (see hand_calculation.md) gives the grid-only contribution.
pandapower adds the inverter contribution on top, so the model result should sit
slightly ABOVE the hand value by roughly the inverter current limit.

Passes if pandapower is within TOLERANCE of (hand + inverter contribution).
"""

import warnings
warnings.filterwarnings("ignore")
import math
import pandapower.shortcircuit as sc
from network import build_network, load_params, inverter_fault_current_ka

# ---- hand calculation results, PCC bus, grid-connected, max case ----------
HAND_3PH_GRID_ONLY_A = 7022.5     # from hand_calculation.md, section 4
HAND_1PH_GRID_ONLY_A = 7257.0     # from hand_calculation.md, section 6
TOLERANCE = 0.02                  # 2 %


def model_pcc(p, fault):
    net = build_network(p, islanded=False, tiers=("1",))
    sc.calc_sc(net, fault=fault, case="max")
    idx = net.bus.index[net.bus.name == "pcc"][0]
    return net.res_bus_sc.loc[idx, "ikss_ka"] * 1000


def main():
    p = load_params()
    inv_a = inverter_fault_current_ka(p, p["lv"]["vn_kv"]) * 1000

    checks = [
        ("3ph", HAND_3PH_GRID_ONLY_A),
        ("1ph", HAND_1PH_GRID_ONLY_A),
    ]
    all_ok = True
    print(f"Inverter contribution added by the model: ~{inv_a:.0f} A\n")
    for fault, hand in checks:
        model = model_pcc(p, fault)
        expected = hand + inv_a          # arithmetic sum; true phasor sum is slightly less
        err = abs(model - expected) / expected
        ok = err <= TOLERANCE
        all_ok &= ok
        print(f"PCC {fault}:  hand (grid only) {hand:7.1f} A   "
              f"+ inverters ≈ {expected:7.1f} A   model {model:7.1f} A   "
              f"diff {err*100:4.1f}%   {'OK' if ok else 'FAIL'}")

    print()
    if all_ok:
        print("Cross-check PASSED — hand calculation and pandapower agree.")
    else:
        raise SystemExit("Cross-check FAILED — revisit params.json or the hand calculation.")


if __name__ == "__main__":
    main()
