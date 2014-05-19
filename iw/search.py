import re, sre_parse, sre_compile, sre_constants, collections, time, operator, itertools
from collections import namedtuple
from pystuff import config, mkdir_if_absent
import pystuff, stuff
import StringIO
inf, neginf = float('inf'), float('-inf')

def intersect_iterables(iterables, is_asc):
    subits = map(iter, iterables)
    minval = neginf if is_asc else inf
    less = -1 if is_asc else 1
    ids = [(minval, None)] * (len(subits) - 1)
    while True:
        first_id, ctxs = next(subits[0])
        for i, (id, ictxs) in enumerate(ids):
            while cmp(id, first_id) == less:
                try:
                    id, ictxs = next(subits[i+1])
                except StopIteration:
                    return # there is nothing more
            ids[i] = (id, ictxs)
            c = cmp(id, first_id)
            if c == -less:
                break # not matching
            elif c == 0:
                ctxs += ictxs
        else: # all through
            yield (first_id, ctxs)

def union_iterables(iterables, is_asc):
    subits = map(iter, iterables)
    subit_count = len(subits)
    if is_asc:
        minval = neginf
        maxval = inf
        _min = min
    else:
        minval = inf
        maxval = neginf
        _min = max
    ids = [(minval, None)] * subit_count
    while subit_count > 0:
        min_id, ctxs = _min(ids)
        if min_id != minval:
            yield (min_id, ctxs)
        for i, (id, ctxs) in enumerate(ids):
            if id == min_id:
                try:
                    ids[i] = next(subits[i])
                except StopIteration:
                    ids[i] = (maxval, None)
                    subit_count -= 1

def subtract_iterables(minuend, subtrahend, is_asc):
    minval = neginf if is_asc else inf
    maxval = inf if is_asc else neginf
    less = -1 if is_asc else 1

    bad = minval
    for id, ctxs in minuend:
        while cmp(bad, id) == less:
            try:
                bad, _ = next(subtrahend)
            except StopIteration:
                bad = maxval
        if bad != id:
            yield id, ctxs

def lex_query(text):
    # -bar, but foo-bar is one term
    ms = re.finditer(r'''
        (?P<or> OR (?= ["/\s()] ) \s* | \| \s* )?
        (?P<plusminus> [+-] )?
        (
            " (?P<quoted> [^"]* ) "
          | / (?P<regex> (?: [^\\] | \\. )* ) / (?P<regopts> [a-zA-Z]* )
          | (?P<operator> [a-zA-Z-]+ ) : (?P<operand> [^"/\s\(\)]* )
          | (?P<parens> [()] )
          | (?P<simple> [^"/\s()]+ )
        )
    ''', text, re.X)
    return [{k: v for (k, v) in m.groupdict().iteritems() if v is not None} for m in ms]

