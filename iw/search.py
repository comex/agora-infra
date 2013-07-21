import re, sre_parse, sre_constants, collections
from pystuff import config, mkdir_if_absent

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
            trigrams = re_trigrams(regex, flags)
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
        return ('errors', errors)
    return ('ok', existing)

def pprint(tree, indent=''):
    if isinstance(tree, tuple):
        print indent + tree[0]
        for sub in tree[1:]:
            pprint(sub, indent + '  ')
    else:
        print indent + str(tree)

def split_query(tree, operators):
    pass
    #kind, *args = tree
    #if kind == 'and':

def get_trigrams(text):
    #text = fix_trigrams(text)
    #return ' '.join(set(text[i:i+3] for i in xrange(len(text) - 3)))
    text = text.encode('utf-8')
    return set(text[i:i+3] for i in xrange(len(text) - 3))

# http://swtch.com/~rsc/regexp/regexp4.html
PatternInfo = collections.namedtuple('PatternInfo', ['emptyable', 'exact', 'prefix', 'suffix', 'match'])

class MakePatternInfo:
    @staticmethod
    def str_union(a, b):
        i = 0
        for i in xrange(min(len(a), len(b))):
            if a[i] != b[i]:
                break
        return a[:i]

    # these are sets or None
    @staticmethod
    def match_and(a, b):
        if a is None: return b
        if b is None: return a
        return a & b

    @staticmethod
    def match_or(a, b):
        if a is None or b is None: return None
        return a | b

    def _any(self, none): # .
        return PatternInfo(False, None, '', '', None)
    # ANY_ALL unused
    def _assert(self, (dir, sp)):
        # like an empty string
        return None
    _assert_not = _assert
    def _at(self, where):
        return None
    def _category(self, cat):
        return self._any(None)
    def _groupref(self):
        # same as .*
        return PatternInfo(False, None, '', '', None)
    def _groupref_exists(self, (group, yes, no)):
        return self._in([yes, no])
    def _in(self, subs):
        pi = subs[0]
        for opi in subs[1:]:
            pi = PatternInfo(
                pi.emptyable or opi.emptayble,
                pi.exact or opi.exact,
                self.str_union(pi.prefix, opi.prefix),
                self.str_union(pi.suffix, opi.suffix),
                self.match_or(pi.match, opi.match)
            )
        return pi

    def _literal(self, val):
        val = chr(val).lower()
        return PatternInfo(False, val, val, val, None)
    def _not_literal(self, val):
        return self._any(None)
    def _max_repeat(self, (min, max, item)):
        if min >= 1:
            return self.go_sub(item)._replace(exact=None)
        else:
            return PatternInfo(True, None, '', '', None)
    def _min_repeat(self, tup):
        # e.g. x*?
        return self._max_repeat(tup)
    def _range(self, arg):
        return self._any(None)
    def _subpattern(self, (num, sp)):
        return self.go_sub(sp)

    def go_sub(self, p):
        pi = PatternInfo(True, '', '', '', None)
        for kind, arg in p:
            wpi = getattr(self, '_' + kind)(arg)
            if wpi is None:
                # this is effectively nothing
                continue
            if pi is None:
                pi = wpi
                continue
            # concatenation
            pi = PatternInfo(
                pi.emptyable and wpi.emptyable,
                (pi.exact + wpi.exact)
                    if pi.exact is not None and wpi.exact is not None
                    else None,
                (pi.exact + wpi.prefix) if pi.exact is not None
                    else self.str_union(pi.prefix, wpi.prefix) if pi.emptyable
                    else pi.prefix,
                (pi.suffix + wpi.exact) if wpi.exact is not None
                    else self.str_union(wpi.suffix, pi.suffix) if wpi.emptyable
                    else wpi.suffix,
                self.match_and(pi.match, wpi.match)
            )

        return pi

    @staticmethod
    def is_dot_star((kind, arg)):
        # can't use == becaue of hidden SubPattern class
        if kind is not sre_constants.MAX_REPEAT: return False
        min, max, sub = arg
        if min != 0 or max < 4294967295 or len(sub) != 1: return False
        return sub[0] == (sre_constants.ANY, None)

    def go(self, p):
        p = list(p)
        while p and self.is_dot_star(p[0]):
            p.pop(0)
        while p and self.is_dot_star(p[-1]):
            p.pop()
        return self.go_sub(p)


def re_trigrams(regex, flags):
    p = sre_parse.parse(regex, flags)
    info = MakePatternInfo().go(p)
    print '!', info

class Index:
    def __init__(self, name, db):
        self.name = name
        self.db = db
        if db.new:
            db.cursor.execute('CREATE VIRTUAL TABLE %s USING fts4(%s, content='', text text);' % (name, self.fts_opts))
        self.insert_stmt = 'INSERT INTO %s(docid, text) VALUES(?, ?)' % self.name

    def begin(self):
        pass

    def commit(self):
        pass

    def _insert(self, docid, text):
        self.db.cursor.execute(self.insert_stmt, (docid, text))

class WordIndex(Index):
    fts_opts = 'tokenize=porter'
    insert = Index._insert

class TrigramIndex(Index):
    fts_opts = 'tokenize=simple'

    def insert(self, docid, text):
        text = str(text).lower().encode('hex')
        self._insert(docid, ' '.join(set(text[i:i+6] for i in xrange(0, len(text) - 6, 2))))

class CombinedIndex(Index):
    def __init__(self, name, db):
        self.widx = WordIndex(name + '_word', db)
        self.tidx = TrigramIndex(name + '_trigram', db)

    def begin(self):
        self.widx.begin()
        self.tidx.begin()

    def commit(self):
        self.widx.commit()
        self.tidx.commit()

    def insert(self, docid, text):
        self.widx.insert(docid, text)
        self.tidx.insert(docid, text)

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
        print ' -->', l
        p = parse_query(l, operators)
        print ' -->'
        pprint(p)
        s = split_query(p, operators)
        print ' -->', s
