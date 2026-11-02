%% plot_microgrid_results.m
%% Plots the 24-hour Firebreak Microgrid simulation results
%% Run AFTER simulating firebreak_microgrid (Ctrl+T)

% Convert timeseries to arrays
t_hr = sim_soc.Time / 3600;   % seconds → hours

SOC      = sim_soc.Data;
P_load   = sim_power.Data;

% Solar profile (v4: same design-day timeseries the model uses)
P_solar  = interp1(pv_data.Time/3600, pv_data.Data, t_hr, 'previous', 0);

% Battery = Load - Solar (discharge positive)
P_bat = P_load - P_solar;

figure('Name','Firebreak Microgrid — 48h Simulation (v4)','NumberTitle','off',...
       'Color','white','Position',[100 100 1100 750]);

%% --- Plot 1: Power Flows ---
subplot(3,1,1);
hold on;
plot(t_hr, P_load,  'b-',  'LineWidth', 2, 'DisplayName', 'Total Load (kW)');
plot(t_hr, P_solar, 'y-',  'LineWidth', 2, 'DisplayName', 'Solar PV (kW)');
plot(t_hr, P_bat,   'r--', 'LineWidth', 1.5, 'DisplayName', 'Battery Dispatch (kW)');
xline(17, 'k--', 'LineWidth', 1.5, 'Label', 'Grid Fails 17:00');
xline(41, 'm--', 'LineWidth', 1.2, 'Label', 'Grid Returns 17:00 day 2');
hold off;
ylabel('Power (kW)');
title('Power Flows — Tier 1 Loads, Solar PV, Battery');
legend('Location','northeast');
grid on;
xlim([0 48]);
xticks(0:4:48);

%% --- Plot 2: Battery SOC ---
subplot(3,1,2);
plot(t_hr, SOC * 100, 'g-', 'LineWidth', 2);
yline(20, 'r--', 'LineWidth', 1.5, 'Label', 'Min SOC 20%');
yline(32, 'b--', 'LineWidth', 1.2, 'Label', 'Target End SOC 32%');
xline(17, 'k--', 'LineWidth', 1.5, 'Label', 'Grid Fails');
xline(41, 'm--', 'LineWidth', 1.2, 'Label', 'Grid Returns');
ylabel('SOC (%)');
title('Battery State of Charge (80 kWh)');
grid on;
xlim([0 48]);
ylim([0 110]);
xticks(0:4:48);

%% --- Plot 3: Load breakdown ---
subplot(3,1,3);
P_telecom = 47.56;
P_health  = 10.0;
P_firestn =  8.5;
P_water   = 16.0;
bar_data  = [P_telecom, P_water, P_health, P_firestn];
bar_names = {'Telecom Tower','Water Pumping','Health Clinic','Fire Station'};
b = bar(bar_data, 'FaceColor', 'flat');
b.CData = [0.2 0.4 0.8; 0.1 0.7 0.5; 0.9 0.6 0.1; 0.8 0.2 0.2];
set(gca,'XTickLabel', bar_names);
ylabel('Constant Load (kW)');
title('Tier 1 Critical Load Breakdown (Total ≈ 82 kW)');
grid on;

% Print key results
fprintf('\n========================================\n');
fprintf('  FIREBREAK MICROGRID — Simulation Summary\n');
fprintf('========================================\n');
fprintf('  Start SOC :  %.1f%%\n', SOC(1)*100);
fprintf('  Min SOC   :  %.1f%%  (must stay above 20%%)\n', min(SOC)*100);
fprintf('  End SOC   :  %.1f%%  (target: 32%%)\n', SOC(end)*100);
fprintf('  Peak Load :  %.1f kW\n', max(P_load));
fprintf('  Peak Solar:  %.1f kW\n', max(P_solar));
fprintf('========================================\n\n');

if min(SOC)*100 < 20
    fprintf('  WARNING: Battery hit minimum SOC!\n');
    fprintf('  Consider larger battery or load shedding.\n\n');
else
    fprintf('  OK: Battery stayed above 20%% minimum.\n\n');
end
