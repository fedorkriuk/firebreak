%% b02_dump2.m - values needed to rescale to 22 kV / MW
mdl = 'ts_b02_island'; load_system(mdl);

sup = [mdl '/Microgrid Supervisory Control'];
fprintf('--- Supervisory mask\n');
n = get_param(sup,'MaskNames'); v = get_param(sup,'MaskValues');
for k = 1:numel(n), fprintf('%s = %s\n', n{k}, v{k}); end

fprintf('--- Stair generators (t = times, e = values)\n');
for nm = {'Pdyn','Qdyn','Stair Generator4','Stair Generator5'}
    p = [mdl '/' nm{1}];
    fprintf('%s: t=%s | e=%s | Ts=%s\n', nm{1}, get_param(p,'t'), get_param(p,'e'), get_param(p,'Ts'));
end

fprintf('--- Blocks of interest\n');
b  = find_system(mdl,'LookUnderMasks','all','FollowLinks','on','RegExp','on', ...
                 'Name','PI regulator.*|C1|Load1|Load2|Variable load');
b  = [b; find_system(mdl,'LookUnderMasks','all','FollowLinks','on','BlockType','RateLimiter')];
for i = 1:numel(b)
    fprintf('\n%s\n', strrep(b{i},newline,' '));
    try, dp = get_param(b{i},'DialogParameters'); catch, continue, end
    if ~isstruct(dp), continue, end
    fn = fieldnames(dp);
    for k = 1:numel(fn)
        try, val = get_param(b{i},fn{k}); if ischar(val), fprintf('  %s = %s\n', fn{k}, val); end, catch, end
    end
end