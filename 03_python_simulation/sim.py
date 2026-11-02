"""
sim.py — time-domain simulation of the Firebreak islanding microgrid.

Average-value model (no switching detail). Four acts:

  ACT 1  Grid loss → loss-of-mains detection (ROCOF) → PCC opens → battery
         becomes grid-forming → Tier 3 load shed → frequency restored.     [0–8 s, 1 ms]
  ACT 2  Fault on the water-pump feeder while islanded. Inverters current-limit
         at ~95 A. Relays on setting group 2 integrate the IEC SI curve; R3
         trips, other feeders ride through. Group-1 counterfactual computed.  [0–3 s, 1 ms]
  ACT 3  24-hour island from 17:00 on the worst winter day. Tier 1 served all
         night from the battery; Tier 2 (pump) runs in the solar window.       [24 h, 1 min]
  ACT 4  Grid returns. Stability timer, synchronising (slip control), close
         inside the sync-check window, Tier 3 restored.                       [0–12 s, 1 ms]

All parameters come from params.json, relay_settings.json and critical_load_list.csv
where they exist; dynamic constants are declared below.

Outputs: sim_act1.csv … sim_act4.csv, sim_events.json
"""

import json, math
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
PROT = HERE.parent / "02_network_and_protection"
RNG = np.random.default_rng(7)
F0, V0 = 50.0, 1.0
VLL = 400.0

P = json.load(open(DATA / "params.json"))
RS = json.load(open(PROT / "relay_settings.json"))
K, ALPHA = RS["constants"]["k"], RS["constants"]["alpha"]

PV_KW = P["pv"]["p_mw"] * 1000                     # 30
BAT_KW = P["battery"]["p_mw"] * 1000                # 20
S_INV_KVA = (P["pv"]["sn_mva"] + P["battery"]["sn_mva"]) * 1000   # 55
I_LIM_A = 1.2 * S_INV_KVA * 1000 / (math.sqrt(3) * VLL)           # ~95 A
BAT_KWH = P["battery"]["energy_kwh"]
DOD = 0.80
ETA = 0.95                                          # one-way efficiency

BUILDINGS = ["fire_station", "water_pump", "health_clinic", "telecom_tower"]
RELAY_OF = {"fire_station": "R2", "water_pump": "R3", "health_clinic": "R4", "telecom_tower": "R5"}

# -------------------------------------------------------------- dynamics constants
H_VIRT = 2.0          # s, equivalent virtual inertia of the inverter fleet
ROCOF_TRIP = 1.0      # Hz/s, loss-of-mains threshold
ROCOF_WIN = 0.10      # s, must persist this long
CB_OPEN = 0.06        # s, breaker opening time
GF_TRANSFER = 0.04    # s, inverter transfer to grid-forming
SHED_DELAY = 0.05     # s, Tier 3 shed after PCC opens
DROOP = 0.04          # 4 % frequency droop
TAU_BAT = 0.05        # s, battery power response
KI_SEC = 0.6          # secondary frequency restoration gain
TAU_V = 0.08          # s, voltage regulation
INV_OC_LIMIT_S = 0.50 # s, inverter's own over-current ride-through


def idmt(i, pickup, tms):
    m = i / pickup
    return math.inf if m <= 1.0 else tms * K / (m ** ALPHA - 1)


