%% s14_add_pv_event.m
% Adds PV_Event (Step) summed into the PV power command ahead of PV_Ramp.
% PV_Event is 0 by default, so existing runs are unchanged.
% Run once with ts_b03_pv open. Save a _PASS copy first.
mdl = 'ts_b03_pv';
if ~bdIsLoaded(mdl), error('Open %s first.', mdl); end
if ~isempty(find_system(mdl,'SearchDepth',1,'Name','PV_Event'))
    error('PV_Event already exists. Nothing changed.');
end

p = get_param([mdl '/PV_Pstep'],'Position');
add_block('simulink/Sources/Step',[mdl '/PV_Event'], ...
    'Position', p + [0 -120 0 -120], ...
    'Time','8', 'Before','0', 'After','0', 'SampleTime','Ts');
add_block('simulink/Math Operations/Sum',[mdl '/PV_SumEvt'], ...
    'Position', [p(3)+30 p(2)-70 p(3)+50 p(2)-30], 'Inputs','++');

delete_line(mdl,'PV_Pstep/1','PV_Ramp/1');
add_line(mdl,'PV_Pstep/1','PV_SumEvt/1','autorouting','smart');
add_line(mdl,'PV_Event/1','PV_SumEvt/2','autorouting','smart');
add_line(mdl,'PV_SumEvt/1','PV_Ramp/1','autorouting','smart');

set_param([mdl '/PV_Ramp'],'RisingSlewLimit','2e6','FallingSlewLimit','-1e6');
save_system(mdl);

fprintf('PV_Event added (value 0). Ramp: rise 2 MW/s, fall 1 MW/s.\n\n');
fprintf('Common setup (PV at 8 MW by 4.5 s, before the 6 s trip):\n');
fprintf('  set_param(''%s/PV_Pstep'',''Time'',''0.5''); set_param(''%s/PV_Pstep'',''After'',''8e6'');\n\n', mdl, mdl);
fprintf('CLOUD test (8 -> 3 MW over 5 s from 8 s):\n');
fprintf('  set_param(''%s/PV_Event'',''After'',''-5e6'');\n', mdl);
fprintf('  set_param(''%s/PV_Ramp'',''FallingSlewLimit'',''-1e6'');\n', mdl);
fprintf('  PRESS RUN, then s10_plot_pv(''cloud'') and s09_check_pv\n\n');
fprintf('PV LOSS test (8 MW lost at once at 8 s):\n');
fprintf('  set_param(''%s/PV_Event'',''After'',''-8e6'');\n', mdl);
fprintf('  set_param(''%s/PV_Ramp'',''FallingSlewLimit'',''-1e9'');\n', mdl);
fprintf('  PRESS RUN, then s10_plot_pv(''PVloss'') and s09_check_pv\n');