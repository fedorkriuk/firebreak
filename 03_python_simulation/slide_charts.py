"""Static charts for the final deck, drawn from the simulation outputs (dark theme to match the video)."""
import json, math
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

HERE = Path(__file__).resolve().parent
OUT = HERE / "figures"; OUT.mkdir(exist_ok=True)
DATA = HERE.parent / "data"; PROT = HERE.parent / "02_network_and_protection"
for f in font_manager.findSystemFonts():
    if "Inter" in f:
        try: font_manager.fontManager.addfont(f)
        except Exception: pass
BG, PANEL, TXT, MUTED, GRIDC = "#0B1020", "#121A2E", "#E8ECF4", "#8A96B0", "#24304D"
C_GRID, C_PV, C_BAT, C_LOAD = "#8FA3C7", "#FFC23D", "#2EE6A6", "#FF6B8B"
C_ALERT, C_CYAN, C_PURP, C_AMBER = "#FF3B3B", "#4CC9F0", "#B388FF", "#FF9F1C"
plt.rcParams.update({"font.family": "Inter", "font.size": 13, "axes.unicode_minus": False})

EV = json.load(open(HERE / "sim_events.json"))
A1 = pd.read_csv(HERE / "sim_act1.csv"); A2 = pd.read_csv(HERE / "sim_act2.csv")
A3 = pd.read_csv(HERE / "sim_act3.csv"); A4 = pd.read_csv(HERE / "sim_act4.csv")


def fig(w, h):
    f, ax = plt.subplots(figsize=(w, h), dpi=200, facecolor=PANEL)
    style(ax); return f, ax


def style(ax):
    ax.set_facecolor(PANEL)
    for s in ax.spines.values(): s.set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=12); ax.grid(color=GRIDC, lw=0.8)
    ax.yaxis.label.set_color(MUTED); ax.xaxis.label.set_color(MUTED)


def save(f, name):
    f.tight_layout(pad=1.2); f.savefig(OUT / name, facecolor=PANEL); plt.close(f); print(name)


# ---- 1. grid loss: frequency
m = EV["act1"]["meta"]
f, ax = fig(7.6, 4.4)
win = A1[(A1.t >= 0.5) & (A1.t <= 5)]
ax.axhspan(49.85, 50.15, color=C_BAT, alpha=0.08)
ax.plot(win.t, win.f, color=C_CYAN, lw=3)
for t0, lbl, dy in ((m["t_loss"], "grid lost", 0.03), (m["t_open"], f"PCC open ({m['open_ms']:.0f} ms)", -0.05),
                    (m["t_shed"], "Tier 3 shed", -0.12)):
    ax.axvline(t0, color=C_AMBER, ls="--", lw=1.2, alpha=0.7)
nadir_t = float(A1.t[A1.f.idxmin()])
ax.scatter([nadir_t], [m["f_nadir"]], s=80, color=C_PV, zorder=5)
ax.annotate(f"lowest {m['f_nadir']:.2f} Hz", (nadir_t, m["f_nadir"]), (nadir_t + 0.35, 49.63),
            color=C_PV, fontsize=13, fontweight="bold", arrowprops=dict(arrowstyle="-", color=C_PV))
ax.text(m["t_loss"] - 0.05, 50.12, "grid lost", color=C_AMBER, ha="right", fontsize=11)
ax.text(2.4, 49.82, f"switch opened after {m['open_ms']:.0f} ms\nTier 3 loads shed after {(m['t_shed']-m['t_loss'])*1000:.0f} ms\nback to normal in about 1 s", color=C_AMBER, fontsize=12, va="top")
ax.set_ylim(49.5, 50.16); ax.set_xlim(0.5, 5); ax.set_xlabel("time (s)"); ax.set_ylabel("frequency (Hz)")
save(f, "c_grid_loss.png")

# ---- 2. 24 h island
m3 = EV["act3"]["meta"]
x = A3.minute.values / 60
ticks = np.arange(0, 25, 4); lbls = [f"{(17 + int(h)) % 24:02d}:00" for h in ticks]
f, (a, b) = plt.subplots(2, 1, figsize=(7.6, 5.4), dpi=200, facecolor=PANEL, sharex=True,
                         gridspec_kw=dict(height_ratios=[1.25, 1]))
