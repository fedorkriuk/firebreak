function s17_grid_summary(tag, matfile, tOpen)
%S17_GRID_SUMMARY  Grid-connected operation before the line breaker opens, balance check, 3-panel figure.
%  s17_grid_summary('gridloss_noPV','',7)                 workspace data, breaker opens at 7 s
%  s17_grid_summary('gridloss_noPV','results/run_gridloss_noPV.mat',7)   saved file
if nargin < 1, tag = 'gridrun'; end
if nargin < 2, matfile = ''; end
if nargin < 3, tOpen = 7; end
P = town_params();
if ~isempty(matfile), S = load(matfile); SL = S.SignalLog;
else, SL = evalin('base','SignalLog'); end
g = @(n) SL.get(n).Values;

Pcc = g('P_pcc_kW');  tp = Pcc.Time(:);  pl = squeeze(Pcc.Data)/1000;  pl = pl(:);
Pb = zeros(size(tp));  Qb = zeros(size(tp));  puM = zeros(numel(tp),3);
for k = 1:3
    a = g(sprintf('Pmeas_BS%d',k));  q = g(sprintf('Qmeas_BS%d',k));
    v = interp1(a.Time, squeeze(a.Data), tp);  puM(:,k) = v(:);
    Pb = Pb + puM(:,k)*P.bess.block_MW;
    w = interp1(q.Time, squeeze(q.Data), tp);  Qb = Qb + w(:)*P.bess.block_MW;
end
pv  = g('PV_Pcmd');
ppv = interp1(pv.Time, squeeze(pv.Data), tp)/1e6;  ppv = ppv(:);
Pg  = pl - Pb - ppv;                       % MW imported from the grid (+) / exported (-)

F = g('Freq_pcc');  tf = F.Time(:);  fd = squeeze(F.Data);  fd = fd(:);
V = g('Vab_rms');   tv = V.Time(:);  vv = squeeze(V.Data)/P.V_town;  vv = vv(:);

w1 = tp >= tOpen-1.5 & tp < tOpen-0.1;      % grid-connected, droop on (3 s), settled
fprintf('=== %s: grid connected, window %.1f-%.1f s ===\n', tag, tOpen-1.5, tOpen-0.1);
fprintf('Load %.3f MW | batteries %.3f MW | PV %.3f MW | grid import %.3f MW\n', ...
    mean(pl(w1)), mean(Pb(w1)), mean(ppv(w1)), mean(Pg(w1)));
fprintf('Battery loading per inverter (pu): %.3f  %.3f  %.3f | battery Q %.3f MVAr\n', mean(puM(w1,:),1), mean(Qb(w1)));
fprintf('Frequency %.3f Hz | Vab_rms %.4f pu\n', mean(fd(tf>=tOpen-1.5 & tf<tOpen-0.1)), mean(vv(tv>=tOpen-1.5 & tv<tOpen-0.1)));
w2 = tp >= tOpen+1;
fprintf('After the breaker opens: load - batteries - PV = %.3f MW (should be ~0)\n', mean(Pg(w2)));

fig = figure('Name',['Grid test ' tag]);
subplot(3,1,1); plot(tp,pl,tp,Pb,tp,Pg); legend('load','batteries','grid'); ylabel('MW'); grid on
title(['Grid test: ' tag ' (line opens at ' num2str(tOpen) ' s)']);
subplot(3,1,2); plot(tf,fd); ylabel('Hz'); grid on
subplot(3,1,3); plot(tv,vv); ylabel('Vab\_rms (pu)'); xlabel('Time (s)'); grid on
if ~exist('figures','dir'), mkdir('figures'); end
saveas(fig, fullfile('figures',['grid_' tag '.png']));
end