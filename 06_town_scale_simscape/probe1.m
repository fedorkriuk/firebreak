mdl = 'ts_b04_grid';
gt = find_system(mdl,'SearchDepth',1,'BlockType','Goto');
for i = 1:numel(gt)
    tag = get_param(gt{i},'GotoTag');
    if ~ismember(tag,{'Droop_On','Ctrl_On'}), continue; end
    pc  = get_param(gt{i},'PortConnectivity');
    src = pc(1).SrcBlock;
    fprintf('\n=== Goto tag %s  (block %s)\n', tag, strrep(gt{i},newline,' '));
    if isempty(src), fprintf('   nothing connected upstream\n'); continue; end
    fprintf('   fed by: %s | BlockType=%s | MaskType=%s\n', strrep(getfullname(src),newline,' '), ...
        get_param(src,'BlockType'), get_param(src,'MaskType'));
    dp = get_param(src,'DialogParameters');
    if isstruct(dp)
        fn = fieldnames(dp);
        for j = 1:numel(fn)
            v = get_param(src,fn{j});
            if ischar(v), fprintf('   %-22s = %s\n', fn{j}, v); end
        end
    end
end