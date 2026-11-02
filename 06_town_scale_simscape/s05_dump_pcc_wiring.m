%% s05_dump_pcc_wiring.m
% READ-ONLY. Prints what is on the top level of the open model and how the
% inverters, loads and PCC bus are wired, so B3 (PV) can be connected correctly.
% Run with ts_b02f_log open. It changes nothing.
mdl = bdroot;
nm  = @(h) strrep(get_param(h,'Name'),newline,' ');
fprintf('Model: %s\n\n', mdl);

%% 1. Every top-level block
b = find_system(mdl,'SearchDepth',1,'Type','Block');
fprintf('--- Top-level blocks (%d) ---\n', numel(b));
for k = 1:numel(b)
    bt = get_param(b{k},'BlockType');
    mt = '';  rb = '';
    try, mt = get_param(b{k},'MaskType'); end
    try, rb = get_param(b{k},'ReferenceBlock'); end
    fprintf('%-28s | %-12s | mask: %-22s | ref: %s\n', nm(b{k}), bt, mt, rb);
end

%% 2. Goto / From tags
fprintf('\n--- Goto tags ---\n');
g = find_system(mdl,'SearchDepth',1,'BlockType','Goto');
for k = 1:numel(g)
    fprintf('Goto  [%s]  visibility %s\n', get_param(g{k},'GotoTag'), get_param(g{k},'TagVisibility'));
end
fprintf('--- From tags ---\n');
f = find_system(mdl,'SearchDepth',1,'BlockType','From');
for k = 1:numel(f)
    fprintf('From  [%s]\n', get_param(f{k},'GotoTag'));
end

%% 3. Port-by-port connectivity for the electrical blocks
fprintf('\n--- Physical connections ---\n');
pat = 'Inverter|Load|PCC bus|PCC Measurements';
for k = 1:numel(b)
    if isempty(regexp(nm(b{k}), pat, 'once')), continue; end
    fprintf('\n[%s]\n', nm(b{k}));
    ph = get_param(b{k},'PortHandles');
    for fld = fieldnames(ph)'
        hs = ph.(fld{1});
        for i = 1:numel(hs)
            ln = -1;
            try, ln = get_param(hs(i),'Line'); end
            if ln <= 0
                fprintf('  %s(%d): no line\n', fld{1}, i);
                continue
            end
            s = '?'; d = '?'; nc = 0;
            try, sb = get_param(ln,'SrcBlockHandle'); if sb>0, s = nm(sb); end, end
            try, db = get_param(ln,'DstBlockHandle'); if all(db>0), d = strjoin(arrayfun(nm,db,'UniformOutput',false),','); end, end
            try, nc = numel(get_param(ln,'LineChildren')); end
            fprintf('  %s(%d): line %.0f  src=%s  dst=%s  branches=%d\n', fld{1}, i, ln, s, d, nc);
        end
    end
end