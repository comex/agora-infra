import re, datetime, tempfile, subprocess

class RCSFile:
    tok_re = re.compile('@.*?[^@]@(?!@)|[^@\s]+', re.S)
    def __init__(self, text):
        self.text = text

    @staticmethod
    def unat(text):
        assert text[0] == text[-1] == '@'
        return text[1:-1].replace('@@', '@')

    @staticmethod
    def apply_diff(text, diff):
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
                text[at+1:at+1] = lines
                line_offset -= count
        return text

    def parse(self, mode):
        tokens = re.finditer(self.tok_re, self.text)
        it = iter(tokens)
        text = None
        revs = []
        m = next(it)
        assert m.group(0) == 'head'
        while True:
            try:
                m = next(it)
            except StopIteration: break
            tok = m.group(0)
            if not re.match('1\.[0-9]+$', tok): continue
            rev = {}
            rev['num'] = tok
            if next(it).group(0) != 'log': continue
            rev['log'] = self.unat(next(it).group(0))
            while next(it).group(0) != 'text': pass
            diff = self.unat(next(it).group(0))
            if mode == 1:
                return diff
            diff = diff.split('\n')

            if text is None:
                text = diff
            else:
                text = self.apply_diff(text, diff)
            rev['text'] = text
            revs.append(rev)
        return revs

    def get_revisions(self):
        return self.parse(0)

    def get_last_revision(self):
        return self.parse(1)

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
