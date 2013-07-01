import re, textwrap

def andify(strs):
    strs = tuple(strs)
    if len(strs) == 1:
        return strs[0]
    elif len(strs) == 2:
        return '%s and %s' % strs
    else:
        return ', '.join(strs[:-1]) + ', and ' + strs[-1]

def rangeify(nums):
    ranges = []
    start = None
    expected = None
    def end_range():
        s, e = str(start), str(expected - 1)
        if s[:2] == e[:2]: e = e[2:]
        ranges.append('%s-%s' % (s, e))
    for num in nums:
        if num != expected:
            if expected is not None: end_range()
            start = expected = num
        expected += 1
    end_range()
    return andify(ranges)

def unrangeify(text):
    nums = []
    for nrange in text.split(','):
        nrange = nrange.replace('and', '').strip()
        if '-' in nrange:
            lo, hi = nrange.split('-')
            hi = lo[:max(len(lo) - len(hi), 0)] + hi
            nums += range(int(lo), int(hi) + 1)
        else:
            nums.append(int(nrange))
    return nums

def readlines(fn):
    return open(fn).read().strip().split('\n')

def getcolstarts(line):
    return [m.start() for m in re.finditer('[^ ]+', line)]

def colify(line, colstarts):
    line += '\0'
    return [line[s:e].strip() for s, e in zip(colstarts, colstarts[1:] + [-1])]

def twrap(message):
    return '\n'.join(textwrap.fill(line) for line in message.split('\n'))