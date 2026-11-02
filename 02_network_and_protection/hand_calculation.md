# Hand calculation — fault current at the PCC bus

IEC 60909 method, maximum case. Every number here is from `params.json`.
This is the calculation `verify.py` checks the model against.

---

## 1. The idea in one paragraph

A fault is a short circuit. The current that flows is the source voltage divided
by everything in the way: the upstream grid's own impedance, the transformer, and
any cable between the transformer and the fault. Work out each impedance, refer them
all to the same voltage level, add them up, divide. That's the whole method.

IEC 60909 adds two refinements: a **voltage factor c** (the pre-fault voltage is
allowed to sit above nominal, so use c × U_n instead of U_n), and a **transformer
correction factor K_T** (accounts for the transformer's actual operating point).
Both are small multipliers, but pandapower applies them, so we do too.

---

## 2. Data

| Item | Symbol | Value | Source |
|---|---|---|---|
| Grid nominal voltage | U_nQ | 11 kV | params.json → grid |
| Grid fault level | S_kQ | 50 MVA | params.json → grid (assumption) |
| Grid R/X ratio | R_Q/X_Q | 0.30 | params.json → grid |
| Transformer rating | S_rT | 200 kVA | params.json → transformer |
| Transformer ratio | t_r | 11 / 0.4 = 27.5 | |
| Impedance voltage | u_kr | 4 % | params.json → transformer |
| Resistive part | u_Rr | 1 % | params.json → transformer |
| LV nominal voltage | U_n | 400 V | |
| Voltage factor (max, LV, +10 % tolerance) | c_max | 1.10 | IEC 60909 Table 1 |

---

## 3. Source impedance, referred to 400 V

The upstream network is a voltage source behind an impedance. Its impedance at
11 kV is

    Z_Q = c × U_nQ² / S_kQ
        = 1.10 × (11 000)² / 50 × 10⁶
        = 1.10 × 121 × 10⁶ / 50 × 10⁶
        = 2.662 Ω          (at 11 kV)

Refer it to the LV side by dividing by the turns ratio squared:

    Z_Qt = Z_Q / t_r²
         = 2.662 / 27.5²
         = 2.662 / 756.25
         = 0.003520 Ω      (at 400 V)

Split into R and X using R/X = 0.30:

    X_Qt = Z_Qt / √(1 + 0.30²) = 0.003520 / 1.0440 = 0.003372 Ω
    R_Qt = 0.30 × X_Qt                                = 0.001012 Ω

Why it's so small: the grid is a strong source. 50 MVA at 11 kV is a large
number compared to a 200 kVA transformer, so the grid contributes almost
nothing to the total impedance. The transformer dominates.

---

## 4. Transformer impedance

From nameplate percentages and rating, at the LV voltage:

    Z_T = (u_kr / 100) × U_rT² / S_rT
        = 0.04 × 400² / 200 000
        = 0.04 × 160 000 / 200 000
        = 0.03200 Ω

    R_T = (u_Rr / 100) × U_rT² / S_rT
        = 0.01 × 0.8
        = 0.00800 Ω

    X_T = √(Z_T² − R_T²)
        = √(0.001024 − 0.000064)
        = √0.000960
        = 0.03098 Ω

IEC 60909 correction factor for a network transformer:

    x_T = u_kr / 100 = 0.04
    K_T = 0.95 × c_max / (1 + 0.6 × x_T)
        = 0.95 × 1.10 / 1.024
        = 1.0205

    R_TK = K_T × R_T = 1.0205 × 0.00800 = 0.008164 Ω
    X_TK = K_T × X_T = 1.0205 × 0.03098 = 0.031620 Ω

---

## 5. Three-phase fault at the PCC

Add source and transformer (the PCC is the transformer LV terminal, so no cable):

    R_k = R_Qt + R_TK = 0.001012 + 0.008164 = 0.009176 Ω
    X_k = X_Qt + X_TK = 0.003372 + 0.031620 = 0.034992 Ω

    Z_k = √(R_k² + X_k²)
        = √(0.0000842 + 0.0012244)
        = √0.0013086
        = 0.036175 Ω

Initial symmetrical short-circuit current:

    I''k3 = c × U_n / (√3 × Z_k)
          = 1.10 × 400 / (1.7321 × 0.036175)
          = 440 / 0.062656
          = 7 022 A                                    ← grid contribution

**Model result: 7 113 A.** The difference of 91 A is the inverter contribution
(PV + battery, current-limited at 1.2 × rated ≈ 95 A) which pandapower adds and
this hand calculation deliberately leaves out. Agreement to 0.1 %.

---

## 6. Single-phase-to-ground fault at the PCC

For an unbalanced fault you need three impedances instead of one: positive
sequence Z₁, negative sequence Z₂, and zero sequence Z₀.

    I''k1 = √3 × c × U_n / |Z₁ + Z₂ + Z₀|

For a passive network Z₂ = Z₁. So the only new thing is Z₀.

**The Dyn transformer changes everything.** Its delta winding on the HV side
blocks zero-sequence current from flowing to the grid. So the grid's zero-sequence
impedance is not seen at all — only the transformer's own zero-sequence impedance
appears, and for a Dyn unit that is approximately equal to its positive-sequence
impedance (params.json sets vk0 = vk).

    Z₁ = Z₂ = R_k + jX_k     = 0.009176 + j0.034992   (from section 5)
    Z₀ = R_TK + jX_TK        = 0.008164 + j0.031620   (transformer only)

    Z₁ + Z₂ + Z₀ = (2 × 0.009176 + 0.008164) + j(2 × 0.034992 + 0.031620)
                 = 0.026516 + j0.101604

    |Z₁ + Z₂ + Z₀| = √(0.000703 + 0.010323) = √0.011026 = 0.10501 Ω

    I''k1 = √3 × 1.10 × 400 / 0.10501
          = 762.1 / 0.10501
          = 7 257 A                                    ← grid contribution

**Model result: 7 348 A.** Same 91 A inverter difference. Agreement to 0.1 %.

Why 1ph is *higher* than 3ph here: because the delta blocks the grid's
zero-sequence path, Z₀ is only the transformer, which is less than Z₁. So the
sum Z₁ + Z₂ + Z₀ is less than 3 × Z₁, and the current is higher. This is normal
at the LV terminals of a Dyn transformer.

Why it flips further down the feeder: cable zero-sequence impedance is
roughly 3 × positive sequence (params.json). Once you add cable, Z₀ grows
three times faster than Z₁ and the single-phase current drops below the
three-phase current. Look at the fault_levels.csv — at every building bus,
1ph < 3ph.

---

## 7. What changes when the grid is gone

Open the PCC switch. The transformer and upstream grid are no longer in the
circuit. The only sources are the PV and battery inverters.

An inverter is not a voltage source behind an impedance. It is a controlled
current source with a hard limit — typically 1.1 to 1.5 × rated current,
set by the semiconductor ratings. It will not push more than that no matter
how hard the fault pulls.

So the calculation is no longer "voltage over impedance." It's simply:

    I''k,island ≈ Σ (k × I_rated)
                = 1.2 × (33 kVA + 22 kVA) / (√3 × 400 V)
                = 1.2 × 55 000 / 692.8
                = 95 A

Cable impedance barely matters — the current is limited at the source, not by
the path. That's why every building bus in the islanded column shows ~94 A.

**This is the number that makes protection hard.** Grid-connected, a fault at
the telecom tower gives 4 294 A. Islanded, it gives 94 A. The load current at
that bus is a few amps, and the inverter's normal running current is up to 80 A.
An overcurrent relay set to see 4 000 A faults will never see a 94 A fault;
a relay set to see 94 A faults will trip on inverter load. One setting cannot
serve both states — which is exactly what weeks 8–9 have to solve.

---

## 8. Doing the other buses

For any building bus, add the cable impedance to section 5:

    R_k(bus) = R_k(PCC) + R_tie + R_cable
    X_k(bus) = X_k(PCC) + X_tie + X_cable

where R = r_ohm_per_km × length_km, from the NAYY 4x150 SE line type in
pandapower (r = 0.208 Ω/km, x = 0.080 Ω/km). Then recompute Z_k and I''k3.

For single-phase, the cable's zero-sequence impedance is 3 × its positive
sequence (params.json → r0_factor, x0_factor), so add
    Z₀(bus) = Z_TK + 3 × Z_tie + 3 × Z_cable
and recompute section 6.

Example — telecom tower, 0.02 km tie + 0.12 km feeder = 0.14 km total:

    R_cable = 0.208 × 0.14 = 0.02912 Ω,   X_cable = 0.080 × 0.14 = 0.01120 Ω
    R_k = 0.009176 + 0.02912 = 0.03830,   X_k = 0.034992 + 0.01120 = 0.04619
    Z_k = √(0.001467 + 0.002134) = 0.06001 Ω
    I''k3 = 440 / (1.7321 × 0.06001) = 4 233 A     (model: 4 294 A, inverters again)