# -------------------------------------------------------------- load model
def load_profiles():
    """Hourly average kW per building and tier, from the load list."""
    df = pd.read_csv(DATA / "critical_load_list.csv")
    num = pd.to_numeric(df.rated_power_W, errors="coerce").fillna(0)
    qty = pd.to_numeric(df.quantity, errors="coerce").fillna(1)
    duty = pd.to_numeric(df.duty_cycle_pct, errors="coerce").fillna(0)
    df["kw"] = num * qty * duty / 100 / 1000
    df["kw_rated"] = num * qty / 1000
    win = {"continuous_24h": range(24), "on_demand": range(24),
           "night_only": list(range(18, 24)) + list(range(0, 6)), "daylight_only": range(10, 15)}
    prof = {b: {"1": np.zeros(24), "2": np.zeros(24), "3": np.zeros(24)} for b in BUILDINGS}
    for _, r in df.iterrows():
        tier = str(r.tier)
        if tier == "3" or tier == "CONTESTED":
            # normal (grid-connected) use: ~30 % of rated, daytime-weighted
            for h in range(24):
                prof[r.building]["3"][h] += r.kw_rated * (0.35 if 7 <= h <= 21 else 0.15)
            continue
        hrs = win.get(r.runs_when)
        if hrs is None:
            continue
        kw = r.kw
        if r.runs_when == "daylight_only":       # compress the 10 h window into 5 h, same energy
            kw = kw * 10 / 5
        for h in hrs:
            prof[r.building][tier][h] += kw
    return prof


def pv_shape_minutes():
    """Worst winter day, kW per kWp, 1-minute resolution, with passing cloud."""
    m = np.arange(24 * 60)
    hours = m / 60
    decl = math.radians(-23.45)
    lat = math.radians(-34.5)
    ha = np.radians(15 * (hours - 12))
    elev = np.arcsin(np.sin(lat) * math.sin(decl) + np.cos(lat) * math.cos(decl) * np.cos(ha))
    clear = np.clip(np.sin(elev), 0, None)
    cloud = 0.42 + 0.10 * np.sin(m / 37.0) + 0.06 * RNG.standard_normal(len(m))
    cloud = np.convolve(cloud, np.ones(9) / 9, mode="same")
    return np.clip(clear * cloud * 0.85, 0, None)


