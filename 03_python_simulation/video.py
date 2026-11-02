"""
video.py — renders the microgrid simulation (sim.py outputs) into an MP4 dashboard.

Segments rendered in parallel, then concatenated:
  00 intro · 10 card1 · 11 act1 · 20 card2 · 21 act2 · 30 card3 · 31 act3 · 40 card4 · 41 act4 · 99 outro

Usage:  python3 video.py            (renders everything → firebreak_simulation.mp4)
        python3 video.py act2       (one segment, for testing)
"""
import sys, json, math, subprocess
from pathlib import Path
from multiprocessing import Pool
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, Circle, Wedge
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from matplotlib.animation import FFMpegWriter
from matplotlib import font_manager

HERE = Path(__file__).resolve().parent
ICON = HERE / "icons"
SEG = HERE / "video_segments"; SEG.mkdir(exist_ok=True)
FPS = 25

for f in font_manager.findSystemFonts():
    if "Inter" in f:
        try: font_manager.fontManager.addfont(f)
        except Exception: pass
plt.rcParams.update({"font.family": "Inter", "font.size": 11, "axes.unicode_minus": False})

# ---------------------------------------------------------------- palette
BG, PANEL, PANEL2 = "#0B1020", "#121A2E", "#18223B"
TXT, MUTED, GRIDC = "#E8ECF4", "#8A96B0", "#24304D"
C_GRID, C_PV, C_BAT, C_LOAD = "#8FA3C7", "#FFC23D", "#2EE6A6", "#FF6B8B"
C_ALERT, C_CYAN, C_PURP, C_AMBER = "#FF3B3B", "#4CC9F0", "#B388FF", "#FF9F1C"
C_ON, C_OFF = "#2EE6A6", "#FF3B3B"

MODE_STYLE = {"GRID": ("GRID-CONNECTED", C_GRID), "LOST": ("GRID LOST", C_AMBER),
              "DETECTED": ("LOSS OF MAINS DETECTED", C_AMBER), "ISLAND": ("ISLANDED", C_BAT),
              "FAULT": ("FAULT IN ISLAND", C_ALERT), "CLEARED": ("ISLANDED — FAULT CLEARED", C_BAT),
              "WAIT": ("GRID RETURNED — CHECKING", C_CYAN), "SYNC": ("SYNCHRONISING", C_CYAN),
              "CLOSING": ("CLOSING PCC", C_CYAN), "RECON": ("RECONNECTED", C_GRID)}

EV = json.load(open(HERE / "sim_events.json"))
A1 = pd.read_csv(HERE / "sim_act1.csv"); A2 = pd.read_csv(HERE / "sim_act2.csv")
A3 = pd.read_csv(HERE / "sim_act3.csv"); A4 = pd.read_csv(HERE / "sim_act4.csv")
BUILD = ["fire_station", "water_pump", "health_clinic", "telecom_tower"]
BLABEL = {"fire_station": "Fire station", "water_pump": "Water pump",
          "health_clinic": "Health clinic", "telecom_tower": "Telecom tower"}
BICON = {"fire_station": "fire", "water_pump": "water", "health_clinic": "clinic", "telecom_tower": "tower"}
RELAY = {"fire_station": "R2", "water_pump": "R3", "health_clinic": "R4", "telecom_tower": "R5"}


def icon(name, zoom):
    return OffsetImage(plt.imread(ICON / f"{name}.png"), zoom=zoom)


def keymap(frac, keys):
    xs, ys = zip(*keys)
    return float(np.interp(frac, xs, ys))


