mdl = 'ts_b02e_3x6';
out = sim(mdl);
whos
disp(out.who)
if exist('PCC','var')
    disp(class(PCC)); disp(size(PCC));
    if isstruct(PCC), disp(PCC), end
end
if isfield(struct(out),'PCC') || any(strcmp(out.who,'PCC'))
    x = out.PCC; disp(class(x)); disp(size(x));
    if isstruct(x), disp(x), end
end