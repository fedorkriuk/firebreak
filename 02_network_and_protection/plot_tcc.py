"""
plot_tcc.py — time–current curves with an automatic grading-margin check.

Reads relay_settings.json and fault_levels.csv. Produces:
    tcc_grid.png     group 1 curves, grid-connected fault levels marked
    tcc_island.png   group 2 curves, islanded fault level marked
    tcc_check.txt    the numerical check behind the plots

The check FAILS LOUDLY (non-zero exit) if any upstream–downstream pair grades
with less than the required margin at the coordination current.
"""

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent

INK, EMBER, GOLD, TEAL, GREY, MIST = "#141B2B", "#E8552F", "#F2A93B", "#2FA98C", "#6B7280", "#EDEFF2"
COLORS = {"R1": INK, "R2": EMBER, "R3": GOLD, "R4": TEAL, "R5": "#7C5CBF"}

plt.rcParams.update({
    "font.family": "DejaVu Sans", "axes.edgecolor": "#C9CDD4",
    "axes.spines.top": False, "axes.spines.right": False,
    "xtick.color": GREY, "ytick.color": GREY, "text.color": INK, "axes.labelcolor": INK,
})


def idmt(i, pickup, tms, k, a):
    m = np.asarray(i, dtype=float) / pickup
    with np.errstate(divide="ignore", invalid="ignore"):
        t = tms * k / (m ** a - 1)
    t[m <= 1.0] = np.inf
    return t


def draw(ax, relays, group, k, a, i_min, i_max, label_suffix=""):
    I = np.logspace(np.log10(i_min), np.log10(i_max), 600)
    for name in ["R1", "R2", "R3", "R4", "R5"]:
        g = relays.get(name, {}).get(group)
        if not g:
            continue
        t = idmt(I, g["pickup_a"], g["tms"], k, a)
        ax.loglog(I, t, lw=2.4, color=COLORS[name],
                  label=f"{name}  {relays[name]['location']}  "
                        f"(pickup {g['pickup_a']} A, TMS {g['tms']}){label_suffix}")
    ax.set_xlabel("Fault current  (A)")
    ax.set_ylabel("Operating time  (s)")
    ax.grid(which="both", color="#E6E8EC", lw=0.7)
    ax.set_ylim(0.02, 30)
    ax.set_xlim(i_min, i_max)