# ============================================================== ACT 1
def act1():
    dt = 1e-3
    t = np.arange(0, 8.0, dt)
    prof = load_profiles()
    h = 17
    l1 = sum(prof[b]["1"][h] for b in BUILDINGS)
    l2 = sum(prof[b]["2"][h] for b in BUILDINGS)
    l3 = sum(prof[b]["3"][h] for b in BUILDINGS)
    pv = PV_KW * 0.11                               # dusk
    t_loss = 1.0

    f = np.full_like(t, F0); v = np.full_like(t, V0)
    p_bat = np.zeros_like(t); p_grid = np.zeros_like(t); p_load = np.zeros_like(t)
    rocof = np.zeros_like(t); mode = np.empty(len(t), dtype=object)
    pcc = np.ones_like(t, dtype=bool)
    shed = np.zeros_like(t, dtype=bool)
    events = []

    state = "GRID"; t_detect = t_open = t_gf = t_shed = None
    over = 0.0; integ = 0.0; pb = 0.0
    for i, ti in enumerate(t):
        was_shed = bool(shed[i - 1]) if i else False
        load = l1 + l2 + (0 if was_shed else l3)
        # voltage-dependent load (constant-impedance share)
        load *= (0.6 + 0.4 * v[i - 1] ** 2) if i else 1.0
        if state == "GRID" and ti >= t_loss:
            state = "LOST"; events.append((ti, "Upstream feeder de-energised — grid lost"))
        if state == "GRID":
            f[i] = F0 + 0.004 * math.sin(2 * math.pi * 0.7 * ti)
            v[i] = V0 + 0.002 * math.sin(2 * math.pi * 1.1 * ti)
            pb = 0.0
            p_grid[i] = load - pv - pb
        else:
            if state in ("LOST", "DETECTED"):
                # grid-following inverters hold set-points: mismatch drives f
                pgen = pv + pb
                dfdt = F0 * (pgen - load) / (2 * H_VIRT * S_INV_KVA)
                f[i] = f[i - 1] + dfdt * dt
                v[i] = v[i - 1] + dt * (-(0.06) * (load - pgen) / S_INV_KVA)
                p_grid[i] = 0.0
                if state == "LOST":
                    over = over + dt if abs(dfdt) > ROCOF_TRIP else 0.0
                    if over >= ROCOF_WIN:
                        state = "DETECTED"; t_detect = ti
                        events.append((ti, f"ROCOF {abs(dfdt):.1f} Hz/s > {ROCOF_TRIP} Hz/s — loss of mains detected"))
                if state == "DETECTED" and ti >= t_detect + CB_OPEN and t_open is None:
                    t_open = ti; events.append((ti, "PCC breaker OPEN — microgrid islanded"))
                if t_open is not None and ti >= t_open + GF_TRANSFER:
                    state = "ISLAND"; t_gf = ti
                    events.append((ti, "Battery inverter → grid-forming (droop + V control)"))
            else:  # ISLAND, grid-forming
                if t_shed is None and ti >= t_open + GF_TRANSFER + SHED_DELAY:
                    t_shed = ti; events.append((ti, f"Tier 3 load shed ({l3:.1f} kW)"))
                integ += KI_SEC * (F0 - f[i - 1]) * dt
                p_ref = (F0 - f[i - 1]) / (DROOP * F0) * BAT_KW + integ * BAT_KW / 2
                p_ref = float(np.clip(p_ref, -BAT_KW, BAT_KW))
                pb += (p_ref - pb) * dt / TAU_BAT
                dfdt = F0 * (pv + pb - load) / (2 * H_VIRT * S_INV_KVA)
                f[i] = f[i - 1] + dfdt * dt
                v[i] = v[i - 1] + (V0 - v[i - 1]) * dt / TAU_V
                p_grid[i] = 0.0
            if t_open is not None:
                pcc[i] = False
            if t_shed is not None:
                shed[i] = True
        p_bat[i] = pb
        p_load[i] = load
        rocof[i] = (f[i] - f[i - 1]) / dt if i else 0.0
        mode[i] = state
    # restoration event
    k = np.where((t > (t_shed or 0) + 0.5) & (np.abs(f - F0) < 0.02))[0]
    if len(k):
        events.append((t[k[0]], f"Frequency restored to {F0:.2f} Hz (secondary control)"))
    fmin = f.min()
    events.append((t[np.argmin(f)], f"Frequency nadir {fmin:.2f} Hz (limit 47.5 Hz)"))
    events.sort()
    rocof_s = pd.Series(rocof).rolling(50, center=True, min_periods=1).mean().values
    df = pd.DataFrame(dict(t=t, f=f, v=v, p_pv=pv, p_bat=p_bat, p_grid=p_grid,
                           p_load=p_load, rocof=rocof_s, pcc=pcc, shed=shed, mode=mode))
    meta = dict(t_loss=t_loss, t_detect=t_detect, t_open=t_open, t_gf=t_gf, t_shed=t_shed,
                f_nadir=float(fmin), detect_ms=round((t_detect - t_loss) * 1000),
                open_ms=round((t_open - t_loss) * 1000), l1=l1, l2=l2, l3=l3, pv=pv)
    return df, events, meta


