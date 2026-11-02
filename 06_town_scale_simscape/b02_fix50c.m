%% b02_fix50c.m - inverter measurement frequency clamps were 55..65 Hz
mdl = 'ts_b02_island';
if ~bdIsLoaded(mdl), load_system(fullfile(pwd,'models',[mdl '.slx'])); end
inv = {'Inverter 1 500 kW','Inverter 2 300 kW','Inverter 3 200 kW'};
for i = 1:3
    p = [mdl '/' inv{i} '/Control System/Measurements/Saturation'];
    set_param(p,'UpperLimit','55','LowerLimit','45');
    fprintf('%s -> 45..55\n', p);
end
save_system(mdl);