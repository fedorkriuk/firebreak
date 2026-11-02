%% s03_enable_logging.m
% Makes a COPY of the open model and switches on signal logging for:
%   PCC Measurements outputs 1-4  (frequency, P, Q, Vab_rms)
%   Bus Selector outputs Pmeas, Qmeas for each of the 3 inverters
% Run from the PROJECT ROOT with ts_b02e_3x6 open. Original file is not touched.
% Safe to re-run: it refuses if ts_b02f_log.slx already exists.

src = 'ts_b02e_3x6';
dst = 'ts_b02f_log';
dstFile = fullfile(pwd,'models',[dst '.slx']);
if exist(dstFile,'file')
    error('%s already exists. Open it instead of re-running this script.', dstFile);
end
if ~bdIsLoaded(src), error('Open %s first.', src); end

%% 1. Save As: the copy becomes the open model, the original stays on disk
save_system(src, dstFile);
mdl = bdroot;
fprintf('Open model is now: %s\n', mdl);   % expect ts_b02f_log

%% 2. PCC Measurements outputs
pcc  = [mdl '/PCC Measurements'];
ph   = get_param(pcc,'PortHandles');
names = {'Freq_pcc','P_pcc_kW','Q_pcc_kvar','Vab_rms'};
for k = 1:4
    set_param(ph.Outport(k),'DataLogging','on', ...
        'DataLoggingNameMode','Custom','DataLoggingName',names{k});
    fprintf('Logging PCC Measurements out %d as %s\n', k, names{k});
end

%% 3. Per-inverter Pmeas/Qmeas from the three Bus Selectors
bs = find_system(mdl,'SearchDepth',1,'BlockType','BusSelector');
% find_system returns the exact paths (the names contain a line break)
fprintf('Found %d Bus Selectors\n', numel(bs));
for i = 1:numel(bs)
    ph = get_param(bs{i},'PortHandles');
    set_param(ph.Outport(1),'DataLogging','on', ...
        'DataLoggingNameMode','Custom','DataLoggingName',sprintf('Pmeas_BS%d',i));
    set_param(ph.Outport(2),'DataLogging','on', ...
        'DataLoggingNameMode','Custom','DataLoggingName',sprintf('Qmeas_BS%d',i));
    fprintf('Bus Selector %d (%s): outputs logged as Pmeas_BS%d / Qmeas_BS%d\n', ...
        i, strrep(bs{i},newline,' '), i, i);
end

save_system(mdl);
fprintf('\nSaved. Now press RUN in the Simulink window (stop time 10 s), then run s04_extract_logged.\n');