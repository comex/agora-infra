import re, itertools, datetime
class RCSFile:
    tok_re = re.compile('@.*?[^@]@(?!@)|[^@\s]+', re.S)
    def __init__(self, text):
        self.text = text

    @staticmethod
    def unat(text):
        assert text[0] == text[-1] == '@'
        return text[1:-1].replace('@@', '@')

    @staticmethod
    def at(text):
        return '@' + text.replace('@', '@@') + '@'

    @staticmethod
    def apply_diff(text, diff):
        # Note that this avoids iterating over each line in the original document.
        info = {}
        i, l = 0, len(diff)
        while i < l:
            cmd = diff[i]
            i += 1
            if cmd == '': continue
            kind, at, count = re.match('^([da])([0-9]+) ([0-9]+)', cmd).groups()
            count = int(count); at = int(at)
            if at < 0:
                print cmd
            if kind == 'd':
                for j in xrange(count):
                    info[at + j] = []
            else:
                if at not in info: info[at] = [text[at]]
                lines = diff[i:i + count]
                i += count
                info[at].extend(lines)
        text2 = []
        cur = 1
        for num, lines in sorted(info.items()):
            if num != 0:
                text2.extend(text[cur - 1:num - 1])
            text2.extend(lines)
            cur = num + 1
        text2.extend(text[cur - 1:])
        return text2

    @staticmethod
    def diff(old, new):
        diff = []
        old = old.split('\n')
        new = new.split('\n')
        old_i, old_l = 0, len(old)
        new_i, new_l = 0, len(new)
        def add_diff(old_x, old_i, new_x, new_i):
            if old_x > old_i:
                diff.append('d%d %d' % (old_i + 1, old_x - old_i))
            if new_x > new_i:
                diff.append('a%d %d' % (old_x, new_x - new_i))
                diff.extend(new[new_i:new_x])
        while old_i < old_l and new_i < new_l:
            old_line = old[old_i]
            new_line = new[new_i]
            if old_line != new_line:
                # find the next occurrence of three identical lines
                old_j, new_j = old_i + 1, new_i + 1
                old_seen = {}
                new_seen = {}
                while old_j < old_l or new_j < new_l:
                    if old_j < old_l:
                        seq = tuple(old[old_j:old_j + 3])
                        if seq in new_seen:
                            old_x = old_j
                            new_x = new_seen[seq]
                            break
                        old_seen.setdefault(seq, old_j)
                    if new_j < new_l:
                        seq = tuple(new[new_j:new_j + 3])
                        if seq in old_seen:
                            old_x = old_seen[seq]
                            new_x = new_j
                            break
                        new_seen[seq] = new_j
                    old_j += 1
                    new_j += 1
                else:
                    # they're completely different
                    old_x = old_l
                    new_x = new_l
                add_diff(old_x, old_i, new_x, new_i)
                old_i, new_i = old_x, new_x
            else:
                old_i += 1
                new_i += 1
        add_diff(old_l, old_i, new_l, new_i)
        return diff

    def parse(self, mode):
        tokens = re.finditer(self.tok_re, self.text)
        it = iter(tokens)
        text = None
        was_head = False
        revs = []
        m = next(it)
        assert m.group(0) == 'head'
        head_m = next(it)
        meta_m = None
        rev_m = None
        while True:
            try:
                m = next(it)
            except StopIteration: break
            tok = m.group(0)
            if not re.match('1\.[0-9]+$', tok): continue
            rev = {}
            rev['num'] = tok
            if next(it).group(0) != 'log':
                if meta_m is None: meta_m = m
                continue
            rev['log'] = self.unat(next(it).group(0))
            while next(it).group(0) != 'text': pass
            text_m = next(it)
            diff = self.unat(text_m.group(0))
            if mode == 1:
                return diff
            elif mode == 2:
                return head_m, meta_m, m, text_m, diff
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

    def commit(self, new_text, log, author):
        head_m, meta_m, rev_m, text_m, text = self.parse(2)
        old_rev = rev_m.group(0)
        one, num = old_rev.split('.')
        assert one == '1'
        new_rev = '1.%d' % (int(num) + 1)
        diff = self.diff(new_text, text)
        date = datetime.datetime.utcnow().strftime('%Y.%m.%d.%H.%M.%S')
        new = ''.join([
            self.text[:head_m.start()],
            new_rev, ';',
            self.text[head_m.end():meta_m.start()],

            new_rev, '\n',
            'date\t', date, ';\tauthor ', author, ';\tstate Exp;\n',
            'branches;\n',
            'next\t', old_rev, ';\n\n',

            self.text[meta_m.start():rev_m.start()],

            new_rev, '\n',
            'log\n',
            self.at(log + '\n'), '\n',
            'text\n',
            self.at(new_text), '\n\n\n',

            self.text[rev_m.start():text_m.start()],
            self.at('\n'.join(diff) + '\n'),
            self.text[text_m.end():],
        ])
        self.text = new


if __name__ == '__main__':
    import sys
    if len(sys.argv) <= 1:
        print 'Usage: rcs.py (--diff fileA fileB | --commit rcsfile newFile log author [newRcsfile] | rcsfile [revs...])'
        sys.exit(0)
    if sys.argv[1] == '--diff':
        old = open(sys.argv[2]).read()
        new = open(sys.argv[3]).read()
        diff = RCSFile.diff(old, new)
        sys.stdout.write('\n'.join(diff))
        new = new.split('\n')
        realnew = RCSFile.apply_diff(old.split('\n'), diff)
        if realnew != new:
            print '*** Actual new document was:'
            print realnew
            print '*** Expected:'
            print new
            sys.exit(1)
    elif sys.argv[1] == '--commit':
        rf = RCSFile(open(sys.argv[2]).read())
        text = open(sys.argv[3]).read()
        log = sys.argv[4]
        author = sys.argv[5]
        outfp = open(sys.argv[6], 'w') if len(sys.argv) > 6 else sys.stdout
        rf.commit(text, log, author)
        outfp.write(rf.text)

    else:
        rf = RCSFile(open(sys.argv[1]).read())
        wanted = sys.argv[2:]
        if wanted:
            revs = rf.get_revisions()
            for rev in revs:
                if rev['num'] in wanted:
                    sys.stdout.write('\n'.join(rev['text']))
        else:
            sys.stdout.write(rf.get_last_revision())