# ================================================================ dashboard frame
class Dashboard:
    def __init__(self, act_no, act_title):
        self.fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor=BG)
        f = self.fig
        # header
        f.text(0.022, 0.955, "FIREBREAK MICROGRID", color=TXT, fontsize=22, fontweight="bold")
        f.text(0.022, 0.928, "Live simulation of our islanding design  ·  Team 10", color=MUTED, fontsize=12)
        f.text(0.335, 0.955, f"ACT {act_no}", color=C_CYAN, fontsize=13, fontweight="bold")
        f.text(0.335, 0.928, act_title, color=TXT, fontsize=14, fontweight="bold")
        self.clock = f.text(0.985, 0.950, "", color=TXT, fontsize=21, fontweight="bold", ha="right",
                            family="DejaVu Sans Mono")
        self.badge_ax = f.add_axes([0.648, 0.925, 0.172, 0.05]); self.badge_ax.axis("off")
        self.badge = FancyBboxPatch((0.02, 0.1), 0.96, 0.8, boxstyle="round,pad=0,rounding_size=0.35",
                                    transform=self.badge_ax.transAxes, fc=C_GRID, ec="none")
        self.badge_ax.add_patch(self.badge)
        self.badge_txt = self.badge_ax.text(0.5, 0.5, "", ha="center", va="center", color=BG,
                                            fontsize=13, fontweight="bold", transform=self.badge_ax.transAxes)
        f.text(0.022, 0.012, "Python average-value model of our design  ·  fault levels IEC 60909  ·  "
               "relay curves IEC 60255 (standard inverse)  ·  limits AS/NZS 4777.2",
               color=MUTED, fontsize=9.5)
        self._sld()
        self._kpis()
        self._log()

    # ---------------------------------------------------------- single-line diagram
    def _sld(self):
        ax = self.fig.add_axes([0.012, 0.40, 0.575, 0.505]); self.sld = ax
        ax.set_xlim(0, 100); ax.set_ylim(0, 60); ax.axis("off")
        ax.add_patch(FancyBboxPatch((0.5, 0.5), 99, 59, boxstyle="round,pad=0,rounding_size=2",
                                    fc=PANEL, ec="none"))
        self.island = FancyBboxPatch((37, 3), 61.5, 54, boxstyle="round,pad=0,rounding_size=2.5",
                                     fc="none", ec=C_BAT, lw=2.5, ls=(0, (6, 4)), alpha=0.0)
        ax.add_patch(self.island)
        self.island_lbl = ax.text(97.5, 55, "ISLAND", color=C_BAT, ha="right", fontsize=11,
                                  fontweight="bold", alpha=0)
        # grid
        ax.add_patch(FancyBboxPatch((3, 29), 9, 10, boxstyle="round,pad=0,rounding_size=1.5",
                                    fc=PANEL2, ec=C_GRID, lw=1.5))
        ax.add_artist(AnnotationBbox(icon("grid", 0.13), (7.5, 35), frameon=False))
        ax.text(7.5, 30.4, "GRID 11 kV", color=TXT, ha="center", fontsize=8.5, fontweight="bold")
        self.grid_box = ax.patches[-1]
        # transformer
        for dx in (0, 2.6):
            ax.add_patch(Circle((19 + dx, 34), 2.2, fc="none", ec=C_GRID, lw=1.6))
        ax.text(20.3, 28.3, "200 kVA\n11/0.4 kV", color=MUTED, ha="center", fontsize=7.5, va="top")
        self.grid_line1, = ax.plot([12, 16.8], [34, 34], color=C_GRID, lw=3)
        self.grid_line2, = ax.plot([23.8, 29.5], [34, 34], color=C_GRID, lw=3)
        # PCC breaker
        self.pcc = FancyBboxPatch((29.5, 31.5), 5, 5, boxstyle="round,pad=0,rounding_size=0.8",
                                  fc=C_ON, ec="none")
        ax.add_patch(self.pcc)
        self.pcc_txt = ax.text(32, 34, "", ha="center", va="center", color=BG, fontsize=8, fontweight="bold")
        ax.text(32, 39.2, "PCC", color=TXT, ha="center", fontsize=10, fontweight="bold")
        self.r1 = Circle((32, 27.5), 1.1, fc=C_ON, ec="none"); ax.add_patch(self.r1)
        ax.text(34, 27.5, "R1", color=MUTED, fontsize=8, va="center")
        self.pcc_line, = ax.plot([34.5, 40], [34, 34], color=C_GRID, lw=3)
        # bus
        ax.add_patch(Rectangle((40, 33), 56, 2, fc=TXT, ec="none"))
        ax.text(95.5, 36.2, "400 V microgrid bus", color=MUTED, ha="right", fontsize=8.5)
        # sources
        self.src = {}
        for key, x, col, lbl, sub in (("pv", 47, C_PV, "SOLAR PV", "30 kWp"),
                                      ("bat", 63, C_BAT, "BATTERY", "80 kWh · 20 kW")):
            ax.plot([x, x], [35, 44], color=col, lw=3)
            ax.add_patch(FancyBboxPatch((x - 6, 44), 12, 10, boxstyle="round,pad=0,rounding_size=1.5",
                                        fc=PANEL2, ec=col, lw=1.8))
            ax.add_artist(AnnotationBbox(icon("solar" if key == "pv" else "battery", 0.10), (x - 3, 49),
                                         frameon=False))
            ax.text(x + 0.2, 51.2, lbl, color=col, fontsize=8.5, fontweight="bold")
            ax.text(x + 0.2, 48.6, sub, color=MUTED, fontsize=7.5)
            self.src[key] = ax.text(x + 0.2, 45.6, "", color=TXT, fontsize=9, fontweight="bold",
                                    family="DejaVu Sans Mono")
        self.bat_mode = ax.text(63, 41.3, "", color=C_BAT, fontsize=7.5, ha="center", fontweight="bold")
        # soc bar
        ax.add_patch(Rectangle((70, 44.5), 1.6, 9, fc=GRIDC, ec="none"))
        self.socbar = Rectangle((70, 44.5), 1.6, 9, fc=C_BAT, ec="none"); ax.add_patch(self.socbar)
        # buildings
        self.bx = {}; self.bdots = {}; self.blamp = {}; self.relay = {}; self.bkw = {}
        for j, b in enumerate(BUILD):
            x = 47 + j * 13.5
            line, = ax.plot([x, x], [33, 21], color=C_LOAD, lw=2.6)
            r = FancyBboxPatch((x - 1.6, 26.0), 3.2, 3.2, boxstyle="round,pad=0,rounding_size=0.5",
                               fc=C_ON, ec="none"); ax.add_patch(r)
            ax.text(x + 2.2, 27.6, RELAY[b], color=MUTED, fontsize=8, va="center")
            box = FancyBboxPatch((x - 6, 6), 12, 15, boxstyle="round,pad=0,rounding_size=1.5",
                                 fc=PANEL2, ec=C_ON, lw=2.2); ax.add_patch(box)
            ax.add_artist(AnnotationBbox(icon(BICON[b], 0.12), (x, 15.6), frameon=False))
            ax.text(x, 10.4, BLABEL[b], color=TXT, ha="center", fontsize=8.6, fontweight="bold")
            self.bkw[b] = ax.text(x, 7.6, "", color=MUTED, ha="center", fontsize=8, family="DejaVu Sans Mono")
            lamp = Circle((x + 4.4, 19.0), 0.9, fc=C_ON, ec="none"); ax.add_patch(lamp)
            self.bx[b], self.relay[b], self.blamp[b] = box, r, lamp
            self.bdots[b] = line
        self.tier3 = ax.text(39.5, 55.6, "", color=C_AMBER, ha="left", fontsize=9, fontweight="bold")
        # flow dots
        self.links = {"grid": ((12, 34), (40, 34), C_GRID), "pv": ((47, 44), (47, 35), C_PV),
                      "bat": ((63, 44), (63, 35), C_BAT)}
        for j, b in enumerate(BUILD):
            x = 47 + j * 13.5
            self.links[b] = ((x, 33), (x, 21.2), C_LOAD)
        self.dots = {k: ax.scatter([], [], s=20, c=v[2], zorder=6, edgecolors="none")
                     for k, v in self.links.items()}
        self.phase = {k: 0.0 for k in self.links}
        # fault marker
        self.bolt = AnnotationBbox(icon("bolt", 0.11), (60.5 + 2.6, 24), frameon=False)
        self.bolt.set_visible(False); ax.add_artist(self.bolt)
        self.bolt_ring = Circle((63.1, 24), 2.4, fc=C_ALERT, ec="none", alpha=0.0, zorder=5)
        ax.add_patch(self.bolt_ring)

    def flows(self, powers, dt_vis):
        for k, ((x0, y0), (x1, y1), col) in self.links.items():
            p = powers.get(k, 0.0)
            if abs(p) < 0.05:
                self.dots[k].set_offsets(np.empty((0, 2))); continue
            n = 6 if k in ("grid",) else 4
            self.phase[k] = (self.phase[k] + np.sign(p) * dt_vis * (0.35 + 0.08 * min(abs(p), 12))) % 1.0
            s = (self.phase[k] + np.arange(n) / n) % 1.0
            pts = np.c_[x0 + (x1 - x0) * s, y0 + (y1 - y0) * s]
            self.dots[k].set_offsets(pts)
            self.dots[k].set_sizes(np.full(n, 18 + 9 * min(abs(p), 12)))

    def set_state(self, *, pcc_closed, grid_live, island, bat_mode, soc=None, pv=None, bat=None,
                  loads=None, on=None, relays=None, r1=None, tier3_shed=False, fault=False, pulse=0.0):
        self.pcc.set_facecolor(C_ON if pcc_closed else C_ALERT)
        self.pcc_txt.set_text("ON" if pcc_closed else "OFF")
        gc = C_GRID if grid_live else "#3A4560"
        for l in (self.grid_line1, self.grid_line2):
            l.set_color(gc)
        self.pcc_line.set_color(C_GRID if pcc_closed else "#3A4560")
        self.grid_box.set_edgecolor(gc)
        self.island.set_alpha(1.0 if island else 0.0); self.island_lbl.set_alpha(1.0 if island else 0)
        self.bat_mode.set_text(bat_mode)
        if soc is not None:
            self.socbar.set_height(9 * soc / 100)
            self.socbar.set_facecolor(C_BAT if soc > 35 else C_AMBER)
        if pv is not None: self.src["pv"].set_text(f"{pv:5.1f} kW")
        if bat is not None:
            self.src["bat"].set_text(f"{bat:+5.1f} kW")
        for b in BUILD:
            ok = True if on is None else on[b]
            self.bx[b].set_edgecolor(C_ON if ok else C_OFF)
            self.blamp[b].set_facecolor(C_ON if ok else C_OFF)
            if loads is not None:
                self.bkw[b].set_text(f"{loads[b]:4.2f} kW" if ok else "OFF")
            if relays is not None:
                self.relay[b].set_facecolor({"ok": C_ON, "pick": C_AMBER, "trip": C_ALERT}[relays[b]])
        if r1 is not None:
            self.r1.set_facecolor({"ok": C_ON, "pick": C_AMBER, "trip": C_ALERT, "off": "#3A4560"}[r1])
        self.tier3.set_text("TIER 3 SHED — critical loads only" if tier3_shed else "")
        self.bolt.set_visible(fault)
        self.bolt_ring.set_alpha(0.25 + 0.35 * pulse if fault else 0.0)

    # ---------------------------------------------------------- KPI tiles
    def _kpis(self):
        ax = self.fig.add_axes([0.600, 0.625, 0.388, 0.28]); ax.axis("off"); self.kax = ax
        ax.set_xlim(0, 3); ax.set_ylim(0, 2)
        self.kpi = {}
        names = [("f", "Frequency", "Hz"), ("v", "Voltage", "pu"), ("soc", "Battery charge", "%"),
                 ("pv", "Solar", "kW"), ("bat", "Battery", "kW"), ("load", "Load served", "kW")]
        for i, (k, lbl, unit) in enumerate(names):
            c, r = i % 3, 1 - i // 3
            ax.add_patch(FancyBboxPatch((c + 0.03, r + 0.05), 0.94, 0.9,
                                        boxstyle="round,pad=0,rounding_size=0.08", fc=PANEL, ec="none"))
            t_l = ax.text(c + 0.1, r + 0.78, lbl.upper(), color=MUTED, fontsize=10, fontweight="bold", va="center")
            t_v = ax.text(c + 0.1, r + 0.40, "—", color=TXT, fontsize=30, fontweight="bold", va="center",
                          family="DejaVu Sans Mono")
            t_u = ax.text(c + 0.92, r + 0.16, unit, color=MUTED, fontsize=11, ha="right")
            self.kpi[k] = (t_v, t_l, t_u)

    def set_kpi(self, k, val, fmt, color=TXT, label=None, unit=None):
        t_v, t_l, t_u = self.kpi[k]
        if unit is not None: t_u.set_text(unit)
        t_v.set_text("—" if val is None else fmt.format(val)); t_v.set_color(color)
        if label: t_l.set_text(label.upper())

    # ---------------------------------------------------------- event log
    def _log(self):
        ax = self.fig.add_axes([0.600, 0.40, 0.388, 0.215]); ax.axis("off"); self.lax = ax
        ax.set_xlim(0, 1); ax.set_ylim(0, 1)
        ax.add_patch(FancyBboxPatch((0.008, 0.02), 0.984, 0.96, boxstyle="round,pad=0,rounding_size=0.04",
                                    fc=PANEL, ec="none"))
        ax.text(0.035, 0.88, "EVENT LOG", color=MUTED, fontsize=10, fontweight="bold")
        self.log_lines = [ax.text(0.035, 0.73 - i * 0.135, "", color=TXT, fontsize=10.5, va="center")
                          for i in range(6)]

    def set_log(self, items):
        items = items[-6:]
        for i, l in enumerate(self.log_lines):
            if i < len(items):
                stamp, msg = items[i]
                newest = i == len(items) - 1
                l.set_text(f"{stamp}   {msg}")
                l.set_color(C_CYAN if newest else TXT); l.set_alpha(1.0 if newest else 0.75)
                l.set_fontweight("bold" if newest else "normal")
            else:
                l.set_text("")

    def set_header(self, clock, mode_key):
        self.clock.set_text(clock)
        lbl, col = MODE_STYLE[mode_key]
        self.badge.set_facecolor(col); self.badge_txt.set_text(lbl)

    def plot_axes(self):
        a = self.fig.add_axes([0.045, 0.075, 0.43, 0.285]); b = self.fig.add_axes([0.555, 0.075, 0.43, 0.285])
        for ax in (a, b):
            style(ax)
        return a, b


