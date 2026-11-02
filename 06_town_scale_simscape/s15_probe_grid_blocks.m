%% s15_probe_grid_blocks.m
% READ-ONLY on your models. Tests grid-side candidates in a throw-away scratch model.
cand = { ...
 'powerlib/Electrical Sources/Three-Phase Source', ...
 'powerlib/Electrical Sources/Three-Phase Programmable Voltage Source', ...
 'powerlib/Elements/Three-Phase PI Section Line', ...
 'powerlib/Elements/Distributed Parameters Line', ...
 'powerlib/Elements/Three-Phase Fault', ...
 'powerlib/Elements/Three-Phase Breaker', ...
 'powerlib/Elements/Three-Phase Transformer (Two Windings)', ...
 'powerlib/Elements/Three-Phase Series RLC Branch', ...
 'powerlib/Elements/Ground'};
sys = 'ts_scratch_probe3';
if bdIsLoaded(sys), close_system(sys,0); end
new_system(sys);
for k = 1:numel(cand)
    fprintf('\n--- %s ---\n', cand{k});
    try
        b  = add_block(cand{k}, [sys '/blk' num2str(k)]);
        ph = get_param(b,'PortHandles');
        fprintf('ports: %s\n', strjoin(cellfun(@(f) sprintf('%s=%d',f,numel(ph.(f))), ...
            fieldnames(ph),'UniformOutput',false),' '));
        dumpParams(b);
    catch ME
        fprintf('FAIL: %s\n', strtok(ME.message, newline));
    end
end
close_system(sys,0);
fprintf('\nScratch model closed. Nothing saved.\n');

function dumpParams(b)
    dp = get_param(b,'DialogParameters');
    if isempty(dp), fprintf('  (no dialog parameters)\n'); return; end
    for n = fieldnames(dp)'
        try, v = get_param(b,n{1}); catch, v = '?'; end
        if isnumeric(v), v = mat2str(v); end
        e = '';
        try
            if isfield(dp.(n{1}),'Enum') && ~isempty(dp.(n{1}).Enum)
                e = [' | options: ' strjoin(dp.(n{1}).Enum,' / ')];
            end
        end
        fprintf('  %-22s = %s%s\n', n{1}, v, e);
    end
end