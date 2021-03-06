import sys, re
import stuff

props = map(str, stuff.unrangeify(sys.argv[1]))

more = []
who = None
votes = {}
line = '\t'
pn = None
def end():
    line = who
    for prop in props:
        if prop in votes:
            v = votes[prop]
            del votes[prop]
        else:
            v = ''
        line += '\t' + v
    print line
    if votes:
        print 'leftover votes:', votes
print '\t' + '\t'.join(props) + '\tVL'
for line in sys.stdin:
    line = line.strip()
    if not line: continue
    if line.startswith('- '):
        if who is not None: end()
        who = line[2:]
        continue
    if not line.startswith('> ') and re.search('AGAINST|FOR|PRESENT', line):
        m = re.match('(AGAINST|FOR|PRESENT)\s+([0-9]+)', line)
        n = re.match('([0-9]+)\s+(AGAINST|FOR|PRESENT)', line)
        if m:
            votes[m.group(2)] = m.group(1)[0]
        elif n:
            votes[m.group(1)] = m.group(2)[0]
        elif re.match('AGAINST|FOR|PRESENT', line) and pn is not None:
            votes[pn] = line[0]
        if line not in ('AGAINST', 'FOR', 'PRESENT') and not re.match('[0-9]{4}\s+[0-9]', line):
            more.append('** %s %s %s' % (pn, who, line))
    m = re.match('(> )?(Proposal |ID: )?([0-9]{4})', line)
    if m:
        pn = m.group(3)
        votes.setdefault(pn, '?')
if votes: end()
for line in sorted(more): print line