def style(ax):
    ax.set_facecolor(PANEL)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=10)
    ax.grid(color=GRIDC, lw=0.8)
    ax.yaxis.label.set_color(MUTED); ax.xaxis.label.set_color(MUTED)


def ptitle(ax, txt):
    ax.set_title(txt, loc="left", color=TXT, fontsize=12.5, fontweight="bold", pad=8)


import os, contextlib
PREVIEW = os.environ.get("PREVIEW")          # e.g. "0.1,0.4,0.8" → save PNGs at those fractions


class _Preview:
    def __init__(self): self.k = 0; self.fig = None; self.name = None
    @contextlib.contextmanager
    def saving(self, fig, path, dpi=100):
        self.fig, self.name, self.k = fig, Path(path).stem, 0
        yield self
    def grab_frame(self):
        self.k += 1


def writer():
    if PREVIEW:
        return _Preview()
    return FFMpegWriter(fps=FPS, codec="libx264", bitrate=9000,
                        extra_args=["-pix_fmt", "yuv420p", "-preset", "medium"])


def maybe_snap(w, k, n):
    if PREVIEW and isinstance(w, _Preview):
        for fr in PREVIEW.split(","):
            if k == int(float(fr) * (n - 1)):
                w.fig.savefig(SEG / f"preview_{w.name}_{fr}.png", dpi=50, facecolor=BG)


