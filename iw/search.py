import re

def lex_query(text):
    # -bar, but foo-bar is one term
    ms = re.finditer(r'''
        (?P<or> OR (?= ["/\s()] ) \s* )?
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
        is_or = token.get('or')
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
            tree = ('regex', r)
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

def fix_trigrams(text):
    # encoding is a waste of space, custom tokenizer is REALLY ugly, custom index is annoying, so do this
    return re.sub('[^a-zA-Z0-9_]', 'z', text)

def get_trigrams(text):
    #text = fix_trigrams(text)
    #return ' '.join(set(text[i:i+3] for i in xrange(len(text) - 3)))
    text = text.encode('utf-8')
    return set(text[i:i+3] for i in xrange(len(text) - 3))

import anydbm, struct
class Index:
    def __init__(self, path, create=False):
        self.db = anydbm.open(path, 'c' if create else 'w')
        #self.fp = open(path + '.docs', 'a' if create else 'r')

    def begin(self):
        self.additions = {}

    def cache(self, docid, words):
        for word in set(words):
            self.additions.setdefault(word, []).append(docid)

    def commit(self):
        for word, docids in self.additions.iteritems():
            docids = struct.pack('>' + 'I' * len(docids), *docids)
            self.db[word] = self.db.get(word, '') + docids


    def search(self, word):
        words = self.db.get(word, '')
        return struct.unpack('>' + 'I' * len(words), words)

if __name__ == '__main__':
    operators = {'foo': None}
    for example in [
        'a OR f d OR (g h)',
        '+test bar -("hi"/test/+x-f) -f',
        '',
        '(OR)',
        '(-)',
    ]:
        print repr(example)
        l = lex_query(example)
        print ' -->', l
        p = parse_query(l, operators)
        print ' -->'
        pprint(p)
        s = split_query(p, operators)
        print ' -->', s
