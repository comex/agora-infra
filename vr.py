quorum = 0

import sys, re
from collections import OrderedDict, Counter
from stuff import lblrangeify, twrap, RowTable
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
                # x - marker for non-punter (retracted/conditional)
                assert vote[0] in ('F', 'A', 'P', 'x')
                vlist += [vote[0]] * count
            vlist[vl:] = []

for line, num in re.findall('^(([0-9]{4}) .*?)\s*$', stuff[1], re.M):
    prop = pbn[int(num)]
    prop['line'] = line

m = re.search('Quorum is ([0-9]+)', stuff[1][:stuff[1].find('}{}{')])
if m:
    quorum = int(m.group(1))

#for text, num, ai, pf, authors in re.findall('\n(}{}{}[^\n]*\n\nProposal ([0-9]+) \(AI=([^,]*), PF=Y([^,]*)[^\)]*\) by ([^\n]*).*?)(?=\n(?:\n*$|}{}{}))', stuff[1], re.S):
for text, num, title, authors, ai in re.findall('\n(}{}{}[^\n]*\n\nID: ([0-9]+)\nTitle: ([^\n]*)\nAuthor: ([^\n]*)\nAdoption Index: ([^\n]*)\n\n.*?)(?=\n(?:\n*$|}{}{}))', stuff[1], re.S):
    prop = pbn[int(num)]
    prop['ai'] = float(ai)
    #prop['pf'] = int(pf)
    prop['text'] = text
    prop['authors'] = authors.split(', ')

props.sort(key=lambda prop: prop['num'])
players = sorted(players, key=lambda p: p.lower())

points_proposals = Counter()
points_voting = Counter()
points_purses = Counter()

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
    lucrative_vote = None
    if prop['n'] < quorum:
        prop['result'] = '!'
    elif prop['vi'] is None or (prop['vi'] > 1 and prop['vi'] >= prop['ai']):
        prop['result'] = '*'
        lucrative_vote = 'A'
        for author in prop['authors']:
            # *** does not take into account previous weekly gains
            points_proposals[author] = min(15, points_voting[author] + int(prop['ai']))
    else:
        prop['result'] = 'x'
        lucrative_vote = 'F'

    prop['lucky'] = lucky = [player for (player, votes) in prop['votes'].items() if votes == [lucrative_vote] * len(votes)]
    prop['purse'] = quorum * 10 + 10
    prop['purse_per'] = None if not lucky else max(prop['purse'] / len(lucky), 1)
    for player in lucky:
        points_purses[player] += prop['purse_per']
    # *** ditto
    for voter in prop['votes'].keys():
        points_voting[voter] += 5

    prop['summary'] = {}
    for player, votes in prop['votes'].items():
        summary = OrderedDict()
        for vote in votes:
            if vote in summary: continue
            count = votes.count(vote)
            summary[vote] = vote if count == 1 else '%d%s' % (count, vote)
        prop['summary'][player] = '+'.join(summary.values())

    prop['q'] = quorum
    quorum = prop['n'] - 3

print 'Voting results for %s:' % lblrangeify([prop['num'] for prop in props], 'Proposal')

if len(props) > 1:
    print '''
[This notice resolves the Agoran decisions of whether to adopt the
 following proposals.  For each decision, the options available to
 Agora are ADOPTED (*), REJECTED (x), and FAILED QUORUM (!).]
'''
else:
    print '''
[This notice resolves the Agoran decision of whether to adopt the
 following proposal.  The options available to Agora are ADOPTED (*),
 REJECTED (x), and FAILED QUORUM (!).]
'''

for prop in props:
    print prop['result'] + prop['line']

print

t = RowTable()
lines = {}
lines['s'] = t.row('')
t.row()
for player in players:
    lines['v' + player] = t.row(player)
t.row()
lines['ai'] = t.row('AI')
lines['vi'] = t.row('VI')
lines['fa'] = t.row('F/A')
t.row()
lines['q'] = t.row('Quorum')
lines['n'] = t.row('Voters')
lines['p'] = t.row('Purse')

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
    lines['q'].append(str(prop['q']))
    lines['n'].append(str(prop['n']))
    lines['p'].append(str(prop['purse']))

t.print_all()

print
print 'Ending Quorum: %s' % quorum

if notes:
    print
    for note in notes: print note

if points_purses:
    print
    print 'Purse Splits'
    for prop in props:
        if prop['purse_per'] is None:
            print '%-7s    -' % prop['num']
        else:
            print twrap('%-7s(%2d) %s' % (prop['num'], prop['purse_per'], ', '.join(prop['lucky'])), subsequent_indent=12)

print

t = RowTable()
t.row(['Points Awarded', '>Proposals', '>Voting', '>Purses', '>Total'])
for player in set(points_proposals.keys() + points_voting.keys() + points_purses.keys()):
    t.row([player,
        str(points_proposals[player] or ''),
        str(points_voting[player] or ''),
        str(points_purses[player] or ''),
        str(points_proposals[player] + points_voting[player] + points_purses[player] or ''),
    ])
t.print_all()


#print 'Yak awards:'
#print_awards(yaks, True)

print '''

Text of adopted proposals:
'''

some = False
for prop in props:
    if prop['result'] == '*':
        print prop['text']
        some = True

if not some:
    print '(none)'
