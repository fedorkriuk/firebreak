if exist(fullfile(pwd,'models','ts_b02_island.slx'),'file')
    error('ts_b02_island.slx already exists. Delete it on purpose if you want to start over.');
end

%% b02_make_model.m - Stage 2a (copy) and 2b (50 Hz). Run once.
src = 'MicroGridIslandedOperation';   % must be on the path
dst = 'ts_b02_island';
load_system(src);
save_system(src, fullfile(pwd,'models',[dst '.slx']));   % saves a renamed copy
close_system(src,0);
load_system(fullfile(pwd,'models',[dst '.slx']));
mdl = dst;

inv = {'Inverter 1 500 kW','Inverter 2 300 kW','Inverter 3 200 kW'};

%% 2b: 60 Hz -> 50 Hz
for i = 1:3
    p = [mdl '/' inv{i}];
    set_param(p,'Fnom','50');
    set_param([p '/L1'],'Inductance','0.15 * (Vnom_sec^2/Pnom/2/pi/Fnom)');
end
set_param([mdl '/Load1'],'NominalFrequency','50');
set_param([mdl '/Load2'],'NominalFrequency','50');
set_param([mdl '/Variable load'],'NominalVoltage','[ 600 50 ]');
set_param([mdl '/powergui'],'frequency','50');
try set_param([mdl '/powergui'],'fundamental','50'); catch ME, disp(ME.message); end

f = find_system(mdl,'LookUnderMasks','all','FollowLinks','on', ...
                'RegExp','on','Name','Second-Order Filter\d*');
for k = 1:numel(f)
    try set_param(f{k},'Vac_Init','[0, 0, 50]'); catch ME, disp(ME.message); end
end

save_system(mdl);
disp('Done. Now run b02_scan(mdl, ''(?<![\d.])60(?!\d)'') to find any missed 60s.');