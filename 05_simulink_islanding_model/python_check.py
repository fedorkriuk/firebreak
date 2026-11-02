"""Python check of the Simulink islanding model (build_firebreak_microgrid_v4.m).
Same blocks and logic: grid step sources, PV lookup, SOC integrator with clamps (20-100 %), MG controller
(P_bat = P_load - P_solar, gated by island_active via a one-step Memory), droop V/f model
(V = min(1, SOC/0.30), f = 50 - 0.004*(P_load - P_bat)), ROCOF = df/dt, and the 4-state islanding FSM.
Version 4: Tier 1 load profile and winter solar from Scene 3 (82 kWh/day), 48 h run with the grid
lost 17:00 day 1 and back 17:00 day 2, battery discharge lowers SOC, and the state machine sees grid
V/f while the PCC is closed. Run: python python_check.py  -> results_48h.csv, results_48h.json, results_48h.png"""
import json
from pathlib import Path
import numpy as np, pandas as pd

HERE = Path(__file__).resolve().parent; SIM = HERE.parent / "03_python_simulation"
BAT_KWH, SOC_MIN, SOC_MAX = 80.0, 0.20, 1.0
LOAD_KW = {"Telecom_Tower": 47.3 / 24, "Health_Clinic": 20.1 / 24, "Fire_Station": 11.4 / 24, "Water_Pumping": 2.9 / 24}
P_LOAD = sum(LOAD_KW.values())
T_FAIL, T_RET, T_END, DT = 17 * 3600, 41 * 3600, 48 * 3600, 1.0