# ================================================================ ACT 1
def act1(name="11_act1"):
    d = Dashboard(1, "The grid goes down — the microgrid saves itself")
    ev = EV["act1"]["events"]; meta = EV["act1"]["meta"]
    a, b = d.plot_axes()
    t = A1.t.values
    ptitle(a, "Frequency at the microgrid bus"); a.set_xlim(0, 8); a.set_ylim(49.45, 50.18)
    a.axhspan(49.85, 50.15, color=C_BAT, alpha=0.07); a.set_xlabel("time (s)"); a.set_ylabel("Hz")
    a.plot(t, A1.f, color=C_CYAN, lw=1, alpha=0.12)
    lf, = a.plot([], [], color=C_CYAN, lw=2.6)
    ptitle(b, "Who supplies the power"); b.set_xlim(0, 8); b.set_ylim(-1.5, 12)
    b.set_xlabel("time (s)"); b.set_ylabel("kW")
    lg, = b.plot([], [], color=C_GRID, lw=2.4, label="Grid import")
    lp, = b.plot([], [], color=C_PV, lw=2.4, label="Solar")
    lb, = b.plot([], [], color=C_BAT, lw=2.4, label="Battery")
    ll, = b.plot([], [], color=C_LOAD, lw=2.4, label="Load")
    b.legend(loc="upper right", frameon=False, labelcolor=TXT, fontsize=10, ncol=4)
    cur_a = a.axvline(0, color=TXT, lw=1, alpha=0.4); cur_b = b.axvline(0, color=TXT, lw=1, alpha=0.4)
    marks = []
    seconds = 27
    n = seconds * FPS
    keys = [(0, 0), (0.12, 0.92), (0.62, 2.1), (1.0, 8.0)]
    w = writer()
    with w.saving(d.fig, str(SEG / f"{name}.mp4"), dpi=100):
        prev_ts = 0
        for k in range(n):
            ts = keymap(k / (n - 1), keys)
            i = min(int(ts / 1e-3), len(t) - 1)
            r = A1.iloc[i]
            lf.set_data(t[:i + 1], A1.f.values[:i + 1])
            for line, col in ((lg, "p_grid"), (lb, "p_bat"), (ll, "p_load")):
                line.set_data(t[:i + 1], A1[col].values[:i + 1])
            lp.set_data(t[:i + 1], np.full(i + 1, r.p_pv))
            cur_a.set_xdata([ts, ts]); cur_b.set_xdata([ts, ts])
            for (te, msg) in ev:
                if te <= ts and te not in [m[0] for m in marks] and "nadir" not in msg:
                    marks.append((te, a.axvline(te, color=C_AMBER, lw=1, ls="--", alpha=0.6)))
            mode = r["mode"]
            d.set_header(f"t = {ts:6.3f} s", {"GRID": "GRID", "LOST": "LOST", "DETECTED": "DETECTED",
                                              "ISLAND": "ISLAND"}[mode])
            island = not bool(r.pcc)
            loads = {bb: 0 for bb in BUILD}
            share = {"fire_station": 0.2, "water_pump": 0.06, "health_clinic": 0.34, "telecom_tower": 0.40}
            for bb in BUILD:
                loads[bb] = r.p_load * share[bb]
            d.set_state(pcc_closed=bool(r.pcc), grid_live=ts < meta["t_loss"], island=island,
                        bat_mode="GRID-FORMING" if mode == "ISLAND" else "grid-following",
                        soc=100, pv=r.p_pv, bat=r.p_bat, loads=loads,
                        relays={bb: "ok" for bb in BUILD}, r1="ok" if ts < meta["t_loss"] else "off",
                        tier3_shed=bool(r.shed))
            d.flows({"grid": r.p_grid, "pv": r.p_pv, "bat": r.p_bat, **loads}, dt_vis=1 / FPS)
            d.set_kpi("f", r.f, "{:6.2f}", C_AMBER if abs(r.f - 50) > 0.15 else TXT)
            d.set_kpi("v", r.v, "{:5.3f}")
            d.set_kpi("soc", 100, "{:4.0f}")
            d.set_kpi("pv", r.p_pv, "{:5.1f}"); d.set_kpi("bat", r.p_bat, "{:+5.1f}")
            d.set_kpi("load", r.p_load, "{:5.1f}")
            d.set_log([(f"{te:6.3f} s", m) for te, m in ev if te <= ts])
            w.grab_frame(); maybe_snap(w, k, n)
    plt.close(d.fig)


