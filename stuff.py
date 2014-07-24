import re, textwrap, chardet

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
        ae = e[2:] if s[:2] == e[:2] else e
        ranges.append(s if s == e else '%s-%s' % (s, ae))
    for num in nums:
        if num != expected:
            if expected is not None: end_range()
            start = expected = num
        expected += 1
    end_range()
    return andify(ranges)

def lblrangeify(nums, label):
    return '%s%s %s' % (label, 's' if len(nums) > 1 else '', rangeify(nums))

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

def twrap(message, width=72, indent=0, subsequent_indent=None):
    indent = ' ' * indent
    subsequent_indent = indent if subsequent_indent is None else ' ' * subsequent_indent
    return '\n'.join(textwrap.fill(line, width=width, initial_indent=indent, subsequent_indent=subsequent_indent, break_on_hyphens=False) for line in message.split('\n'))

def faildecode(text):
    if isinstance(text, unicode):
        return text
    try:
        return text.decode('utf-8')
    except:
        return text.decode('ISO-8859-2')

class RowTable:
    def __init__(self):
        self.lines = []
        self.col_info = {}

    def row(self, line=[]):
        if not isinstance(line, list):
            line = [line]
        self.lines.append(line)
        return line

    def print_block(self, out):
        for o in out:
            print o.rstrip()
        out[:] = [''] * len(self.lines)

    def print_col(self, col, llen, out, spacing_after, rjust):
        cells = [line[col] if col < len(line) else '' for line in self.lines]
        clen = max(map(len, cells))
        if llen + clen > 80:
            self.print_block(out)
            print
            llen = self.print_col(0, 0, out)
        for j, val in enumerate(cells):
            out[j] += (val.rjust if rjust else val.ljust)(clen) + ' ' * spacing_after
        llen += clen + spacing_after
        return llen

    def print_all(self):
        out = [''] * len(self.lines)
        line0 = self.lines[0]
        llen = 0
        for col in xrange(max(map(len, self.lines))):
            spacing_after = 3 if col == 0 else 2
            rjust = False
            if col < len(line0):
                control = line0[col]
                if control.startswith('>'):
                    rjust = True
                    control = control[1:]
                line0[col] = control
            llen = self.print_col(col, llen, out, spacing_after, rjust)
        self.print_block(out)

def maildecode(em):
    pl = em.get_payload(decode=True)
    assert not isinstance(pl, unicode)
    if em.get_content_charset() is None:
        charset = chardet.detect(pl)['encoding']
    else:
        charset = em.get_content_charset()
    try:
        return unicode(pl, charset, 'replace')
    except LookupError:
        return unicode(pl, 'iso-8859-2')
