import re, datetime

class RCSFile:
    tok_re = re.compile('@.*?[^@]@(?!@)|[^@\s]+', re.S)
    def __init__(self, text):
        self.text = text

    @staticmethod
    def unat(text):
        assert text[0] == text[-1] == '@'
        return text[1:-1].replace('@@', '@')

    @staticmethod
    def make_indirect(lines, indirect):
        if indirect is not None:
            offsets = []
            for line in lines:
                offsets.append(indirect.tell())
                indirect.write(line)
                indirect.write('\n')
            return offsets
        else:
            return lines

    @classmethod
    def apply_diff(cls, text, diff, indirect):
        # Note that this avoids iterating over each line in the original document.
        text = text[:]
        line_offset = 0
        i, l = 0, len(diff)
        while i < l:
            cmd = diff[i]
            i += 1
            if cmd == '': continue
            kind, at, count = re.match('^([da])([0-9]+) ([0-9]+)', cmd).groups()
            count = int(count); at = int(at)
            at = at - 1 - line_offset
            if kind == 'd':
                del text[at:at + count]
                line_offset += count
            else:
                lines = diff[i:i + count]
                i += count
                lines = cls.make_indirect(lines, indirect)
                text[at+1:at+1] = lines
                line_offset -= count
        return text

    def parse(self, mode, indirect):
        tokens = re.finditer(self.tok_re, self.text)
        it = iter(tokens)
        text = None
        revs = []
        dates = {}
        m = next(it)
        assert m.group(0) == 'head'
        while True:
            try:
                m = next(it)
            except StopIteration: break
            num = m.group(0)
            if not re.match('1\.[0-9]+$', num): continue
            tok = next(it).group(0)
            if tok == 'date':
                date = next(it).group(0)
                dt = datetime.datetime.strptime(date, '%Y.%m.%d.%H.%M.%S;')
                dates[num] = dt
                continue
            else:
                assert tok == 'log'
            rev = {}
            rev['num'] = num
            rev['date'] = dates[num]
            rev['log'] = self.unat(next(it).group(0))
            while next(it).group(0) != 'text': pass
            diff = self.unat(next(it).group(0))
            if mode == 1:
                return diff
            diff = diff.split('\n')

            if text is None:
                text = self.make_indirect(diff, indirect)
            else:
                text = self.apply_diff(text, diff, indirect)
            rev['text'] = text
            revs.append(rev)
        return revs

    def get_revisions(self, indirect=None):
        return self.parse(0, indirect)

    def get_last_revision(self):
        return self.parse(1, None)

if __name__ == '__main__':
    import sys
    if len(sys.argv) <= 1:
        print 'Usage: rcs.py rcsFile [revs...]'
        sys.exit(0)
    rf = RCSFile(open(sys.argv[1]).read())
    wanted = sys.argv[2:]
    if wanted:
        revs = rf.get_revisions()
        for rev in revs:
            if rev['num'] in wanted:
                sys.stdout.write('\n'.join(rev['text']))
    else:
        sys.stdout.write(rf.get_last_revision())