# ================================================================ ACT 2
def act2(name="21_act2"):
    d = Dashboard(2, "A fault inside the island — only the right relay trips")
    ev = EV["act2"]["events"]; meta = EV["act2"]["meta"]
    a, b = d.plot_axes()
    a.set_position([0.045, 0.075, 0.40, 0.285]); b.set_position([0.655, 0.075, 0.33, 0.285])
    m3 = EV["act3"]["meta"]
    t = A2.t.values
    ptitle(a, "Bus voltage and fault current (water-pump feeder)")
    a.set_xlim(0, 3); a.set_ylim(0, 1.15); a.set_xlabel("time (s)"); a.set_ylabel("Voltage (pu)")
    a2 = a.twinx(); style(a2); a2.grid(False); a2.set_ylim(0, 115); a2.set_ylabel("Current (A)")
    lv, = a.plot([], [], color=C_CYAN, lw=2.6, label="Bus voltage")
    li, = a2.plot([], [], color=C_ALERT, lw=2.6, label="R3 current")
    a.legend(handles=[lv, li], loc="upper right", frameon=False, labelcolor=TXT, fontsize=10, ncol=2)
    cur_a = a.axvline(0, color=TXT, lw=1, alpha=0.4)
    # relay race bars
    ptitle(b, "Relay timing race (bar full = trip)")
    rows = [("R2  Fire station", "prog_R2", C_ON), ("R3  Water pump", "prog_R3", C_ALERT),
            ("R4  Health clinic", "prog_R4", C_ON), ("R5  Telecom", "prog_R5", C_ON),
            ("R3 if grid settings were used", "prog_g1", C_PURP),
            ("Inverter self-protection (0.5 s)", "inv_cf", C_AMBER)]
    b.set_xlim(0, 1.0); b.set_ylim(-0.6, len(rows) - 0.4); b.invert_yaxis()
    b.set_yticks(range(len(rows))); b.set_yticklabels([r[0] for r in rows], color=TXT, fontsize=10.5)
    b.set_xticks([0, 0.25, 0.5, 0.75, 1.0]); b.set_xticklabels(["0", "25%", "50%", "75%", "TRIP"])
    b.grid(axis="y", visible=False)
    for j in range(len(rows)):
        b.barh(j, 1.0, color=GRIDC, height=0.55)
    bars = [b.barh(j, 0, color=r[2], height=0.55)[0] for j, r in enumerate(rows)]
    btxt = [b.text(0.985, j, "", color=TXT, fontsize=10, va="center", ha="right", fontweight="bold")
            for j in range(len(rows))]
    seconds = 20; n = seconds * FPS
    keys = [(0, 0), (0.10, 0.95), (0.70, 1.45), (1.0, 3.0)]
    w = writer()
    with w.saving(d.fig, str(SEG / f"{name}.mp4"), dpi=100):
        for k in range(n):
            ts = keymap(k / (n - 1), keys)
            i = min(int(ts / 1e-3), len(t) - 1); r = A2.iloc[i]
            lv.set_data(t[:i + 1], A2.v_bus.values[:i + 1]); li.set_data(t[:i + 1], A2.I_R3.values[:i + 1])
            cur_a.set_xdata([ts, ts])
            for j, row in enumerate(rows):
                v = float(r[row[1]])
                if row[1] in ("prog_g1", "inv_cf"):
                    v = float(r[row[1]])
                bars[j].set_width(v)
                if row[1] == "prog_R3" and r.trip_R3:
                    btxt[j].set_text(f"TRIPPED  {meta['t_op_g2']:.3f} s")
                elif row[1] == "inv_cf" and v >= 1:
                    btxt[j].set_text("inverter would trip → blackout")
                elif row[1] == "prog_g1" and v > 0:
                    btxt[j].set_text(f"needs {meta['t_op_g1']:.2f} s — too slow")
                elif row[1] in ("prog_R2", "prog_R4", "prog_R5") and ts > meta["t_fault"] + 0.05:
                    btxt[j].set_text("stays ON")
                else:
                    btxt[j].set_text("")
            fault = bool(r.fault)
            tripped = bool(r.trip_R3)
            mode = "FAULT" if fault else ("CLEARED" if tripped else "ISLAND")
            d.set_header(f"11:30 · {ts:5.3f} s", mode)
            relays = {bb: "ok" for bb in BUILD}
            if fault:
                relays["water_pump"] = "pick"
            if tripped:
                relays["water_pump"] = "trip"
            on = {bb: True for bb in BUILD}; on["water_pump"] = not tripped
            base = meta["run_kw"]
            loads = {bb: base[bb] * r.v_bus ** 2 for bb in BUILD}
            loads["water_pump"] += 5.6 * r.v_bus ** 2          # pump running in the solar window
            if tripped: loads["water_pump"] = 0
            flows = dict(loads)
            if fault:
                flows["water_pump"] = meta["p_fault_kw"] * (r.I_R3 / meta["i_lim"]) ** 2
            demand = sum(flows.values())
            pv_out = min(m3["pv_at_fault"], 0.6 * demand) if fault else min(m3["pv_at_fault"], demand)
            bat_out = demand - pv_out
            d.set_state(pcc_closed=False, grid_live=False, island=True, bat_mode="GRID-FORMING",
                        soc=m3["soc_at_fault"], pv=pv_out, bat=bat_out, loads=loads, on=on, relays=relays,
                        r1="off", tier3_shed=True, fault=fault, pulse=0.5 + 0.5 * math.sin(k * 0.9))
            d.flows({"grid": 0, "pv": pv_out, "bat": bat_out, **flows}, dt_vis=1 / FPS)
            d.set_kpi("f", 50.0 - (0.06 if fault else 0), "{:6.2f}")
            d.set_kpi("v", r.v_bus, "{:5.3f}", C_ALERT if r.v_bus < 0.85 else TXT)
            d.set_kpi("soc", m3["soc_at_fault"], "{:4.0f}")
            d.set_kpi("pv", r.I_R3, "{:5.0f}", C_ALERT if fault else TXT, label="R3 feeder current", unit="A")
            d.set_kpi("bat", r.inv_i, "{:5.0f}", C_AMBER if r.inv_i > 90 else TXT, label="Inverter current", unit="A")
            d.set_kpi("load", sum(loads.values()), "{:5.1f}")
            d.set_log([(f"{te:5.3f} s", m) for te, m in ev if te <= ts])
            w.grab_frame(); maybe_snap(w, k, n)
    plt.close(d.fig)