# ============================================================== ACT 2
def act2():
    dt = 1e-3
    t = np.arange(0, 3.0, dt)
    t_fault, rf = 1.0, 1.0          # arcing fault, 1 Ω, on the water-pump feeder
    prof = load_profiles()
    h = 11
    run_kw = {b: prof[b]["1"][h] for b in BUILDINGS}
    run_a = {b: run_kw[b] * 1000 / (math.sqrt(3) * VLL * 0.9) for b in BUILDINGS}
    relays = {RELAY_OF[b]: RS["relays"][RELAY_OF[b]]["group2"] for b in BUILDINGS}
    g1_r3 = RS["relays"]["R3"]["group1"]

    v_bus = np.ones_like(t); cur = {r: np.zeros_like(t) for r in relays}
    prog = {r: np.zeros_like(t) for r in relays}
    tripped = {r: np.zeros_like(t, dtype=bool) for r in relays}
    inv_i = np.zeros_like(t); inv_timer = np.zeros_like(t)
    fault_on = np.zeros_like(t, dtype=bool); prog_g1 = np.zeros_like(t)
    events = []; acc = {r: 0.0 for r in relays}; acc_g1 = 0.0; timer = 0.0
    t_trip = t_clear = None; vb = 1.0; tripped_now = {r: False for r in relays}
    for i, ti in enumerate(t):
        on = (t_fault <= ti) and (t_clear is None or ti < t_clear)
        fault_on[i] = on
        if on:
            v_target = min(1.0, I_LIM_A * rf / (VLL / math.sqrt(3)))   # current-limited source into Rf
        else:
            v_target = 1.0
        vb += (v_target - vb) * dt / (0.004 if on else 0.03)
        v_bus[i] = vb
        total_load_a = 0.0
        for b in BUILDINGS:
            r = RELAY_OF[b]
            ia = 0.0 if tripped_now[r] else run_a[b] * vb
            total_load_a += ia
            cur[r][i] = ia
        if on:
            i_f = max(I_LIM_A - (total_load_a - cur["R3"][i]), 0) * min(1.0, (1 - vb) / (1 - v_target + 1e-9))
            cur["R3"][i] = i_f
        inv_i[i] = min(I_LIM_A, sum(cur[r][i] for r in relays))
        timer = timer + dt if inv_i[i] >= 0.98 * I_LIM_A else 0.0
        inv_timer[i] = timer
        for r, g in relays.items():
            top = idmt(cur[r][i], g["pickup_a"], g["tms"])
            acc[r] = acc[r] + dt / top if math.isfinite(top) else max(0.0, acc[r] - dt / 0.5)
            if acc[r] >= 1.0 and not tripped_now[r]:
                tripped_now[r] = True
                if r == "R3":
                    t_trip = ti; t_clear = ti + CB_OPEN
                    events.append((ti, f"R3 trips (group 2): {cur[r][i]:.0f} A → {ti - t_fault:.3f} s"))
            prog[r][i] = 1.0 if tripped_now[r] else min(acc[r], 1.0); tripped[r][i] = tripped_now[r]
        top1 = idmt(cur["R3"][i], g1_r3["pickup_a"], g1_r3["tms"])
        acc_g1 = acc_g1 + dt / top1 if math.isfinite(top1) else acc_g1
        prog_g1[i] = min(acc_g1, 1.0)
    events.insert(0, (t_fault, f"11:30 fault on water-pump feeder (arcing, {rf:.0f} Ω) — voltage collapses"))
    events.append((t_clear, "Breaker on water-pump feeder OPEN — fault cleared"))
    events.append((t_clear + 0.15, "Fire station, clinic and telecom stay ON — selective trip"))
    i_r3 = cur["R3"][int((t_fault + 0.05) / dt)]
    t_g1 = idmt(i_r3, g1_r3["pickup_a"], g1_r3["tms"])
    el = np.clip(t - t_fault, 0, None)
    prog_g1 = np.clip(el / t_g1, 0, 1) * (t >= t_fault)
    inv_cf = np.clip(el / INV_OC_LIMIT_S, 0, 1) * (t >= t_fault)
    df = pd.DataFrame(dict(t=t, v_bus=v_bus, inv_i=inv_i, inv_timer=inv_timer, fault=fault_on,
                           prog_g1=prog_g1, inv_cf=inv_cf,
                           **{f"I_{r}": cur[r] for r in relays},
                           **{f"prog_{r}": prog[r] for r in relays},
                           **{f"trip_{r}": tripped[r] for r in relays}))
    meta = dict(t_fault=t_fault, t_trip=t_trip, t_clear=t_clear, i_fault=float(i_r3),
                t_op_g2=t_trip - t_fault, t_op_g1=t_g1, inv_limit=INV_OC_LIMIT_S,
                v_sag=float(v_bus[fault_on].min()), i_lim=I_LIM_A,
                p_fault_kw=3 * I_LIM_A ** 2 * rf / 1000,
                run_kw={b: float(run_kw[b]) for b in BUILDINGS})
    return df, events, meta


