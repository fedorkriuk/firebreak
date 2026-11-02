# Firebreak Microgrid - Team 10

Islanding microgrid that keeps four rural critical buildings (fire station, water pump, health clinic, telecom tower) running for 24 h when the grid fails.

- 30 kWp solar, 80 kWh / 20 kW battery, one PCC switch
- Islands in 0.16 s, clears an island fault in 0.18 s, lowest battery charge 28%, recloses at 3°

## Folders

- `data/` - shared parameters and the 29-item critical load list
- `01_load_and_sizing/` - Tier 1 energy and PV / battery sizing sweep
- `02_network_and_protection/` - pandapower network, IEC 60909 fault study, relay settings, coordination curves
- `03_python_simulation/` - full outage simulation (grid loss, island fault, 24 h island, reconnection) and video
- `04_real_site_check/` - real-site check: Nowra NSW, PVGIS 2023 data, datasheet loads
- `05_simulink_islanding_model/` - Simulink islanding model (build script) and Python check
- `06_town_scale_simscape/` - town-scale Simscape study (22 kV, 10 MW essential load)
- `media/` - simulation videos

## Run (Python)

- `pip install -r requirements.txt`
- `01`: `python size_system.py`
- `02`: `python network.py`, `fault_study.py`, `verify.py`, `relay_settings.py`, `plot_tcc.py`
- `03`: `python sim.py`, then `python video.py` (needs ffmpeg, about 10 min)
- `04`: `python run_all.py`
- `05`: `python python_check.py`

## Run (MATLAB)

- `05`: run `build_firebreak_microgrid_v4.m`, press Run, then `plot_microgrid_results_v4.m` (standard Simulink only)
- `06`: needs Simscape Electrical, see the README in the folder