def parse_query(tokens, operators):
    errors = []
    stack = []
    def err_if_absent(error):
        if error not in errors:
            errors.append(error)
    existing, was_and = None, False
    order = None
    for token in tokens:
        inverted = token.get('plusminus') == '-'
        is_or = bool(token.get('or'))
        if 'parens' in token:
            if token['parens'] == '(':
                stack.append((existing, inverted, is_or, was_and))
                existing, was_and = None, False
                continue
            else: # )
                if not stack:
                    err_if_absent('Mismatched )')
                    continue
                else:
                    tree = existing
                    existing, inverted, is_or, was_and = stack.pop()
                    if tree is None: continue
        elif 'quoted' in token:
            tree = ('lit', token['quoted'])
        elif 'simple' in token:
            if token['simple'] == 'OR':
                err_if_absent('Bad OR')
                continue
            tree = ('lit', token['simple'])
        elif 'operator' in token:
            operator, operand = token['operator'], token['operand']
            if operator == 'order':
                operand = operand.lower()
                if operand not in ('asc', 'desc'):
                    errors.append('Bad order (must be asc or desc)')
                else:
                    order = operand
                continue
            if operator not in operators or operator in ('regex', 'lit'):
                errors.append('No such operator %s' % operator)
                continue
            tree = (operator, operand)
        elif 'regex' in token:
            regex, regopts = token['regex'], token['regopts']
            flags = 0
            for opt in regopts.upper():
                if opt in 'IMSX':
                    flags |= getattr(re, opt)
                else:
                    err_if_absent('Unknown regex flags')
            try:
                p = sre_parse.parse(regex, flags)
            except re.error as e:
                errors.append('Regex error: %s' % e.message)
                continue
            db = operators[None]
            if hasattr(db, 'idx'):
                trigrams = p_trigrams(p)
                #if trigrams is None:
                #    errors.append('Regex un-indexable')
                #    continue
                trigrams = simplify_trigrams(trigrams)
            else:
                trigrams = None
            p_fix_spaces(p)
            r = sre_compile.compile(p, flags)
            tree = ('regex', r, trigrams)
        if inverted: tree = ('not', tree)
        if is_or:
            if existing is None:
                err_if_absent('Bad OR')
                continue
            if was_and:
                existing = ('and', existing[1], ('or', existing[2], tree))
            else:
                existing = ('or', existing, tree)
                was_and = False
        else:
            if existing is not None:
                existing = ('and', existing, tree)
                was_and = True
            else:
                existing = tree
                was_and = False

    if stack:
        errors.append('Mismatched (')
    if errors:
        return ('errors', errors, None)
    elif not existing:
        return ('empty', None, None)
    else:
        return ('ok', existing, order)

def pprint(tree, indent=''):
    if isinstance(tree, tuple):
        print indent + str(tree[0])
        for sub in tree[1:]:
            pprint(sub, indent + '  ')
    else:
        print indent + str(tree)

def optimize_query(tree):
    if tree[0] in ('and', 'or'):
        kind = tree[0]
        args = []
        lits = []

        def add_arg(r):
            if r[0] == 'lit':
                lits.append(r[1])
            else:
                args.append(r)

        for subtree in [tree[1], tree[2]]:
            r = optimize_query(subtree)
            if r[0] == tree[0]:
                map(add_arg, r[1:])
            else:
                add_arg(r)
        if lits:
            if len(lits) == 1:
                args.append(('lit', lits[0]))
            else:
                args.append(('lit', (kind,) + tuple(lits)))
        if len(args) == 1:
            return args[0]
        else:
            return (kind,) + tuple(args)
    elif tree[0] == 'not':
        sub = tree[1]
        negative = True
        while sub[0] == 'not':
            negative = not negative
            sub = sub[1]
        sub = optimize_query(sub)
        if not negative: return sub
        if sub[0] == 'lit' and ' ' not in sub[1]:
            # can't do -"foo"
            return ('lit', ('not', sub[1]))
        else:
            return tree
    else:
        return tree

class QueryTimeoutException(Exception): pass

def run_query(tree, operators, deadline, limit=None, asc=False):
    if time.time() > deadline:
        raise QueryTimeoutException
    if tree[0] == 'or':
        return union_iterables(
            [run_query(subtree, operators, deadline, limit)
             for subtree in tree[1:]],
            asc)
    elif tree[0] == 'and':
        positive = [run_query(subtree, operators, deadline, None)
                    for subtree in tree[1:]
                    if subtree[0] != 'not']
        negative = [run_query(subtree[1], operators, deadline, None)
                    for subtree in tree[1:]
                    if subtree[0] == 'not']
        itr = intersect_iterables(positive, asc)
        if negative:
            return subtract_iterables(itr, union_iterables(negative, asc), asc)
        else:
            return itr
    elif tree[0] == 'lit':
        db = operators[None]
        return db.idx.word.search(tree[1], limit=limit, asc=asc)
    elif tree[0] == 'regex':
        db = operators[None]
        r, trigrams = tree[1], tree[2]
        if trigrams is None or pystuff.force_unindexed: # no index
            trigram_hits = db.keys()
            if not asc: trigram_hits = trigram_hits[::-1]
        else:
            trigram_hits = (result for result, _ in db.idx.trigram.search(trigrams, asc=asc))
        #list(trigram_hits); import sys; sys.exit(0)
        #db.cache_keys(trigram_hits)
        #db.cache_keys_done()
        results = set()

        def func():
            for result in trigram_hits:
                if pystuff.print_trigram_hits: print '?', result
                if time.time() > deadline:
                    raise QueryTimeoutException
                text = db.get_by_id(result)
                assert text is not None
                if isinstance(text, dict): text = text['text']
                it = r.finditer(text)
                #it = re.finditer('^', text)
                try:
                    m = next(it)
                except StopIteration:
                    pass
                else:
                    yield (result, [FoundRegex(itertools.chain([m], it))])
        return func()
    else:
        raise Exception('bad tree')

