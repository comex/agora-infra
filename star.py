import sys, os, hashlib, re, random, string
import stuff

mailboiler = '''From: "omd" <comex@vps.qoid.us>
To: "%s" <%s>
Reply-To: "omd" <c.ome.xk@gmail.com>
Subject: [Promotor] %s's %s for %s %s

Hi!  I'm a bot owned by the Promotor.  You are receiving this message because you're listed as an active player of Agora Nomic, and the voting %s of %s in the Star Chamber %s just started.  The Star Chamber (R2409) is designed for secret voting: to cast a vote on a proposal, you must use your code for that proposal in the %s listed below, which I will publicly post at the end of the voting period to allow votes to be verified.

I have publicly posted the SHA-1 %s of each Codebook, which you may use to verify that I have honestly reported yours in this message.  Hashes are to be computed without trailing newlines.  An online SHA-1 calculator may be found at:
http://www.movable-type.co.uk/scripts/sha1.html
'''
def getmailboiler(name, email, nums):
    n = len(nums)
    if n == 1:
        return mailboiler % (name, email, name, 'Codebook', 'Proposal', nums[0], 'period', 'a proposal', 'has', 'Codebook', 'hash')
    else:
        return mailboiler % (name, email, name, 'Codebooks', 'Proposals', stuff.rangeify(nums), 'periods', '%d proposals' % n, 'have', 'Codebooks', 'hashes')

def readplayers(fn):
    on = False
    fp = open(fn)
    for line in fp:
        if line.startswith('  Player'):
            colstarts = stuff.getcolstarts(line)
        if line.startswith(' - First-class'): break
    players = []
    for line in fp:
        if line.startswith(' - Second-class'): break
        cells = stuff.colify(line, colstarts)
        cells = [re.sub(' \[[0-9]*\]', '', cell) for cell in cells]
        players.append(cells[:2])
    return players

def getbase(num):
    return '../starchamber/' + num
def mkdir(fn):
    if not os.path.exists(fn):
        os.mkdir(fn)
options = ['FOR', 'AGAINST']
mode = sys.argv[1]
if mode == 'gen':
    playersfn, num, univfn = sys.argv[2:]
    base = getbase(num)
    mkdir(base)
    players = readplayers(playersfn)
    univ = set(w.upper() for w in stuff.readlines(univfn))
    nvalues = len(players) * len(options)
    assert nvalues * 2 < len(univ)
    values = random.sample(univ, nvalues)
    codebooks = []
    hashes = ''
    for name, _ in players:
        codes = {option: values.pop(0) for option in options}
        codebook = ['%s: %s' % (option, codes[option]) for option in options]
        codebook += ['Random characters to prevent hash cracking: %s' % ''.join(random.sample(string.letters, 20))]
        codebook = '\n'.join(codebook)
        open(base + '/%s.codebook' % name, 'w').write(codebook)
        codebooks.append('%s:\n%s' % (name, codebook))
        hashes += '%s: %s\n' % (name, hashlib.sha1(codebook).hexdigest())
    open(base + '/codebooks', 'w').write('\n--\n'.join(codebooks))
    open(base + '/hashes', 'w').write(hashes)
elif mode == 'email':
    n = False
    if sys.argv[2] == '-n':
        n = True
        sys.argv.pop(2)
    if len(sys.argv) == 5:
        just = sys.argv.pop(4)
    else:
        just = None
    playersfn, nums = sys.argv[2:]
    players = readplayers(playersfn)
    nums = stuff.unrangeify(nums)
    for name, email in players:
        if just is not None and name != just: continue
        message = getmailboiler(name, email, nums)
        message = stuff.twrap(message)
        for num in nums:
            message += '\nFor Proposal %s:\n' % num
            message += '{\n'
            message += open('../starchamber/%s/%s.codebook' % (num, name)).read()
            message += '\n}\n'

        if n:
            print '<%s>' % name
            print message
        else:
            print '/usr/sbin/qmail-sendmail -t << END11'
            print message[:-1]
            print 'END11'
        if just is not None:
            break
    else:
        if just is not None:
            print >> sys.stderr, 'not found'

else:
    print '???'
