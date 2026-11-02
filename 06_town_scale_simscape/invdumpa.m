% B. Dump everything inside Inverter 1 (top level of the subsystem only) and what each port connects to
s = 'ts_b02d_trip/Inverter 1 500 kW';
b = find_system(s,'LookUnderMasks','all','FollowLinks','on','SearchDepth',1,'Type','Block');
for i = 2:numel(b)          % entry 1 is the subsystem itself
    fprintf('\n%s | %s\n', strrep(b{i},newline,' '), get_param(b{i},'BlockType'));
    pc = get_param(b{i},'PortConnectivity');
    for j = 1:numel(pc)
        tgt = [pc(j).SrcBlock pc(j).DstBlock];
        tgt = tgt(tgt > 0);
        names = arrayfun(@(h) strrep(get_param(h,'Name'),newline,' '), tgt, 'UniformOutput', false);
        fprintf('    port %d (%s) -> %s\n', j, pc(j).Type, strjoin(names,', '));
    end
end