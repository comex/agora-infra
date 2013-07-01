import re, aword, sys

def power2str(power):
    if power % 1 == 0:
        return str(int(power))
    else:
        return str(power)

mode = sys.argv[2] if len(sys.argv) > 2 else 'check'
separator = '\n----------------------------------------------------------------------\n'
f = open(sys.argv[1], 'r')
flr = f.read()
f.close()
m = re.findall(' \n', flr, re.M)
if m:
    for j in m:
        print '*** %s' % repr(j)
    sys.exit(1)
#idx_order = map(int, re.findall('^      Rule +([0-9]+)', flr, re.M))
data = flr.split(separator)
catdescs = {}
catas = []
order = []
powers = {}
rules = {}
for d in data:
    d = d.strip()
    if re.match('^======================================================================', d):
        _, catname, catdesc = d.split('\n', 2)
        catname = catname.strip()
        catdesc = aword.aunwrap(catdesc)
        catas.append(catname)
        catdescs[catname] = catdesc
    else:
        m = re.match('^Rule ([0-9]+)\/[0-9]+ \(Power=([0-9\.]+)\)', d)
        if m:
            rn = int(m.group(1))
            order.append(rn)
            powers[rn] = float(m.group(2))
            rules[rn] = d
idx_catas = []
idx_order = []
idx_both = []
for line in data[3].split('\n'):
    m = re.match('^      Rule +([0-9]+)', line)
    if m:
        rn = int(m.group(1))
        idx_order.append(rn)
        idx_both.append(('rule', rn))
    m = re.match('^      \* (.*)$', line)
    if m:
        cname = m.group(1)
        idx_catas.append(cname)
        idx_both.append(('cata', cname))
#idx_catas = re.findall('^      \* (.*)$', data[3], re.M)
cidx_catas = re.findall('^      \* (.*)$', data[2], re.M)
#assert sorted(order) == sorted(idx_order)
if mode == 'check':
    assert cidx_catas == idx_catas
    assert cidx_catas == catas
    assert order == idx_order
    sys.exit(0)
elif mode != 'fix':
    print 'unknown mode'
    sys.exit(1)

# use idx_order and idx_catas to rebuild the ruleset.
newdata = []
newdata.append(data[0])
s = '\nStatistics\n\nCurrent total number of rules: %d\n\nPower distribution:\n' % len(order)
pv = powers.values()
for power in sorted(set(pv), reverse=True):
    s += '%s with Power=%s\n' % (str(pv.count(power)).rjust(8), power2str(power))
newdata.append(s)

s = '\nIndex of Categories\n\n'
for cata in idx_catas:
    s += '      * %s\n' % cata

newdata.append(s)
newdata.append(data[3]) # index of rules
newdata.append(data[4]) # notes
for kind, x in idx_both:
    if kind == 'cata':
        s = '\n======================================================================\n%s\n%s' % (x, aword.awrap(catdescs.get(x, '(TODO: description)')))
        newdata.append(s)

    elif kind == 'rule':
        newdata.append('\n%s\n' % rules[x])
newdata.append(data[-1]) # end of FLR
print separator.join(newdata).rstrip()

#print data
#print idx_order
