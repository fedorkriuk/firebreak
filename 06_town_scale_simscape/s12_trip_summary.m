function s12_trip_summary(tag, matfile, tT, tE)
%S12_TRIP_SUMMARY  Compliance numbers for an event inside the window [tT, tE].
%  s12_trip_summary('trip_noPV','',6)            event at 6 s, window to end of run
%  s12_trip_summary('PVloss_event','',4,5.9)     event at 4 s, window 4-5.9 s
if nargin < 1, tag = 'run'; end
if nargin < 2, matfile = ''; end
if nargin < 3 || isempty(tT), tT = 6.0; end
if nargin < 4 || isempty(tE), tE = inf; end
P = town_params();
if ~isempty(matfile)
    S = load(matfile);  SL = S.SignalLog;  pcc = S.PCC;
else
    SL = evalin('base','SignalLog');  pcc = evalin('base','PCC');
end
g = @(n) SL.get(n).Values;

%% Voltage from raw phase voltages: half-cycle and one-cycle RMS
t  = pcc.time(:);  v = pcc.signals.values;  dt = median(diff(t));
tE = min(tE, max(t));
vab = v(:,1)-v(:,2);  vbc = v(:,2)-v(:,3);  vca = v(:,3)-v(:,1);
rmsw = @(x,n) sqrt(movmean(x.^2,[n-1 0]));
wins = [round(0.5/P.f0/dt), round(1/P.f0/dt)];
post = t >= tT & t <= tE;
vmin = zeros(1,2);  tbel = zeros(1,2);
for k = 1:2
    Vm = min([rmsw(vab,wins(k)) rmsw(vbc,wins(k)) rmsw(vca,wins(k))],[],2)/P.V_town;
    vmin(k) = min(Vm(post));
    tbel(k) = sum(post & Vm < 1-P.dV_proj)*dt;
end
Vb = g('Vab_rms');  vb = squeeze(Vb.Data)/P.V_town;  tvb = Vb.Time;
vbmin = min(vb(tvb >= tT & tvb <= tE));

%% Frequency
F = g('Freq_pcc');  fd = squeeze(F.Data);  tf = F.Time;
m  = tf >= tT & tf <= tE;  tm = tf(m);  [fmin,i] = min(fd(m));
fend = mean(fd(tf >= tE-1 & tf <= tE));

%% Inverter loading and PV at the event
Pcc = g('P_pcc_kW');  tp = Pcc.Time;  pl = squeeze(Pcc.Data)/1000;
Si = zeros(size(tp));
peak = zeros(1,3);  last = zeros(1,3);
for k = 1:3
    Pk = g(sprintf('Pmeas_BS%d',k));
    dk = squeeze(Pk.Data);  tk = Pk.Time;
    Si = Si + interp1(tk, dk, tp)*P.bess.block_MW;
    peak(k) = max(dk(tk >= tT & tk <= tE));
    last(k) = mean(dk(tk >= tE-1 & tk <= tE));
end
pre = tp >= tT-0.1 & tp < tT;
pvTrip = mean(pl(pre) - Si(pre));
inSvc  = last > 0.02;
peakLoad = max(peak(inSvc));  endLoad = mean(last(inSvc));

fprintf('=== %s: event at %.1f s, window %.1f-%.1f s ===\n', tag, tT, tT, tE);
fprintf('PV injecting just before the event: %.2f MW\n', pvTrip);
fprintf('Frequency minimum in window       : %.3f Hz at %.3f s | last second mean %.3f Hz\n', fmin, tm(i), fend);
fprintf('Voltage min, half-cycle RMS       : %.4f pu (%.2f%%) | below 0.94 pu for %.4f s\n', vmin(1), 100*(vmin(1)-1), tbel(1));
fprintf('Voltage min, one-cycle RMS        : %.4f pu (%.2f%%) | below 0.94 pu for %.4f s\n', vmin(2), 100*(vmin(2)-1), tbel(2));
fprintf('Voltage min, PCC block output     : %.4f pu (%.2f%%)\n', vbmin, 100*(vbmin-1));
fprintf('Inverters in service: %d | peak loading %.3f pu (headroom %.1f%%), last second %.3f pu\n', ...
    nnz(inSvc), peakLoad, 100*(1-peakLoad), endLoad);
end