for axx in (a, b): style(axx)
a.fill_between(x, 0, A3.pv, color=C_PV, alpha=0.25, lw=0); a.plot(x, A3.pv, color=C_PV, lw=2, label="Solar")
a.plot(x, A3.t1, color=C_LOAD, lw=1.8, label="Critical load")
a.plot(x, A3.t2, color=C_PURP, lw=1.8, label="Pump (runs on spare solar)")
a.set_ylabel("kW"); a.legend(frameon=False, labelcolor=TXT, fontsize=11, loc="upper left")
a.axvspan(0.8, 12.2, color="#000", alpha=0.18, lw=0); a.text(6.5, 6.5, "night: battery only", color=MUTED, ha="center", fontsize=11)
b.fill_between(x, 0, A3.soc, color=C_BAT, alpha=0.18, lw=0); b.plot(x, A3.soc, color=C_BAT, lw=2.6)
i = int(np.argmin(A3.soc)); b.scatter([x[i]], [A3.soc[i]], s=70, color=C_AMBER, zorder=5)
b.text(x[i] + 0.5, A3.soc[i] - 14, f"lowest {m3['soc_min']:.0f}% at {m3['t_min']}", color=C_AMBER, fontsize=12, fontweight="bold")
b.set_ylim(0, 105); b.set_ylabel("battery %"); b.set_xlim(0, 24); b.set_xticks(ticks); b.set_xticklabels(lbls)
save(f, "c_24h.png")

# ---- 3. relay race (final state)
m2 = EV["act2"]["meta"]
f, ax = fig(7.6, 4.2)
rows = [("R3 with our island settings", m2["t_op_g2"], C_BAT),
        ("Inverter's own protection", m2["inv_limit"], C_AMBER),
        ("R3 with normal grid settings", m2["t_op_g1"], C_PURP)]
for j, (lbl, v, c) in enumerate(rows):
    ax.barh(j, v, color=c, height=0.55)
    ax.text(v + 0.03, j, f"{v:.2f} s", color=TXT, va="center", fontsize=14, fontweight="bold")
ax.axvline(m2["inv_limit"], color=C_AMBER, ls="--", lw=1.4)
ax.text(m2["inv_limit"] + 0.02, -0.55, "inverter gives up here\n→ whole island goes dark", color=C_AMBER, fontsize=11, va="top")
ax.set_yticks(range(3)); ax.set_yticklabels([r[0] for r in rows], color=TXT, fontsize=13)
ax.invert_yaxis(); ax.set_xlim(0, 1.45); ax.set_xlabel("time to trip after the fault (s)"); ax.grid(axis="y", visible=False)
save(f, "c_relay_race.png")

# ---- 4. fault level collapse
fl = pd.read_csv(PROT / "fault_levels.csv"); d = fl[fl.fault == "3ph"]
buses = ["fire_station", "water_pump", "health_clinic", "telecom_tower"]
names = ["Fire\nstation", "Water\npump", "Health\nclinic", "Telecom\ntower"]
g = [float(d[(d.bus == b) & (d.state == "grid_connected")].ikss_a.iloc[0]) for b in buses]
isl = [float(d[(d.bus == b) & (d.state == "islanded")].ikss_a.iloc[0]) for b in buses]
f, ax = fig(7.6, 4.4); xx = np.arange(4); w = 0.38
ax.bar(xx - w / 2, g, w, color=C_GRID, label="Grid connected"); ax.bar(xx + w / 2, isl, w, color=C_ALERT, label="Islanded")
ax.set_yscale("log"); ax.set_ylim(30, 60000)
for k in range(4):
    ax.text(xx[k] - w / 2, g[k] * 1.15, f"{g[k]:,.0f}", ha="center", color=TXT, fontsize=11)
    ax.text(xx[k] + w / 2, isl[k] * 1.15, f"{isl[k]:.0f}", ha="center", color=C_ALERT, fontsize=11, fontweight="bold")
ax.set_xticks(xx); ax.set_xticklabels(names, color=TXT); ax.set_ylabel("fault current (A, log)")
ax.legend(frameon=False, labelcolor=TXT, loc="upper left", ncol=2); ax.grid(axis="x", visible=False)
save(f, "c_fault_levels.png")

# ---- 5. load by building
df = pd.read_csv(DATA / "critical_load_list.csv")
num = pd.to_numeric(df.rated_power_W, errors="coerce").fillna(0); qty = pd.to_numeric(df.quantity, errors="coerce").fillna(1)
duty = pd.to_numeric(df.duty_cycle_pct, errors="coerce").fillna(0); win = pd.to_numeric(df.window_hours, errors="coerce").fillna(0)
df["kwh"] = num * qty * duty / 100 * win / 1000
e = df[df.tier.astype(str) == "1"].groupby("building").kwh.sum().reindex(buses[::-1])
f, ax = fig(7.0, 4.0)
cols = [C_CYAN, C_LOAD, C_BAT, C_PV][::-1]
ax.barh(range(4), e.values, color=[C_PV, C_BAT, C_LOAD, C_CYAN][::-1], height=0.6)
for k, v in enumerate(e.values):
    ax.text(v + 0.8, k, f"{v:.0f} kWh", va="center", color=TXT, fontsize=13, fontweight="bold")
ax.set_yticks(range(4)); ax.set_yticklabels([n.replace("\n", " ") for n in names[::-1]], color=TXT)
ax.set_xlim(0, 60); ax.set_xlabel("critical energy per day (kWh)"); ax.grid(axis="y", visible=False)
save(f, "c_load_split.png")
