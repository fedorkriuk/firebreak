%% s04_extract_logged.m
% Reads SignalLog (base workspace, created by pressing Run in ts_b02f_log)
% and prints the numbers for the compliance table.
P = town_params();
Pbase_kW = P.bess.block_MW*1000;     % 5874 kW per inverter (assumes Pmeas is per unit)
tTrip = 6.0; tSkip = 0.3;

names = SignalLog.getElementNames;
fprintf('Logged elements: %s\n\n', strjoin(names,', '));

g = @(n) SignalLog.get(n).Values;    % timeseries
f  = g('Freq_pcc');  pp = g('P_pcc_kW'); qq = g('Q_pcc_kvar'); vv = g('Vab_rms');
for n = {'Freq_pcc','P_pcc_kW','Q_pcc_kvar','Vab_rms','Pmeas_BS1','Pmeas_BS2','Pmeas_BS3'}
    ts = g(n{1});
    fprintf('%-11s samples %d, size(Data) = %s\n', n{1}, numel(ts.Time), mat2str(size(ts.Data)));
end
fprintf('(expect 200001 samples each; fewer means decimation or a data-point limit is on)\n\n');

%% Frequency
t = f.Time; d = squeeze(f.Data);
ok = t >= tSkip;  post = t >= tTrip;
[fmin,i1] = min(d(post)); tp = t(post); 
fprintf('--- Frequency (Hz) ---\n');
fprintf('Before 3 s (no droop)   : mean %.3f\n', mean(d(t>=1 & t<3)));
fprintf('3-6 s (droop, pre-trip) : mean %.3f\n', mean(d(t>=4 & t<6)));
fprintf('Min after trip          : %.3f Hz @ %.3f s\n', fmin, tp(i1));
fprintf('Max after trip          : %.3f Hz\n', max(d(post)));
fprintf('Settled (9-10 s)        : mean %.3f Hz\n', mean(d(t>=9)));
fprintf('Time outside 49.5-50.5 (>%.1f s): %.3f s\n\n', tSkip, ...
    sum(ok & (d<49.5 | d>50.5))*median(diff(t)));

%% Inverter power (pu -> MW) and check against PCC
Pi = cell(1,3);
for k = 1:3, Pi{k} = g(sprintf('Pmeas_BS%d',k)); end
tt = pp.Time; Ppcc_MW = squeeze(pp.Data)/1000;
sumInv = zeros(size(tt));
for k = 1:3
    sumInv = sumInv + interp1(Pi{k}.Time, squeeze(Pi{k}.Data), tt)*Pbase_kW/1000;
end
fprintf('--- Power ---\n');
fprintf('Check: sum of inverters vs PCC at t=5 s : %.3f vs %.3f MW\n', ...
    interp1(tt,sumInv,5), interp1(tt,Ppcc_MW,5));
fprintf('Check: same at t=9 s                    : %.3f vs %.3f MW\n', ...
    interp1(tt,sumInv,9), interp1(tt,Ppcc_MW,9));
for k = 1:3
    tk = Pi{k}.Time; dk = squeeze(Pi{k}.Data);
    fprintf('Inverter(BS%d): pre-trip %.3f pu | post-trip max %.3f pu | settled %.3f pu (%.2f MW)\n', k, ...
        mean(dk(tk>=5 & tk<5.9)), max(dk(tk>=tTrip)), mean(dk(tk>=9)), mean(dk(tk>=9))*Pbase_kW/1000);
end
fprintf('PCC P: pre-trip %.3f MW | min after trip %.3f MW | settled %.3f MW\n', ...
    mean(Ppcc_MW(tt>=5 & tt<5.9)), min(Ppcc_MW(tt>=tTrip)), mean(Ppcc_MW(tt>=9)));
Qd = squeeze(qq.Data);
fprintf('PCC Q settled: %.0f kvar\n\n', mean(Qd(qq.Time>=9)));

%% Block's own Vab_rms vs our one-cycle RMS (from s02)
tv = vv.Time; dv = squeeze(vv.Data)/P.V_town;
okv = tv >= tSkip;
[vm,iv] = min(dv(okv)); tvv = tv(okv);
fprintf('--- PCC Measurements Vab_rms (block output) ---\n');
fprintf('Min: %.4f pu (%.2f%%) @ %.3f s   [s02 one-cycle RMS gave 0.9437 pu]\n', vm, 100*(vm-1), tvv(iv));
fprintf('Max: %.4f pu (%.2f%%)\n', max(dv(okv)), 100*(max(dv(okv))-1));
fprintf('Time below 0.94 pu: %.3f s\n', sum(okv & dv<0.94)*median(diff(tv)));