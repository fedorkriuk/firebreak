% listbreaker_test.m
load_system('powerlib');
mdl = 'scratch_brk';
if bdIsLoaded(mdl), close_system(mdl,0); end
new_system(mdl);
cands = {'powerlib/Elements/Three-Phase Breaker', ...
         'powerlib/Elements/Breaker', ...
         'powerlib/Elements/Three-Phase Fault'};
for i = 1:numel(cands)
    try
        b = add_block(cands{i}, [mdl '/T' num2str(i)]);
        fprintf('\nFOUND: %s\n', cands{i});
        dp = get_param(b,'DialogParameters');
        disp(fieldnames(dp));
        pc = get_param(b,'PortConnectivity');
        fprintf('  ports: %d\n', numel(pc));
        for j = 1:numel(pc), fprintf('   port %d type %s\n', j, pc(j).Type); end
    catch ME
        fprintf('\nNOT FOUND: %s\n   %s\n', cands{i}, ME.message);
    end
end
close_system(mdl,0);