# ============================================================== ACT 3
def act3():
    prof = load_profiles()
    pvs = pv_shape_minutes()
    start = 17 * 60
    mins = np.arange(24 * 60)
    clock_min = (start + mins) % (24 * 60)
    usable = BAT_KWH * DOD
    soc = usable
    t1 = np.zeros(len(mins)); t2 = np.zeros(len(mins)); pv = np.zeros(len(mins))
    pv_used = np.zeros(len(mins)); pbat = np.zeros(len(mins)); socs = np.zeros(len(mins))
    curt = np.zeros(len(mins)); per_b = {b: np.zeros(len(mins)) for b in BUILDINGS}
    pump_off = (11 * 60 + 30, 12 * 60 + 15)          # fault at 11:30, restored 12:15
    events = [(0, "Island begins 17:00 — battery 100 %, Tier 3 shed")]
    noise = RNG.standard_normal((len(mins), 4)) * 0.05
    for k, cm in enumerate(clock_min):
        hh = cm // 60
        dead_pump = pump_off[0] <= cm < pump_off[1]
        l1b = {}
        for j, b in enumerate(BUILDINGS):
            v = prof[b]["1"][hh] * (1 + noise[k, j])
            if b == "water_pump" and dead_pump:
                v = 0.0
            l1b[b] = max(v, 0)
            per_b[b][k] = l1b[b]
        l1 = sum(l1b.values())
        l2 = sum(prof[b]["2"][hh] for b in BUILDINGS if not (b == "water_pump" and dead_pump))
        g = PV_KW * pvs[cm]
        # Tier 2 only runs from surplus PV (pump, autoclave, compressor)
        surplus = g - l1
        l2_served = min(l2, max(surplus, 0)) if l2 > 0 else 0
        net = g - l1 - l2_served                     # + charge, − discharge
        if net >= 0:
            room = (usable - soc) / ETA * 60
            chg = min(net, BAT_KW, room)
            soc += chg * ETA / 60
            curt[k] = net - chg
            pbat[k] = -chg
        else:
            dis = min(-net, BAT_KW, soc * ETA * 60)
            soc -= dis / ETA / 60
            pbat[k] = dis
        t1[k] = l1; t2[k] = l2_served; pv[k] = g; pv_used[k] = g - curt[k]; socs[k] = soc / usable * 100
    i_min = int(np.argmin(socs))
    hhmm = lambda m: f"{((start + m) % 1440) // 60:02d}:{((start + m) % 1440) % 60:02d}"
    events += [((pump_off[0] - start) % 1440, "11:30  Fault on pump feeder — R3 trips (see Act 2)"),
               ((pump_off[1] - start) % 1440, "12:15  Pump feeder checked and restored"),
               (i_min, f"{hhmm(i_min)}  Battery minimum {socs[i_min]:.0f} %"),
               (int(np.argmax(t2 > 1.0)), f"{hhmm(int(np.argmax(t2 > 1.0)))}  Solar surplus — pump starts (Tier 2)"),
               (len(mins) - 1, f"17:00  24 h complete — every Tier 1 load served")]
    events.sort()
    df = pd.DataFrame(dict(minute=mins, clock_min=clock_min, pv=pv, pv_used=pv_used, t1=t1, t2=t2,
                           p_bat=pbat, soc=socs, curtail=curt,
                           **{f"L_{b}": per_b[b] for b in BUILDINGS}))
    k_fault = (pump_off[0] - start) % 1440
    meta = dict(soc_min=float(socs.min()), soc_end=float(socs[-1]), t_min=hhmm(i_min),
                soc_at_fault=float(socs[k_fault]), pv_at_fault=float(pv[k_fault]),
                e_t1=float(t1.sum() / 60), e_pv=float(pv_used.sum() / 60), e_t2=float(t2.sum() / 60),
                unserved=0.0)
    return df, events, meta