a3 = pd.read_csv(SIM / "sim_act3.csv")                      # minute steps from 17:00, 24 h
pv_by_clock = np.zeros(1440); pv_by_clock[(a3.clock_min.values.astype(int)) % 1440] = a3.pv.values
t1_by_clock = np.zeros(1440); t1_by_clock[(a3.clock_min.values.astype(int)) % 1440] = a3.t1.values   # Scene 3 Tier 1 profile
def p_load(t):
    return t1_by_clock[int(t // 60) % 1440]
def p_solar(t):
    return pv_by_clock[int(t // 60) % 1440]

def fsm_step(state, V, f, rocof, fire, Vg, fg):
    loss = (V < 0.85 or V > 1.10) or (f < 49.0 or f > 51.0) or abs(rocof) > 1.0 or fire
    grid_ok = 0.95 < Vg < 1.05 and 49.5 < fg < 50.5
    resync_ok = grid_ok and abs(V - Vg) < 0.05 and abs(f - fg) < 0.10 and not fire
    if state == 0 and loss: state = 1
    elif state == 1 and grid_ok and not fire: state = 2
    elif state == 2: state = 3 if resync_ok else (1 if (not grid_ok or fire) else 2)
    elif state == 3: state = 1 if loss else 0
    return state

n = int(T_END / DT); t = np.arange(n) * DT
out = {k: np.zeros(n) for k in ["soc", "pv", "pload", "pbat", "v", "f", "state", "pcc"]}
soc_int, state, island_mem, f_prev = 1.0, 0, 0.0, 50.0
for i in range(n):
    ti = t[i]; grid_up = ti < T_FAIL or ti >= T_RET
    Vg, fg = (1.0, 50.0) if grid_up else (0.0, 0.0)
    ps = p_solar(ti); pl = p_load(ti)
    pbat = min(pl - ps, 100.0) * island_mem                # MG_Controller (gated by delayed island_active)
    soc = min(max(soc_int, SOC_MIN), SOC_MAX)                  # Battery_Model clamps (output only)
    Vi = min(1.0, soc / 0.30); fi = 50.0 - 0.004 * (pl - pbat)
    pcc_closed = state != 1
    V, f = (Vg, fg) if pcc_closed and state in (0, 3) else (Vi, fi)   # PCC closed: relay sees the grid
    rocof = (f - f_prev) / DT if i else 0.0; f_prev = f
    state = fsm_step(state, V, f, rocof, False, Vg, fg)
    island_mem = 1.0 if state in (1, 2) else 0.0               # Memory block -> next step
    soc_int -= pbat * DT / (BAT_KWH * 3600)                    # discharge lowers SOC
    soc_int = min(soc_int, SOC_MAX)                            # no wind-up above full
    for k, v in zip(["soc", "pv", "pload", "pbat", "v", "f", "state", "pcc"], [soc, ps, pl, pbat, V, f, state, float(state != 1)]):
        out[k][i] = v
df = pd.DataFrame(out); df.insert(0, "t_h", t / 3600)
df.iloc[::60].to_csv(HERE / "results_48h.csv", index=False)
isl = (df.state == 1)
i_min = df.soc[isl].idxmin()
meta = dict(load_kWh_island=round(df.pload[isl].sum()*DT/3600, 1), soc_min=round(df.soc.min() * 100, 1), t_soc_min_h=round(df.t_h[i_min], 2),
            soc_end_island=round(df.soc[df.t_h < 41].iloc[-1] * 100, 1),
            t_island=float(df.t_h[df.state == 1].iloc[0]), t_reconnect=float(df.t_h[(df.state == 3)].iloc[0]),
            v_min=round(df.v[isl].iloc[60:].min(), 3), f_min=round(df.f[isl].iloc[60:].min(), 3), soc_min_usable=round((df.soc.min()-0.2)/0.8*100, 1))
json.dump(meta, open(HERE / "results_48h.json", "w"), indent=1); print(meta)

# ---------- plot
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
OUT = HERE
BG, PANEL, TXT, MUTED, GRIDC = "#0B1020", "#121A2E", "#E8ECF4", "#8A96B0", "#24304D"
PV, BAT, LOAD, CYAN, PURP, AMBER, ALERT = "#FFC23D", "#2EE6A6", "#FF6B8B", "#4CC9F0", "#B388FF", "#FF9F1C", "#FF3B3B"
# ---------- results figure
d = pd.read_csv(HERE / "results_48h.csv"); m = meta
a3 = pd.read_csv(SIM / "sim_act3.csv"); ours_t = 17 + a3.minute.values / 60; ours_soc = 0.2 + 0.8 * a3.soc.values / 100
f, ax = plt.subplots(4, 1, figsize=(11, 10.5), dpi=180, facecolor=PANEL, sharex=True, gridspec_kw=dict(height_ratios=[1.2, 1.1, 1, 0.8]))
for a in ax:
    a.set_facecolor(PANEL); [sp.set_visible(False) for sp in a.spines.values()]
    a.tick_params(colors=MUTED); a.grid(color=GRIDC, lw=0.8); a.yaxis.label.set_color(MUTED)
    a.axvspan(17, 41, color=BAT, alpha=0.06, lw=0)
x = d.t_h
ax[0].plot(x, d.pload, color=LOAD, lw=1.8, label="Tier 1 load"); ax[0].plot(x, d.pv, color=PV, lw=1.8, label="Solar available")
ax[0].plot(x, d.pbat, color=BAT, lw=1.8, label="Battery (+ discharge)"); ax[0].axhline(0, color=MUTED, lw=0.8)
ax[0].set_ylabel("kW"); ax[0].legend(frameon=False, labelcolor=TXT, ncol=1, loc="lower left", fontsize=10.5)
ax[0].set_title("Power flows", color=TXT, fontsize=13, loc="left")
ax[1].plot(x, d.soc * 100, color=PURP, lw=2.4, label="Simulink model logic (v4)")
ax[1].plot(ours_t, ours_soc * 100, color=CYAN, lw=1.6, ls="--", label="Our Python model, Scene 3")
ax[1].axhline(20, color=ALERT, lw=1, ls=":"); ax[1].text(47.7, 22, "20% floor (80% depth of discharge)", color=ALERT, fontsize=10, ha="right")
i = d.soc.idxmin(); ax[1].scatter([x[i]], [d.soc[i] * 100], color=AMBER, zorder=5, s=40)
ax[1].text(x[i] + 0.6, d.soc[i] * 100 - 9, f"lowest {m['soc_min']:.1f}% at 06:46", color=AMBER, fontsize=11, fontweight="bold")
ax[1].set_ylim(0, 105); ax[1].set_ylabel("SOC (% of 80 kWh)"); ax[1].legend(frameon=False, labelcolor=TXT, loc="center left", fontsize=10.5)
ax[1].set_title("Battery state of charge", color=TXT, fontsize=13, loc="left")
v = d.v.copy(); fq = d.f.copy()
ax[2].plot(x, v, color=CYAN, lw=1.8); ax[2].set_ylim(-0.05, 1.15); ax[2].set_ylabel("V (pu)")
a2 = ax[2].twinx(); a2.plot(x, fq, color=AMBER, lw=1.4); a2.set_ylim(49.9, 50.02); a2.set_ylabel("f (Hz)", color=AMBER)
a2.tick_params(colors=AMBER); [sp.set_visible(False) for sp in a2.spines.values()]
ax[2].set_title("Bus voltage (blue) and frequency (orange) seen by the state machine", color=TXT, fontsize=13, loc="left")
ax[2].annotate("grid lost: V and f drop,\nstate machine islands", (17, 0.02), (19.5, 0.35), color=TXT, fontsize=10, arrowprops=dict(arrowstyle="->", color=MUTED))
ax[3].step(x, d.state, color=CYAN, lw=2, where="post", label="state (0 grid, 1 island, 2 resync, 3 reconnect)")
ax[3].step(x, d.pcc * 3, color=BAT, lw=1.4, ls="--", where="post", label="PCC closed (x3)")
ax[3].set_yticks([0, 1, 2, 3]); ax[3].set_ylim(-0.3, 3.6); ax[3].legend(frameon=False, labelcolor=TXT, loc="center left", fontsize=10)
ax[3].set_title("Islanding state machine", color=TXT, fontsize=13, loc="left")
ticks = np.arange(0, 49, 4); ax[3].set_xticks(ticks); ax[3].set_xticklabels([f"{int(h % 24):02d}:00" for h in ticks]); ax[3].set_xlim(0, 48)
ax[3].set_xlabel("Day 1 00:00 to Day 2 24:00", color=MUTED)
for xx, lbl in ((17, "grid lost 17:00"), (41, "grid back 17:00 day 2")):
    for a in ax: a.axvline(xx, color=MUTED, ls="--", lw=0.9)
    ax[0].text(xx + 0.3, ax[0].get_ylim()[1] * 0.85, lbl, color=MUTED, fontsize=10)
f.tight_layout(); f.savefig(OUT / "results_48h.png", facecolor=PANEL); plt.close(f)

