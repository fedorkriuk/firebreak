mdl = 'ts_b04_grid';
lh = get_param([mdl '/Grid_Breaker'],'LineHandles');
for k = 1:3
    h = lh.RConn(k);
    while get_param(h,'LineParent') ~= -1, h = get_param(h,'LineParent'); end   % climb to the root of the net
    sp = get_param(h,'SrcPortHandle');
    if sp ~= -1
        fprintf('Breaker RConn%d -> net rooted at %s, port %s\n', k, ...
            strrep(get_param(get_param(sp,'Parent'),'Name'),newline,' '), get_param(sp,'PortType'));
    else
        fprintf('Breaker RConn%d -> net root has no source port (paste this line)\n', k);
    end
end