def do_query(expr, operators, start=0, limit=10, timeout=2.5, asc=False):
    l = lex_query(expr)
    ok, p, order = parse_query(l, operators)
    if ok != 'ok':
        return (ok, p)
    if order is not None:
        asc = order == 'asc'
    o = optimize_query(p)
    if timeout is None:
        deadline = float('inf')
    else:
        deadline = time.time() + 2.5
    it = iter(run_query(o, operators, deadline, None if limit is None else start + limit, asc))
    try:
        for i in xrange(start):
            try:
                next(it)
            except StopIteration:
                break
        if limit is None:
            results = list(it)
        else:
            results = []
            for i in xrange(limit):
                try:
                    result = next(it)
                    results.append(result)
                except StopIteration:
                    break
        return ('ok', results)
    except QueryTimeoutException:
        return ('timeout', None)

def m_to_range(m):
    return (m.start(), m.end())

class FoundLit:
    def __init__(self, query):
        self.query = query
    def ranges(self, text):
        bits = [re.escape(q) for q in self.query[1:] if not isinstance(q, tuple)]
        if not bits:
            return []
        r = r'\b(%s)\b' % '|'.join(bits)
        return (m_to_range(m) for m in re.finditer(r, text, re.I))

class FoundRegex:
    def __init__(self, it):
        self.it = it
    def ranges(self, text):
        for m in self.it:
            yield m_to_range(m)

class HighlightedString:
    def __init__(self, text, ranges):
        self.text = text
        self.ranges = ranges
    def plain(self):
        return self.text
    def ansi(self):
        return self.output('\x1b[7m', '\x1b[27m', lambda text: text)
    def html(self):
        import web
        return self.output('<b>', '</b>', lambda text: web.websafe(text))
    def output(self, enter, exit, transform):
        text = self.text
        last_e = 0
        result = StringIO.StringIO()
        for s, e in self.ranges:
            result.write(transform(text[last_e:s]))
            result.write(enter)
            result.write(transform(text[s:e]))
            result.write(exit)
            last_e = e
        result.write(transform(text[last_e:]))
        return result.getvalue()

def fix_ranges(ranges):
    ranges.sort()
    result = []
    last_s, last_e = -1, -1
    for s, e in ranges:
        if s < last_e:
            result[-1] = (last_s, e)
            last_e = e
        else:
            result.append((s, e))
            last_s, last_e = s, e
    return result

def get_ranges(text, ctxs):
    ranges = []
    for ctx in ctxs:
        ranges += list(ctx.ranges(text))
    return fix_ranges(ranges)

def highlight_all(text, ctxs):
    ranges = get_ranges(text, ctxs)
    return HighlightedString(text, ranges)

def highlight_snippets(text, ctxs):
    ranges = get_ranges(text, ctxs)
    line_ranges = []
    bad_line_ranges = []
    for s, e in ranges:
        prev_nl, next_nl = text.rfind('\n', 0, s), text.find('\n', e)
        lr = (prev_nl + 1, len(text) if next_nl == -1 else next_nl)
        (line_ranges if e - s < 100 else bad_line_ranges).append(lr)
    if not line_ranges:
        line_ranges = bad_line_ranges
    line_ranges = fix_ranges(line_ranges)
    htext = ''
    hranges = []
    for ls, le in line_ranges[:3]:
        if htext != '':
            htext += '\n'
        adj = + len(htext) - ls
        htext += text[ls:le]
        hranges += [(s + adj, e + adj) for (s, e) in ranges if s >= ls and e <= le]
    return HighlightedString(htext, hranges)


