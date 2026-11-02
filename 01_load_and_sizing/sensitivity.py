"""TT01 sensitivity — how the dominant assumption moves battery size."""
from pathlib import Path
import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"
df = pd.read_csv(DATA / 'critical_load_list.csv')
num  = pd.to_numeric(df.rated_power_W, errors='coerce')
qty  = pd.to_numeric(df.quantity, errors='coerce')
win  = pd.to_numeric(df.window_hours, errors='coerce')
duty = pd.to_numeric(df.duty_cycle_pct, errors='coerce')
df['kwh_per_day'] = num*qty*duty/100*win/1000

t1 = df[df.tier == '1']
print("TIER 1 ENERGY BY BUILDING (kWh/day)")
print(t1.groupby('building').kwh_per_day.sum().round(1).to_string())
print(f"\nTotal Tier 1        : {t1.kwh_per_day.sum():.1f} kWh/day")
print(f"Peak connected Tier 1: {(num[df.tier=='1']*qty[df.tier=='1']).sum():.0f} W")

print("\nTIER 2 (served by PV in the solar window)")
t2 = df[df.tier == '2']
print(f"Total Tier 2        : {t2.kwh_per_day.sum():.1f} kWh/day")

# --- TT01 sensitivity -------------------------------------------------
base_other = t1[t1.load_id != 'TT01'].kwh_per_day.sum()
print("\nTT01 SENSITIVITY  (DC site load -> battery)")
print(f"{'DC load':>8} {'TT01':>8} {'Tier 1':>9} {'Usable':>9} {'Nameplate':>10}")
print(f"{'kW':>8} {'kWh/d':>8} {'kWh/d':>9} {'kWh':>9} {'kWh @80% DoD':>10}")
for dc_kw in [0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0]:
    tt01 = dc_kw/0.96 * 24                 # AC kWh/day
    tier1 = base_other + tt01
    usable = tier1 * 1.10                  # 10% margin for inverter and round-trip losses
    nameplate = usable / 0.80              # 80% depth of discharge
    mark = "  <- current assumption" if dc_kw == 1.5 else ""
    print(f"{dc_kw:>8.2f} {tt01:>8.1f} {tier1:>9.1f} {usable:>9.1f} {nameplate:>10.1f}{mark}")

print("\nEverything except TT01 contributes %.1f kWh/day." % base_other)
print("Across the plausible range the battery moves by roughly a factor of two,")
print("so TT01 must be verified before sizing is locked.")