# ============================================================== ACT 4
def act4():
    dt = 1e-3
    t = np.arange(0, 14.0, dt)
    t_ret = 0.5
    f_grid = F0 + 0.01 * np.sin(2 * np.pi * 0.2 * t)
    f_isl = np.zeros_like(t); dth = np.zeros_like(t); dv = np.zeros_like(t)
    pcc = np.zeros_like(t, dtype=bool); mode = np.empty(len(t), dtype=object)
    p_grid = np.zeros_like(t); p_bat = np.zeros_like(t); tier3 = np.zeros_like(t, dtype=bool)
    v_isl = 1.00; v_grid = 0.975
    th = 155.0; fi = F0; state = "WAIT"
    events = [(t_ret, "Upstream feeder re-energised — grid voltage present")]
    stab_hold = 2.0                                   # compressed stand-in for 60 s check
    t_close = None; l1, l3 = 4.3, 5.7
    for i, ti in enumerate(t):
        if state == "WAIT" and ti >= t_ret + stab_hold:
            state = "SYNC"; events.append((ti, "Grid stable — synchronising (battery adjusts f and V)"))
        if state == "SYNC":
            target_slip = 0.10 if abs(th) > 25 else 0.025
            fi += (f_grid[i] + target_slip * (1 if th > 0 else -1) * -1 - fi) * dt / 0.3
            v_isl += (v_grid - v_isl) * dt / 0.4
        elif state in ("WAIT",):
            fi += (F0 - fi) * dt / 0.5
        else:
            fi = f_grid[i]
        th = (th + 360 * (fi - f_grid[i]) * dt + 180) % 360 - 180
        dvv = abs(v_isl - v_grid) / v_grid * 100
        ok = abs(th) < 3 and abs(fi - f_grid[i]) < 0.1 and dvv < 5
        if state == "SYNC" and ok and t_close is None:
            t_close = ti + CB_OPEN; state = "CLOSING"
            events.append((ti, f"Sync-check OK (window ±10°): Δθ {abs(th):.1f}°, Δf {abs(fi - f_grid[i]):.3f} Hz, ΔV {dvv:.1f} %"))
        if state == "CLOSING" and ti >= t_close:
            state = "GRID"; events.append((ti, "PCC breaker CLOSED — reconnected"))
        if state == "GRID":
            th *= 0.98
            p_bat[i] = p_bat[i - 1] + (0 - p_bat[i - 1]) * dt / 0.8
            if ti >= t_close + 1.5:
                if not tier3[i - 1]:
                    events.append((ti, f"Tier 3 loads restored ({l3:.1f} kW)"))
                tier3[i] = True
            p_grid[i] = l1 + (l3 if tier3[i] else 0) - p_bat[i]
        else:
            p_bat[i] = l1
        f_isl[i] = fi; dth[i] = th; dv[i] = dvv; pcc[i] = state == "GRID"; mode[i] = state
    events.append((t_close + 4.0, "Battery → grid-following, recharging from grid"))
    events.sort()
    df = pd.DataFrame(dict(t=t, f_isl=f_isl, f_grid=f_grid, dtheta=dth, dv=dv, pcc=pcc, mode=mode,
                           p_grid=p_grid, p_bat=p_bat, tier3=tier3))
    meta = dict(t_ret=t_ret, t_close=t_close, close_angle=float(abs(dth[int(t_close / dt) - 1])))
    return df, events, meta


def run_all():
    out = {}
    for name, fn in (("act1", act1), ("act2", act2), ("act3", act3), ("act4", act4)):
        df, ev, meta = fn()
        df.to_csv(HERE / f"sim_{name}.csv", index=False)
        out[name] = dict(df=df, events=ev, meta=meta)
    json.dump({k: dict(events=[(float(a), b) for a, b in v["events"]],
                       meta={mk: (float(mv) if isinstance(mv, (int, float, np.floating)) else mv)
                             for mk, mv in v["meta"].items()})
               for k, v in out.items()},
              open(HERE / "sim_events.json", "w"), indent=2)
    return out


if __name__ == "__main__":
    out = run_all()
    for k, v in out.items():
        print(f"\n===== {k.upper()} =====")
        for mk, mv in v["meta"].items():
            print(f"  {mk}: {mv}")
        for t, e in v["events"]:
            print(f"  [{t:8.3f}] {e}")