# http://swtch.com/~rsc/regexp/regexp4.html but simplified
# is the simplification appropriate?...

def p_is_dot_star((kind, arg)):
    # can't use == becaue of hidden SubPattern class
    if kind is not sre_constants.MAX_REPEAT: return False
    min, max, sub = arg
    if min != 0 or max < 4294967295 or len(sub) != 1: return False
    return sub[0] == (sre_constants.ANY, None)

litmap = []
for arg in xrange(128):
    litmap.append(chr(arg).lower().replace('\n', ' ').encode('hex'))

def _p_trigrams(p, litstr=''):
    sp_stack = []
    trigrams = []
    trigrams_set = set()
    alternates = []
    it = iter(p)

    # any character
    any_kinds = (sre_constants.ANY,
                 sre_constants.NOT_LITERAL,
                 sre_constants.RANGE,
                 sre_constants.CATEGORY,
                 sre_constants.IN)
    # empty string
    empty_kinds = (sre_constants.ASSERT,
                   sre_constants.ASSERT_NOT,
                   sre_constants.AT)
    branch_kinds = (sre_constants.BRANCH,
                    sre_constants.GROUPREF_EXISTS)
    while True:
        try:
            kind, arg = next(it)
        except StopIteration:
            if sp_stack:
                it = sp_stack.pop()
                continue
            else:
                break

        if kind in any_kinds:
            litstr = ''
        elif kind in empty_kinds:
            pass
        elif kind in branch_kinds:
            if kind is sre_constants.GROUPREF_EXISTS:
                group, yes, no = arg
                arg = [yes, no]
            else:
                something, arg = arg
            for sp in arg:
                alt = _p_trigrams(sp, litstr)
                if alt is not None and alternates is not None:
                    alternates.append(alt)
                else:
                    alternates = None # could be anything
            litstr = ''
        elif kind is sre_constants.MAX_REPEAT:
            min, max, sub = arg
            if min >= 1:
                # same trigrams as the string itself
                sp_stack.append(it)
                it = iter(sub)
            else:
                litstr = ''
        elif kind is sre_constants.SUBPATTERN:
            sp_stack.append(it)
            group, sub = arg
            it = iter(sub)
        elif kind is sre_constants.LITERAL:
            c = litmap[arg] if arg < 128 else '3f' # '?'
            litstr = litstr[-4:] + c
            if len(litstr) == 6 and litstr not in trigrams_set:
                trigrams_set.add(litstr)
                trigrams.append(litstr)
        else:
            raise Exception('unknown kind %s' % kind)

    if len(trigrams) > 10:
        trigrams = trigrams[:5] + trigrams[-5:]

    texpr = ('and',) + tuple(trigrams)
    aexpr = None if alternates is None else ('or',) + tuple(alternates)
    if trigrams and alternates:
        return ('and', texpr, aexpr)
    elif trigrams:
        return texpr
    elif alternates:
        return aexpr
    else:
        return None

def p_trigrams(p):
    while p and p_is_dot_star(p[0]):
        p.pop(0)
    while p and p_is_dot_star(p[-1]):
        p.pop()
    return _p_trigrams(p)

def p_fix_spaces(p):
    for i, (kind, arg) in enumerate(p):
        if kind is sre_constants.LITERAL and arg == 32: # ' '
            p[i] = (sre_constants.IN, [(sre_constants.LITERAL, 32), (sre_constants.LITERAL, 10)]) # add '\n'
        elif kind is sre_constants.IN and (sre_constants.LITERAL, 32) in arg and (sre_constants.LITERAL, 10) not in arg:
            arg.append((sre_constants.LITERAL, 10))
        elif kind is sre_constants.MAX_REPEAT:
            p_fix_spaces(arg[2])
        elif kind is sre_constants.SUBPATTERN:
            p_fix_spaces(arg[1])
        elif kind is sre_constants.BRANCH:
            for sub in arg[1]:
                p_fix_spaces(sub)

