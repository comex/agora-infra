import re, sre_parse, sre_constants, collections, time, operator
from collections import namedtuple
from pystuff import config, mkdir_if_absent
import pystuff
inf, neginf = float('inf'), float('-inf')

def intersect_iterables(iterables, is_asc):
    subits = map(iter, iterables)
    minval = neginf if is_asc else inf
    less = -1 if is_asc else 1
    ids = [minval] * (len(subits) - 1)
    while True:
        first_id = next(subits[0])
        for i, id in enumerate(ids):
            while cmp(id, first_id) == less:
                try:
                    id = next(subits[i+1])
                except StopIteration:
                    return # there is nothing more
            ids[i] = id
            if cmp(id, first_id) == -less:
                break # not matching
        else: # all through
            yield id

def union_iterables(iterables, is_asc):
    subits = map(iter, iterables)
    subit_count = len(subits)
    minval = neginf if is_asc else inf
    maxval = inf if is_asc else neginf
    ids = [minval] * subit_count
    while subit_count > 0:
        min_id = min(ids)
        if min_id != minval:
            yield min_id
        for i, id in enumerate(ids):
            if id == min_id: 
                try:
                    ids[i] = next(subits[i])
                except StopIteration:
                    ids[i] = maxval
                    subit_count -= 1

#            already = set()
#            for subtree in tree[1:]:
#                results = run_query(subtree, operators, deadline)
#                for result in results:
#                    if result in already: continue
#                    yield result
#                    already.add(result)

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
                r = re.compile(regex, flags)
            except re.error as e:
                errors.append('Regex error: %s' % e.message)
                continue
            db = operators[None]
            if hasattr(db, 'idx'):
                trigrams = re_trigrams(regex, flags)
                if trigrams is None:
                    errors.append('Regex un-indexable')
                    continue
            else:
                trigrams = None
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
        return intersect_iterables(
            [run_query(subtree, operators, deadline, limit)
             for subtree in tree[1:]],
            asc)
    elif tree[0] == 'lit':
        db = operators[None]
        return db.idx.word.search(tree[1], limit=limit, asc=asc)
    elif tree[0] == 'regex':
        db = operators[None]
        r, trigrams = tree[1], tree[2]
        if trigrams is None: # no index
            trigram_hits = db.keys()
        else:
            trigram_hits = db.idx.trigram.search(trigrams, limit=limit, asc=asc)
        results = set()

        def func():
            for result in trigram_hits:
                if time.time() > deadline:
                    raise QueryTimeoutException
                text = db.get_by_id(result)
                print (result, len(text))
                assert text is not None
                if isinstance(text, dict): text = text['text']
                m = r.search(text)
                if m:
                    yield result
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
                results.append(next(it))
            except StopIteration:
                break
    return ('ok', results)


# http://swtch.com/~rsc/regexp/regexp4.html but simplified
# is the simplification appropriate?...

def p_is_dot_star((kind, arg)):
    # can't use == becaue of hidden SubPattern class
    if kind is not sre_constants.MAX_REPEAT: return False
    min, max, sub = arg
    if min != 0 or max < 4294967295 or len(sub) != 1: return False
    return sub[0] == (sre_constants.ANY, None)

def p_trigrams(p, litstr=''):
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
    subpattern_kinds = (sre_constants.SUBPATTERN,
                        sre_constants.MAX_REPEAT)
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
                alt = p_trigrams(sp, litstr)
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
            litstr = litstr[-2:] + chr(arg).lower()
            if len(litstr) == 3 and litstr not in trigrams_set:
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
        return texpr
    else:
        return None

def re_trigrams(regex, flags):
    p = list(sre_parse.parse(regex, flags))
    while p and p_is_dot_star(p[0]):
        p.pop(0)
    while p and p_is_dot_star(p[-1]):
        p.pop()
    return p_trigrams(p)

class Index:
    def __init__(self, name, db):
        self.name = name
        self.db = db
        if db.new:
            db.cursor.execute('CREATE VIRTUAL TABLE %s USING fts4(%s, content='', text text);' % (name, self.fts_opts))
        self.insert_stmt = 'INSERT INTO %s(docid, text) VALUES(?, ?)' % name
        self.search_stmt = 'SELECT docid FROM %s WHERE text MATCH ? ORDER BY docid %%s LIMIT ?' % name
        self.cursor = pystuff.CursorWrapper(db.conn.cursor())

    def begin(self):
        pass

    def commit(self):
        pass

    def _insert(self, docid, text):
        self.cursor.execute(self.insert_stmt, (docid, text))

    # No SQLITE_ENABLE_FTS3_PARENTHESIS means trouble
    @staticmethod
    def to_sql(bit):
        if not isinstance(bit, tuple): return bit
        return {'and': ' ', 'or': ' OR '}[bit[0]].join('"%s"' % s for s in bit[1:])

    def search(self, query, limit=None, asc=False):
        if not isinstance(query, tuple): query = ('and', query)

        # deoptimize
        tuples = []
        nontuples = []
        kind = query[0]
        for bit in query[1:]:
            (tuples if isinstance(bit, tuple) else nontuples).append(bit)
        if tuples:
            tuples.append((kind,) + tuple(nontuples))
            subresults = [self.search(subquery, limit if kind == 'and' else None) for subquery in tuples]
            return (intersect_iterables if kind == 'and' else union_iterables)(subresults, asc)

        sql = Index.to_sql(query)
        result = self.db.cursor.execute(self.search_stmt % ('ASC' if asc else 'DESC'), (sql, 10000000 if limit is None else limit))
        return (docid for docid, in result)

class WordIndex(Index):
    fts_opts = 'tokenize=porter'
    insert = Index._insert

def trigram_hexlify(text):
    return text.encode('ascii', 'replace').lower().encode('hex')

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