# ================================================================ ACT 3
def act3(name="31_act3"):
    d = Dashboard(3, "24 hours on its own — solar by day, battery by night")
    ev = EV["act3"]["events"]; meta = EV["act3"]["meta"]
    a, b = d.plot_axes()
    x = A3.minute.values / 60.0
    ticks = np.arange(0, 25, 3)
    lbls = [f"{(17 + int(h)) % 24:02d}:00" for h in ticks]
    ptitle(a, "Power over 24 hours")
    a.set_xlim(0, 24); a.set_ylim(0, 15); a.set_xticks(ticks); a.set_xticklabels(lbls); a.set_ylabel("kW")
    for s0, s1 in ((1, 13.5),):
        a.axvspan(s0, s1, color="#000000", alpha=0.18, lw=0)
    a.text(7, 14, "NIGHT — battery only", color=MUTED, ha="center", fontsize=10)
    fills = {}
    lpv, = a.plot([], [], color=C_PV, lw=2.4, label="Solar")
    lt1, = a.plot([], [], color=C_LOAD, lw=2.0, label="Critical load (Tier 1)")
    lt2, = a.plot([], [], color=C_PURP, lw=2.0, label="Deferred load (pump, Tier 2)")
    a.legend(loc="upper left", frameon=False, labelcolor=TXT, fontsize=10)
    ptitle(b, "Battery state of charge")
    b.set_xlim(0, 24); b.set_ylim(0, 105); b.set_xticks(ticks); b.set_xticklabels(lbls); b.set_ylabel("%")
    b.axhspan(0, 20, color=C_ALERT, alpha=0.08)
    b.text(23.6, 8, "reserve", color=C_ALERT, ha="right", fontsize=10, alpha=0.8)
    ls, = b.plot([], [], color=C_BAT, lw=3)
    minmark = b.scatter([], [], s=90, c=C_AMBER, zorder=5)
    mintxt = b.text(0, 0, "", color=C_AMBER, fontsize=11, fontweight="bold")
    cur_a = a.axvline(0, color=TXT, lw=1, alpha=0.4); cur_b = b.axvline(0, color=TXT, lw=1, alpha=0.4)
    seconds = 32; n = seconds * FPS
    i_min = int(np.argmin(A3.soc.values))
    w = writer()
    with w.saving(d.fig, str(SEG / f"{name}.mp4"), dpi=100):
        for k in range(n):
            i = int(k / (n - 1) * (len(A3) - 1)); r = A3.iloc[i]
            cm = int(r.clock_min)
            lpv.set_data(x[:i + 1], A3.pv.values[:i + 1]); lt1.set_data(x[:i + 1], A3.t1.values[:i + 1])
            lt2.set_data(x[:i + 1], A3.t2.values[:i + 1]); ls.set_data(x[:i + 1], A3.soc.values[:i + 1])
            for key in list(fills):
                fills.pop(key).remove()
            fills["pv"] = a.fill_between(x[:i + 1], 0, A3.pv.values[:i + 1], color=C_PV, alpha=0.18, lw=0)
            fills["s"] = b.fill_between(x[:i + 1], 0, A3.soc.values[:i + 1], color=C_BAT, alpha=0.12, lw=0)
            cur_a.set_xdata([x[i]] * 2); cur_b.set_xdata([x[i]] * 2)
            if i >= i_min:
                minmark.set_offsets([[x[i_min], A3.soc.values[i_min]]])
                mintxt.set_position((x[i_min] + 0.4, A3.soc.values[i_min] - 9))
                mintxt.set_text(f"lowest {meta['soc_min']:.0f}% at {meta['t_min']}")
            pump_dead = 690 <= cm < 735
            loads = {bb: float(r[f"L_{bb}"]) for bb in BUILD}
            loads["water_pump"] += r.t2 * 0.9
            on = {bb: True for bb in BUILD}; on["water_pump"] = not pump_dead
            mode = "ISLAND"
            d.set_header(f"{cm // 60:02d}:{cm % 60:02d}", mode)
            d.set_state(pcc_closed=False, grid_live=False, island=True, bat_mode="GRID-FORMING",
                        soc=r.soc, pv=r.pv_used, bat=r.p_bat, loads=loads, on=on,
                        relays={bb: ("trip" if (bb == "water_pump" and pump_dead) else "ok") for bb in BUILD},
                        r1="off", tier3_shed=True)
            d.flows({"grid": 0, "pv": r.pv_used, "bat": r.p_bat, **loads}, dt_vis=1 / FPS)
            d.set_kpi("f", 50.0 + 0.01 * math.sin(k / 7), "{:6.2f}")
            d.set_kpi("v", 1.0 - 0.004 * math.sin(k / 11), "{:5.3f}")
            d.set_kpi("soc", r.soc, "{:4.0f}", C_AMBER if r.soc < 35 else C_BAT)
            d.set_kpi("pv", r.pv_used, "{:5.1f}"); d.set_kpi("bat", r.p_bat, "{:+5.1f}")
            d.set_kpi("load", r.t1 + r.t2, "{:5.1f}")
            d.set_log([("", m) if m[:2].isdigit() else ("17:00", m) for te, m in ev if te <= i])
            w.grab_frame(); maybe_snap(w, k, n)
    plt.close(d.fig)