# xxx
def simplify_trigrams(trigrams):
    return trigrams

class Index:
    def __init__(self, name, db):
        self.name = name
        self.db = db
        if db.new:
            db.cursor.execute('CREATE VIRTUAL TABLE %s USING fts4(%s, order=desc, content='', text text);' % (name, self.fts_opts))
        self.insert_stmt = 'INSERT INTO %s(docid, text) VALUES(?, ?)' % name
        self.search_stmt = 'SELECT docid FROM %s WHERE text MATCH ? ORDER BY docid %%s LIMIT ?' % name

    def begin(self):
        pass

    def commit(self):
        pass

    def _insert(self, docid, text):
        self.db.cursor.execute(self.insert_stmt, (docid, text))

    # No SQLITE_ENABLE_FTS3_PARENTHESIS means trouble
    @staticmethod
    def to_sql(bit):
        if not isinstance(bit, tuple): return bit
        return {'and': ' ', 'or': ' OR '}[bit[0]].join(
            ('-%s' % s[1]) if isinstance(s, tuple) # ('not', x)
            else ('"%s"' % s)
            for s in bit[1:])

    def search(self, query, limit=None, asc=False):
        if not (isinstance(query, tuple) and query[0] != 'not'): query = ('and', query)

        # deoptimize
        tuples = []
        nontuples = []
        kind = query[0]
        for bit in query[1:]:
            (tuples if isinstance(bit, tuple) and bit[0] != 'not' else nontuples).append(bit)
        if tuples:
            if nontuples: tuples.append((kind,) + tuple(nontuples))
            subresults = [self.search(subquery, limit if kind == 'and' else None, asc) for subquery in tuples]
            return (intersect_iterables if kind == 'and' else union_iterables)(subresults, asc)

        sql = Index.to_sql(query)
        cursor = pystuff.CursorWrapper(self.db.conn.cursor())
        result = cursor.execute(self.search_stmt % ('ASC' if asc else 'DESC'), (sql, 10000000 if limit is None else limit))
        return ((docid, [FoundLit(query)]) for docid, in result)

class WordIndex(Index):
    fts_opts = 'tokenize=porter'
    insert = Index._insert

def trigram_hexlify(text):
    if not isinstance(text, unicode):
        text = stuff.faildecode(str(text))
    return text.encode('ascii', 'replace').lower().replace('\n', ' ').encode('hex')

class TrigramIndex(Index):
    fts_opts = 'tokenize=simple'

    def insert(self, docid, text):
        text = trigram_hexlify(text)
        self._insert(docid, ' '.join(set(text[i:i+6] for i in xrange(0, len(text) - 6, 2))))

class CombinedIndex:
    def __init__(self, name, db):
        self.word = WordIndex(name + '_word', db)
        self.trigram = TrigramIndex(name + '_trigram', db)

    def begin(self):
        self.word.begin()
        self.trigram.begin()

    def commit(self):
        self.word.commit()
        self.trigram.commit()

    def insert(self, docid, text):
        self.word.insert(docid, text)
        self.trigram.insert(docid, text)

if __name__ == '__main__':
    import sys
    operators = {'foo': None}
    if len(sys.argv) > 1:
        examples = sys.argv[1:]
    else:
        examples = [
            'a OR f d OR (g h)',
            '+test bar -("hi"/test/+x-f) -f',
            '',
            '(OR)',
            '(-)',
            '/foo+/',
        ]
    for example in examples:
        print repr(example)
        l = lex_query(example)
        print ' lex:', l
        ok, p, order = parse_query(l, operators)
        if ok == 'ok':
            o = optimize_query(p)
            print ' par:', ok, order
            pprint(o, indent='   ')
        else:
            print ' par:'
            pprint((ok, p), indent='   ')
