%% b01_sps.m - ideal 22 kV / 50 Hz source + 10 MW load (SPS library). UNTESTED: paste errors.
P   = town_params();
mdl = 'ts_b01_sps';
if bdIsLoaded(mdl), close_system(mdl,0); end
new_system(mdl); open_system(mdl);
Ts = 50e-6; assignin('base','Ts',Ts);
set_param(mdl,'SolverType','Fixed-step','Solver','FixedStepDiscrete', ...
              'FixedStep','Ts','StopTime','0.5');

add_block('powerlib/powergui',[mdl '/powergui'],'Position',[20 20 100 60]);
set_param([mdl '/powergui'],'SimulationMode','Discrete','SampleTime','Ts');
try set_param([mdl '/powergui'],'frequency','50'); catch ME, disp(ME.message); end

add_block('powerlib/Electrical Sources/Three-Phase Source',[mdl '/Source'],'Position',[60 150 130 220]);
add_block('powerlib/Measurements/Three-Phase V-I Measurement',[mdl '/VI'],'Position',[220 150 290 220]);
add_block('powerlib/Elements/Three-Phase Series RLC Load',[mdl '/Load'],'Position',[400 150 470 220]);

Pld = P.load.P_ess_peak*1e6;  Qld = Pld*tan(acos(P.load.pf));
set_param([mdl '/Source'],'Voltage','22e3','Frequency','50');
set_param([mdl '/Source'],'Resistance','1e-4','Inductance','1e-6');
set_param([mdl '/Load'],'NominalVoltage','22e3','NominalFrequency','50', ...
          'ActivePower',num2str(Pld),'InductivePower',num2str(Qld), ...
          'CapacitivePower','0');
set_param([mdl '/Source'],'InternalConnection','Yg');
set_param([mdl '/Load'],'Configuration','Y (grounded)');
% measure line-to-line so no ground reference is needed
set_param([mdl '/VI'],'VoltageMeasurement','phase-to-phase','CurrentMeasurement','yes');

for k = 1:3
    add_line(mdl,sprintf('Source/RConn%d',k),sprintf('VI/LConn%d',k),'autorouting','on');
    add_line(mdl,sprintf('VI/RConn%d',k),sprintf('Load/LConn%d',k),'autorouting','on');
end

add_block('simulink/Sinks/To Workspace',[mdl '/Vabc'],'VariableName','Vabc','SaveFormat','Timeseries','Position',[360 60 420 90]);
add_block('simulink/Sinks/To Workspace',[mdl '/Iabc'],'VariableName','Iabc','SaveFormat','Timeseries','Position',[360 100 420 130]);
add_line(mdl,'VI/1','Vabc/1','autorouting','on');
add_line(mdl,'VI/2','Iabc/1','autorouting','on');

save_system(mdl, fullfile('models',[mdl '.slx']));
out = sim(mdl);

t = out.Vabc.Time; v = out.Vabc.Data; i = out.Iabc.Data;
w = t > 0.2;
Vll = rms(v(w,1)); Il = rms(i(w,1));
p = mean(v(w,1).*i(w,1) - v(w,2).*i(w,3));
fprintf('Vll %.0f V (expect 22000), Vph %.0f V (expect 12702)\n', Vll, Vll/sqrt(3));
fprintf('I   %.1f A (expect 263), P %.2f MW (expect 10)\n', Il, p/1e6);