% b02e_3x6.m
src = 'ts_b02d_trip'; dst = 'ts_b02e_3x6';
mdir = fullfile(pwd,'models');
if exist(fullfile(mdir,[dst '.slx']),'file')
    error('%s.slx exists. Delete it on purpose to redo.', dst);
end
if bdIsLoaded(src), close_system(src,0); end
copyfile(fullfile(mdir,[src '.slx']), fullfile(mdir,[dst '.slx']));
load_system(fullfile(mdir,[dst '.slx']));  mdl = dst;
inv = {'Inverter 1 500 kW','Inverter 2 300 kW','Inverter 3 200 kW'};
Pn  = 6*979e3;                                   % 5.874e6 VA per block
for i = 1:3
    fprintf('%s: Pnom was %s\n', inv{i}, get_param([mdl '/' inv{i}],'Pnom'));
    set_param([mdl '/' inv{i}],'Pnom',sprintf('%.6g',Pn));
    fprintf('%s: Pnom now %s\n', inv{i}, get_param([mdl '/' inv{i}],'Pnom'));
end
fprintf('Breaker time in Inverter 1: %s\n', get_param([mdl '/' inv{1} '/Trip Breaker'],'SwitchTimes'));
set_param(mdl,'StopTime','10');
save_system(mdl);
open_system(mdl);