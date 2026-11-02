function P = town_params()
%TOWN_PARAMS  Single source of truth for the town-scale microgrid study.
%  Use at the top of every script:  P = town_params();
%  Tags:  [S] stated in a source   [D] derived   [A] assumed (replace when sourced)
%  Items marked CHECK conflict between sources and must be verified.

%% ---- System and limits -------------------------------------------------
P.f0       = 50;              % Hz
P.V_town   = 22e3;            % V line-line, town bus [S] network planning reports
P.V_tx     = 220e3;           % V, transmission line [S]
P.dV_proj  = 0.06;            % +/-6 % project limit [S] project brief
P.f_proj   = 0.5;             % Hz, 50 +/- 0.5 [S] project brief (equals NEM island NOFB 49.5-50.5 [S] FOS)
P.NER_V    = [0.90 1.10];     % pu continuous range [S] NER S5.1a.4 (project limit is stricter)

%% ---- AEMO grid-forming checklist (for Stage B pass/fail) ---------------
P.GFM.t_init_ms = 20;         % ms, response initiation [S] AEMO GFM approach paper
P.GFM.P_resp_ms = 50;         % ms, 90 % active-power rise [S] AEMO GFM spec Jan 2024
P.GFM.headroom  = 0.10;       % >=10 % power headroom [S]
P.GFM.Ilim_pu   = [1.0 1.3];  % typical current limit [S]
P.GFM.V_band_pu = [0.8 1.1];  % transient band, outside for <0.1 s [S]
P.test.fault_depth_pu = 0.5;  % [S] AEMO commissioning fault test
P.test.fault_ms       = 120;  % 6 cycles at 50 Hz [S]
P.test.angle_steps    = [10 30 60];   % deg [S] AEMO test 7

%% ---- Grid (upstream of the island) -------------------------------------
P.grid.Sk_min_MVA = 1755;     % MVA, upstream node minimum fault level [S] TAPR 2026 Table 5.3 (CHECK which voltage level)
P.grid.TL_len_km  = 260;      % km [S]
% line line constants, transformer MVA/impedance and 22 kV fault level are NOT FOUND in TAPR, DAPR or PSCR.
% Typical textbook values below are ASSUMED [A]; run a sensitivity (+/-30 %) and say so in the report.
P.grid.TL_R_ohm_km = 0.07;    % [A] typical 220 kV single circuit
P.grid.TL_X_ohm_km = 0.40;    % [A]
P.grid.TL_B_uS_km  = 2.9;     % [A]
P.xfmr.n           = 2;       % number of 220/22 kV units [S]
P.xfmr.MVA         = 60;      % [A] each; one unit can carry the 53 MW historical peak
P.xfmr.Z_pct       = 12;      % [A]
% Illustrative result from these assumptions: ~360 MVA at the 220 kV substation, ~270 MVA at 22 kV (both units in service)

%% ---- Load ---------------------------------------------------------------
P.load.BSP_peak_MW = [38 34];     % summer / winter PEAK at 22 kV BSP, excludes 220 kV mine load [S] TAPR 2026
P.load.avg_total_MW= 40;          % MW average, whole substation = 19 (220 kV, mine) + 21 (22 kV) [S] PACR Table B-4
P.load.avg_22kV_MW = 21;          % MW average, 22 kV town load [S] PACR Table B-4
P.load.hist_peak_MW= 53;          % MW, 2019, whole substation incl. mine [S] PSCR
P.load.share       = [0.25 0.30]; % essential share of demand [A] project proposal
P.load.P_ess_peak  = 10;          % MW [D] ~ mid of 25-30 % x 34-38 MW (range 8.5-11.4)
P.load.T_out_h     = 4;           % h ride-through [A] project scope
P.load.pf          = 0.997;       % [D] from 38 MW / 3 MVAr, TAPR 2026
P.load.shape_file  = '24-h_load_data.xlsx';  % PLACEHOLDER lab shape; replace with site data

%% ---- Battery ------------------------------------------------------------
P.bess.DOD       = 0.80;      % [S] course
P.bess.eta_rt    = 0.937;     % AC-AC round trip, 4-h unit, 25 C [S] Megapack 2 XL datasheet p.2 (2-h unit: 0.920)
P.bess.eta_1way  = sqrt(P.bess.eta_rt);   % [D]
P.bess.unit_kW   = 979;       % kW per 4-h Megapack 2 XL unit [S] datasheet Rev 2.0
P.bess.unit_kWh  = 3916;      % kWh per 4-h unit [S]
P.bess.life_y    = 20;        % [S] GenCost warranty basis
P.bess.n_blocks    = 3;                          % [A] equal grid-forming inverters, 6 units each
P.bess.block_MW    = 6*P.bess.unit_kW/1000;      % [D] 5.874 MW per block

%% ---- PV ----------------------------------------------------------------
P.pv.PR        = 0.80;        % performance ratio [A]
P.pv.eta_inv   = 0.976;       % [S] Lab 2 value (Sungrow SG4400UD max 98.9 %, CEC 98.5 % [S])
P.pv.Ilim_pu   = 1.2;         % GFL current limit [S] MathWorks PV controller doc
P.pv.PLL       = [200 2000];  % PLL P and I gains [S] MathWorks example (60 Hz design; retune)
P.pv.island_mode = 'on';   % [A] PV stays connected while islanded
P.pv.MW_total    = 8;             % [A] 5 MW community + 3 MW rooftop, both grid-following
%% ---- Control starting points ---------------------------------------------
P.ctrl.droopPf_pct = 1;                 % [D] 1 % so full-load droop span 0.5 Hz fits 50 +/- 0.5 Hz; verified in B2
P.ctrl.droopPf_Hz  = 0.01*P.f0;         % [D] 0.5 Hz per pu at 50 Hz
P.bess.n_units     = 18;                % [A]  3 blocks of 6

%% ---- Costs and economics (GenCost 2025-26, real 2025 AUD) -------------
P.cost.pv_util_kW   = 1621;   % $/kW [S]
P.cost.pv_roof_kW   = 1216;   % $/kW [S]
P.cost.pv_fom_kWyr  = 12;     % $/kW/yr [S]
P.cost.pv_life_y    = 30;     % [S]
P.cost.bess4h_kWh   = 385;    % $/kWh [S]
P.cost.bess_fom_frac= 0.02;   % of capex per year [A] not itemised in GenCost
P.cost.r            = 0.07;   % real discount rate [S] GenCost
P.cost.r_sens       = [0.05 0.06];  % Lab 2 and Roy et al. [S] for sensitivity
P.econ.VCR_NSW      = 39.99;  % $/kWh residential, 2025 [S] AER
P.econ.VCR_RITT     = 37.78;  % $/kWh used in the regulatory investment test [S]
P.econ.TL_events    = 10;     % reported outages May 2019 - Jan 2025 [S]
P.econ.TL_years     = 5.7;    % [D]
P.econ.TL_rate      = P.econ.TL_events/P.econ.TL_years;  % events/yr [D] HIGH: assumes all 10 events last >= 4 h
P.econ.TL_rate_low  = 2/P.econ.TL_years;   % events/yr [D] LOW: only 2 events (2022, Oct 2024) known >= 4 h; durations of the other 8 NOT FOUND


%% ---- Simulink (Simscape Electrical, physical domain) ---------------------
P.sim.solver  = 'ode23t';     % [S] MathWorks example
P.sim.maxstep = 1e-4;         % s [S]
P.sim.reltol  = 1e-4;         % [S]
end
