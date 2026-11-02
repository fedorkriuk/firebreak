function b02_scan(mdl, pattern)
%B02_SCAN  Print every block parameter whose text matches a regex.
blks = find_system(mdl,'LookUnderMasks','all','FollowLinks','on','Type','Block');
for i = 1:numel(blks)
    try dp = get_param(blks{i},'DialogParameters'); catch, continue, end
    if isempty(dp) || ~isstruct(dp), continue, end
    fn = fieldnames(dp);
    for k = 1:numel(fn)
        try v = get_param(blks{i},fn{k}); catch, continue, end
        if ischar(v) && ~isempty(regexp(v,pattern,'once'))
            fprintf('%s | %s = %s\n', strrep(blks{i},newline,' '), fn{k}, v);
        end
    end
end
end