# ================================================================ ACT 4
def act4(name="41_act4"):
    d = Dashboard(4, "The grid comes back — match it, then reconnect")
    ev = EV["act4"]["events"]; meta = EV["act4"]["meta"]
    fig = d.fig
    a = fig.add_axes([0.075, 0.085, 0.23, 0.255], projection="polar")
    a.set_facecolor(PANEL); a.tick_params(colors=MUTED, labelsize=9); a.grid(color=GRIDC)
    a.set_yticklabels([]); a.set_theta_zero_location("N"); a.set_theta_direction(-1)
    a.set_title("Sync scope — angle between island and grid", color=TXT, fontsize=12, fontweight="bold",
                loc="left", pad=14)
    win = np.radians(np.linspace(-10, 10, 30))
    a.fill_between(win, 0, 1.0, color=C_BAT, alpha=0.25)
    a.set_ylim(0, 1.05)
    grid_vec, = a.plot([0, 0], [0, 1.0], color=C_GRID, lw=4, solid_capstyle="round")
    isl_vec, = a.plot([0, 0], [0, 0.9], color=C_CYAN, lw=4, solid_capstyle="round")
    fig.text(0.04, 0.038, "grey = grid   ·   cyan = island (turns green inside ±10°)", color=MUTED, fontsize=10)
    b = fig.add_axes([0.40, 0.075, 0.585, 0.285]); style(b)
    ptitle(b, "Phase angle difference — close only inside the ±10° window")
    t = A4.t.values
    b.set_xlim(0, 14); b.set_ylim(-185, 185); b.set_yticks([-180, -90, -10, 10, 90, 180])
    b.axhspan(-10, 10, color=C_BAT, alpha=0.18); b.set_xlabel("time (s)"); b.set_ylabel("Δθ (degrees)")
    lth, = b.plot([], [], color=C_CYAN, lw=2.6)
    cur_b = b.axvline(0, color=TXT, lw=1, alpha=0.4)
    close_mark = b.axvline(meta["t_close"], color=C_BAT, lw=2, alpha=0.0)
    seconds = 22; n = seconds * FPS
    keys = [(0, 0), (0.30, 5.0), (0.70, 8.6), (1.0, 14.0)]
    w = writer()
    with w.saving(fig, str(SEG / f"{name}.mp4"), dpi=100):
        for k in range(n):
            ts = keymap(k / (n - 1), keys)
            i = min(int(ts / 1e-3), len(t) - 1); r = A4.iloc[i]
            th = math.radians(r.dtheta)
            isl_vec.set_data([th, th], [0, 0.9]); isl_vec.set_color(C_BAT if abs(r.dtheta) < 10 else C_CYAN)
            lth.set_data(t[:i + 1], A4.dtheta.values[:i + 1]); cur_b.set_xdata([ts, ts])
            close_mark.set_alpha(0.8 if ts >= meta["t_close"] else 0.0)
            m = r["mode"]
            mode = {"WAIT": "WAIT", "SYNC": "SYNC", "CLOSING": "CLOSING", "GRID": "RECON"}[m]
            grid_live = ts >= meta["t_ret"]
            recon = m == "GRID"
            d.set_header(f"Day 2 · {ts:5.2f} s", mode)
            l3_on = bool(r.tier3)
            share = {"fire_station": 0.2, "water_pump": 0.06, "health_clinic": 0.34, "telecom_tower": 0.40}
            tot = 4.3 + (5.7 if l3_on else 0)
            loads = {bb: tot * share[bb] for bb in BUILD}
            pv = 3.6
            if recon:
                bat = -5.0 * (1 - r.p_bat / 4.3)            # starts recharging from the grid
                grid = tot - pv - bat
            else:
                bat = tot - pv; grid = 0.0
            soc_now = EV["act3"]["meta"]["soc_end"]
            d.set_state(pcc_closed=recon, grid_live=grid_live, island=not recon,
                        bat_mode="GRID-FORMING" if not recon else ("grid-following" if ts > meta["t_close"] + 4 else "handing over"),
                        soc=soc_now, pv=pv, bat=bat,
                        loads=loads, relays={bb: "ok" for bb in BUILD}, r1="ok" if recon else ("pick" if grid_live else "off"),
                        tier3_shed=not l3_on)
            d.flows({"grid": grid, "pv": pv, "bat": bat, **loads}, dt_vis=1 / FPS)
            d.set_kpi("f", r.f_isl, "{:6.3f}", label="Island frequency", unit="Hz")
            d.set_kpi("v", r.f_grid, "{:6.3f}", C_GRID, label="Grid frequency", unit="Hz")
            d.set_kpi("soc", abs(r.dtheta), "{:5.1f}", C_BAT if abs(r.dtheta) < 10 else C_CYAN,
                      label="Angle difference", unit="deg")
            d.set_kpi("pv", grid, "{:5.1f}", label="Grid import", unit="kW")
            d.set_kpi("bat", bat, "{:+5.1f}")
            d.set_kpi("load", tot, "{:5.1f}")
            d.set_log([(f"{te:5.2f} s", mm) for te, mm in ev if te <= ts])
            w.grab_frame(); maybe_snap(w, k, n)
    plt.close(fig)


