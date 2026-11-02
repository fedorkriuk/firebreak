%% b02_fix50.m - replace remaining standalone 60 with 50 in frequency parameters
mdl = 'ts_b02_island';
if ~bdIsLoaded(mdl), load_system(fullfile(pwd,'models',[mdl '.slx'])); end
names = {'Finit','Par_Init','Fnom','Freg_Limits'};
blks  = find_system(mdl,'LookUnderMasks','all','FollowLinks','on','Type','Block');
n = 0;
for i = 1:numel(blks)
    try, dp = get_param(blks{i},'DialogParameters'); catch, continue, end
    if isempty(dp) || ~isstruct(dp), continue, end
    for k = 1:numel(names)
        if ~isfield(dp,names{k}), continue, end
        v  = get_param(blks{i},names{k});
        v2 = regexprep(v,'(?<![\d.])60(?!\d)','50');
        if ~strcmp(v,v2)
            set_param(blks{i},names{k},v2);
            fprintf('%s | %s: %s -> %s\n', strrep(blks{i},newline,' '), names{k}, v, v2);
            n = n + 1;
        end
    end
end
save_system(mdl);
fprintf('%d parameters changed.\n', n);