def main():
    cfg = json.load(open(HERE / "relay_settings.json"))
    relays, c = cfg["relays"], cfg["constants"]
    k, a, margin = c["k"], c["alpha"], c["grading_margin_s"]
    fl = pd.read_csv(HERE / "fault_levels.csv")

    def ik(bus, state, fault="3ph"):
        r = fl[(fl.bus == bus) & (fl.state == state) & (fl.fault == fault)]
        return float(r.ikss_a.iloc[0]) if not r.empty else math.nan

    report = []
    failed = False

    # ------------------------------------------------------------ grid plot
    fig, ax = plt.subplots(figsize=(9, 6.2), dpi=140)
    draw(ax, relays, "group1", k, a, 3, 20000)
    i_coord = cfg["coordination_current_a"]

    # fault level markers
    for bus, col in [("microgrid_bus", INK), ("water_pump", GOLD), ("telecom_tower", "#7C5CBF")]:
        x = ik(bus, "grid_connected")
        ax.axvline(x, color=col, ls=":", lw=1.2, alpha=0.7)

    # fault level labels along the bottom, staggered so they don't overlap
    for j, (bus, col) in enumerate([("water_pump", GOLD), ("telecom_tower", "#7C5CBF"), ("microgrid_bus", INK)]):
        x = ik(bus, "grid_connected")
        ax.text(x, 0.023 * (1.6 ** j), f"{bus} {x:,.0f} A", fontsize=7.5, color=col,
                ha="center", va="bottom", bbox=dict(fc="white", ec="none", pad=1))

    # grading arrows at the coordination current
    r1 = relays["R1"]["group1"]
    t1 = float(idmt([i_coord], r1["pickup_a"], r1["tms"], k, a)[0])
    for name in ["R2", "R3", "R4", "R5"]:
        g = relays[name]["group1"]
        tf = float(idmt([i_coord], g["pickup_a"], g["tms"], k, a)[0])
        ok = (t1 - tf) >= margin - 1e-9
        failed |= not ok
        report.append(f"GRID    {name}->R1 at {i_coord:>6.0f} A : "
                      f"t_{name}={tf:.3f}s  t_R1={t1:.3f}s  margin={t1-tf:.3f}s  "
                      f"{'OK' if ok else 'FAIL'} (need {margin})")
    ax.annotate("", xy=(i_coord, t1), xytext=(i_coord, min(
        float(idmt([i_coord], relays[n]["group1"]["pickup_a"], relays[n]["group1"]["tms"], k, a)[0])
        for n in ["R2", "R3", "R4", "R5"])),
        arrowprops=dict(arrowstyle="<->", color=EMBER, lw=2))
    ax.text(i_coord * 0.93, t1 * 1.6, f"grading\n≥ {margin} s", color=EMBER, fontsize=9,
            ha="right", fontweight="bold")

    # load current and inrush band
    ax.axvspan(3, 45, color=MIST, lw=0)
    ax.text(3.3, 0.025, "normal load\nrange", fontsize=8, color=GREY)
    ax.set_title("Setting group 1 — grid-connected", loc="left", fontsize=13, fontweight="bold", pad=10)
    ax.legend(frameon=True, framealpha=0.95, edgecolor="#E6E8EC", fontsize=8, loc="lower left",
              bbox_to_anchor=(0.19, 0.02))
    fig.tight_layout()
    fig.savefig(HERE / "tcc_grid.png", facecolor="white")
    plt.close(fig)

    # ---------------------------------------------------------- island plot
    fig, ax = plt.subplots(figsize=(9, 6.2), dpi=140)
    draw(ax, relays, "group2", k, a, 3, 400)
    i_isl = ik("microgrid_bus", "islanded")
    ax.axvline(i_isl, color=EMBER, ls="--", lw=2)
    ax.text(i_isl * 1.05, 20, f"inverter limit\n{i_isl:.0f} A — the most\ncurrent ANY fault\ncan draw", fontsize=8.5,
            color=EMBER, va="top", fontweight="bold")

    # what group 1 would have done — the point of the slide
    r3g1 = relays["R3"]["group1"]
    t_r3_g1 = float(idmt([i_isl], r3g1["pickup_a"], r3g1["tms"], k, a)[0])
    ax.loglog([i_isl], [t_r3_g1], "x", color=GOLD, ms=11, mew=2.5)
    ax.text(i_isl * 0.55, t_r3_g1 * 1.25,
            f"R3 on group 1 settings\nwould take {t_r3_g1:.1f} s\n(pickup {r3g1['pickup_a']} A)",
            fontsize=8, color=GOLD, ha="right")

    for name in ["R2", "R3", "R4", "R5"]:
        g = relays[name]["group2"]
        t = float(idmt([i_isl], g["pickup_a"], g["tms"], k, a)[0])
        sens = i_isl / g["pickup_a"]
        ok = sens >= c["min_sensitivity"]
        failed |= not ok
        report.append(f"ISLAND  {name} at {i_isl:>6.0f} A : pickup={g['pickup_a']}A  "
                      f"sensitivity={sens:.1f}x  t={t:.3f}s  {'OK' if ok else 'FAIL'}")

    ax.axvspan(3, 45, color=MIST, lw=0)
    ax.text(3.3, 0.025, "normal load\nrange", fontsize=8, color=GREY)
    ax.set_title("Setting group 2 — islanded (switched in by PCC 52b contact)",
                 loc="left", fontsize=13, fontweight="bold", pad=10)
    ax.legend(frameon=True, framealpha=0.95, edgecolor="#E6E8EC", fontsize=8, loc="lower left",
              bbox_to_anchor=(0.19, 0.02))
    fig.tight_layout()
    fig.savefig(HERE / "tcc_island.png", facecolor="white")
    plt.close(fig)

    # ------------------------------------------------------------------ report
    txt = "\n".join(report)
    (HERE / "tcc_check.txt").write_text(txt + "\n")
    print(txt)
    print("\nPlots: tcc_grid.png, tcc_island.png")
    if failed:
        print("\n*** COORDINATION CHECK FAILED — see lines marked FAIL ***")
        sys.exit(1)
    print("\nCoordination check PASSED.")


if __name__ == "__main__":
    main()