# ================================================================ outro
def outro(name="99_outro", seconds=8):
    m1, m2, m3, m4 = (EV[k]["meta"] for k in ("act1", "act2", "act3", "act4"))
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor=BG)
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off"); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.text(0.06, 0.86, "RESULTS", color=C_CYAN, fontsize=24, fontweight="bold")
    ax.text(0.06, 0.78, "What the simulation proves", color=TXT, fontsize=44, fontweight="bold")
    stats = [(f"{m1['open_ms']:.0f} ms", "grid loss → PCC open", "limit 2 s (AS/NZS 4777.2)", C_CYAN),
             (f"{m1['f_nadir']:.2f} Hz", "lowest frequency", "stays well above 47.5 Hz", C_PV),
             (f"{m2['t_op_g2']:.2f} s", "R3 trips the faulted feeder", "the 3 other buildings stay on", C_ALERT),
             (f"{m3['soc_min']:.0f}%", "lowest battery charge", "never ran out in 24 h", C_BAT),
             (f"{m4['close_angle']:.0f}°", "reconnection angle", "window ±10°", C_PURP),
             (f"{m3['e_t1']:.0f} kWh", "critical energy delivered", "fire · water · clinic · telecom", C_LOAD)]
    arts = []
    for i, (big, lbl, sub, col) in enumerate(stats):
        c, rr = i % 3, i // 3
        x0, y0 = 0.06 + c * 0.30, 0.42 - rr * 0.30
        p = FancyBboxPatch((x0, y0), 0.27, 0.24, boxstyle="round,pad=0,rounding_size=0.015",
                           fc=PANEL, ec="none", alpha=0); ax.add_patch(p)
        t1 = ax.text(x0 + 0.02, y0 + 0.14, big, color=col, fontsize=46, fontweight="bold", alpha=0)
        t2 = ax.text(x0 + 0.02, y0 + 0.075, lbl, color=TXT, fontsize=18, alpha=0)
        t3 = ax.text(x0 + 0.02, y0 + 0.035, sub, color=MUTED, fontsize=14, alpha=0)
        arts.append((p, t1, t2, t3))
    n = int(seconds * FPS)
    w = writer()
    with w.saving(fig, str(SEG / f"{name}.mp4"), dpi=100):
        for k in range(n):
            for i, grp in enumerate(arts):
                a = min(1.0, max(0.0, (k - (0.3 + 0.35 * i) * FPS) / (0.4 * FPS)))
                for g in grp: g.set_alpha(a)
            w.grab_frame(); maybe_snap(w, k, n)
    plt.close(fig)


def simple_card(name, big, title, lines, accent=C_CYAN, seconds=3.2):
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor=BG)
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off"); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.add_patch(Circle((0.86, 0.80), 0.32, fc=accent, alpha=0.07, ec="none"))
    ax.add_patch(Circle((0.10, 0.12), 0.20, fc=C_PV, alpha=0.05, ec="none"))
    t_big = ax.text(0.08, 0.66, big, color=accent, fontsize=26, fontweight="bold", alpha=0)
    t_ttl = ax.text(0.08, 0.54, title, color=TXT, fontsize=54, fontweight="bold", alpha=0)
    t_ln = [ax.text(0.08, 0.43 - i * 0.065, l, color=MUTED, fontsize=23, alpha=0) for i, l in enumerate(lines)]
    n = int(seconds * FPS)
    w = writer()
    with w.saving(fig, str(SEG / f"{name}.mp4"), dpi=100):
        for k in range(n):
            a = min(1.0, k / (0.5 * FPS)); t_big.set_alpha(a); t_ttl.set_alpha(a)
            for i, l in enumerate(t_ln):
                l.set_alpha(min(1.0, max(0.0, (k - (0.35 + 0.3 * i) * FPS) / (0.4 * FPS))))
            w.grab_frame(); maybe_snap(w, k, n)
    plt.close(fig)


JOBS = {
    "00_intro": lambda: simple_card("00_intro", "TEAM 10 · FIREBREAK ENERGY SYSTEMS",
                                    "Keeping the lights on",
                                    ["A simulated microgrid for four critical buildings",
                                     "Fire station · Water pump · Health clinic · Telecom tower",
                                     "Solar 30 kWp  +  battery 80 kWh  +  one smart switch"], seconds=5),
    "10_card1": lambda: simple_card("10_card1", "ACT 1", "The grid goes down",
                                    ["17:00 on a bushfire day. The power line is switched off.",
                                     "Watch the system notice, disconnect and take over."], accent=C_AMBER),
    "11_act1": act1,
    "20_card2": lambda: simple_card("20_card2", "ACT 2", "A fault inside the island",
                                    ["11:30. A fault on the water-pump cable.",
                                     "Only 95 A is available — can the right relay still trip?"], accent=C_ALERT),
    "21_act2": act2,
    "30_card3": lambda: simple_card("30_card3", "ACT 3", "24 hours on its own",
                                    ["The whole night on battery, the day on solar.",
                                     "Does every critical load stay on?"], accent=C_BAT),
    "31_act3": act3,
    "40_card4": lambda: simple_card("40_card4", "ACT 4", "The grid comes back",
                                    ["The system matches the grid's frequency and angle,",
                                     "then reconnects by itself — nobody drives out there."], accent=C_CYAN),
    "41_act4": act4,
    "99_outro": outro,
}


def run(job):
    JOBS[job]()
    return job


if __name__ == "__main__":
    which = sys.argv[1:] or list(JOBS)
    with Pool(min(len(which), 6)) as p:
        for j in p.imap_unordered(run, which):
            print("done", j, flush=True)
    if not sys.argv[1:]:
        lst = SEG / "list.txt"
        lst.write_text("".join(f"file '{SEG / (j + '.mp4')}'\n" for j in sorted(JOBS)))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                        "-c", "copy", str(HERE / "firebreak_simulation.mp4")], check=True)
        print("written firebreak_simulation.mp4")
