quorum = 6

import sys, re
from collections import OrderedDict
notes = []
props = []
pbn = {}
players = set()
stuff = sys.stdin.read().split('\n--\n')
for line in stuff[0].split('\n'):
    line = line.rstrip()
    if not line: continue
    if line.startswith('* '):
        notes.append(line[2:])
        continue
    line = line.split('\t')
    if line[0] == '':
        for num in line[1:-1]:
            num = int(num)
            prop = {'num': int(num)}
            pbn[num] = prop
            props.append(prop)
    #elif line[0] == 'AI':
    #    for prop, ai in zip(props, line[1:]):
    #        prop['ai'] = float(ai)
    else:
        player = line[0]
        players.add(player)
        vl = int(line[-1])
        for prop, votes in zip(props, line[1:-1]):
            vlist = prop.setdefault('votes', {}).setdefault(player, [])
            votes = re.split('\s*,\s*', votes)
            for vote in votes:
                if vote == '-' or not vote: continue
                # todo make this more comprehensive
                m = re.search('([0-9]+)(.*)', vote)
                if m:
                    count = int(m.group(1))
                    vote = m.group(2)
                elif len(votes) == 1:
                    count = vl
                else:
                    count = 1
                vlist += [vote[0]] * count
            vlist[vl:] = []

for line, num in re.findall('^(([0-9]{4}) .*?)\s*$', stuff[1], re.M):
    prop = pbn[int(num)]
    prop['line'] = line

m = re.search('Quorum is ([0-9]+)\.', stuff[1][:stuff[1].find('}{}{')])
if m:
    quorum = m.group(1)

for text, num, ai, pf, authors in re.findall('\n(}{}{}[^\n]*\n\nProposal ([0-9]+) \(AI=([^,]*), PF=Y([^,]*)[^\)]*\) by ([^\n]*).*?)(?=\n(?:\n*$|}{}{}))', stuff[1], re.S):
    prop = pbn[int(num)]
    prop['ai'] = float(ai)
    prop['pf'] = int(pf)
    prop['text'] = text
    prop['authors'] = authors.split(', ')

props.sort(key=lambda prop: prop['num'])
players = sorted(players, key=lambda p: p.lower())

yaks = {}
vcs = {}
for prop in props:
    prop['f'] = prop['a'] = prop['n'] = 0
    for votes in prop['votes'].values():
        for vote in votes:
            if vote == 'F':
                prop['f'] += 1
            elif vote == 'A':
                prop['a'] += 1
        if votes: prop['n'] += 1
    prop['vi'] = None if prop['a'] == 0 else (float(prop['f']) / prop['a'])
    if prop['n'] < quorum:
        prop['result'] = '!'
    elif prop['vi'] is None or (prop['vi'] > 1 and prop['vi'] >= prop['ai']):
        prop['result'] = '*'
        for i, author in enumerate(prop['authors']):
            pf = prop['pf']
            if i >= 1:
                pf /= 3
            else:
                vcs[author] = vcs.get(author, 0) + 1
            if pf:
                yaks[author] = yaks.get(author, 0) + pf
    else:
        prop['result'] = 'x'

    prop['summary'] = {}
    for player, votes in prop['votes'].items():
        summary = {}
        for vote in votes:
            if vote in summary: continue
            count = votes.count(vote)
            summary[vote] = vote if count == 1 else '%d%s' % (count, vote)
        prop['summary'][player] = '+'.join(summary.values())

from stuff import andify, rangeify
print 'Voting results for Proposals %s:' % rangeify(prop['num'] for prop in props)

print '''
[This notice resolves the Agoran decisions of whether to adopt the
 following proposals.  For each decision, the options available to
 Agora are ADOPTED (*), REJECTED (x), and FAILED QUORUM (!).]
'''

for prop in props:
    print prop['result'] + prop['line']

print

lines = OrderedDict()
lines['s'] = ['']
lines['pad1'] = ['']
for player in players:
    lines['v' + player] = [player]
lines['pad2'] = ['']
lines['ai'] = ['AI']
lines['vi'] = ['VI']
lines['fa'] = ['F/A']
lines['pad3'] = ['']
lines['q'] = ['Quorum']
lines['n'] = ['Voters']

for prop in props:
    lines['s'].append(str(prop['num']))
    for player in players:
        lines['v' + player].append('')
    for player, summary in prop['summary'].items():
        lines['v' + player][-1] = summary
    lines['ai'].append(('%f' % prop['ai']).rstrip('0.'))
    if prop['vi'] is None:
        vi = '*U*'
    else:
        vi = ('%.1f' % prop['vi']).rstrip('0.') or '0'
        if prop['vi'] > float(vi):
            vi += '+'
    lines['vi'].append(vi)
    lines['fa'].append('%s/%s' % (prop['f'], prop['a']))
    lines['q'].append(str(quorum))
    lines['n'].append(str(prop['n']))

llen = 0
out = [''] * len(lines)
def printit():
    global out
    for o in out:
        print o.rstrip()
    out = [''] * len(lines)
def printcol(i):
    global llen
    cells = [line[i] if len(line) > i else '' for line in lines.values()]
    clen = max(map(len, cells))
    if llen + clen > 80:
        printit()
        print
        llen = 0
        printcol(0)
    clen += 3 if i == 0 else 2
    llen += clen
    for j, val in enumerate(cells):
        out[j] += val.ljust(clen)

for i in xrange(max(map(len, lines.values()))):
    printcol(i)
printit()

def print_awards(xs, is_yaks):
    xs = xs.items()
    if len(xs) == 0:
        print '  (none)'
    else:
        plen = max(len(who) for who, num in xs)
        for who, num in xs:
            print '  %-*s  %s%s' % (plen, who, 'Y' if is_yaks else '', num)

if notes:
    print
    for note in notes: print note

print
print 'Yak awards:'
print_awards(yaks, True)

print
print 'VC awards:'
print_awards(vcs, False)

print '''

Text of adopted proposals:
'''

for prop in props:
    if prop['result'] == '*':
        print prop['text']

