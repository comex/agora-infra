import re
from pystuff import config, mkdir_if_absent
import whoosh.index, whoosh.fields, whoosh.query, whoosh.qparser, whoosh.qparser.syntax, whoosh.qparser.plugins, whoosh.qparser.dateparse, whoosh.matching

class field:
    string = whoosh.fields.ID
    name = string
    date = whoosh.fields.DATETIME
    text = whoosh.fields.TEXT
    ngram = whoosh.fields.NGRAM(minsize=3, maxsize=3)
    comma_sep = whoosh.fields.KEYWORD(commas=True)

class RegexMatcher(whoosh.matching.WrappingMatcher):
    def __init__(self, re, searcher, child, boost=1.0):
        super(RegexMatcher, self).__init__(child, boost)
        self.re = re
        self.searcher = searcher
    def reset(self):
        self.child.reset()
        self._find_next()
    def next(self):
        self.child.next()
        self._find_next()
    def skip_to(self, id):
        self.child.skip_to(id)
        self._find_next()
    def _find_next(self):
        re = self.re
        r = False
        while self.child.is_active() and not self._matches():
            r = self.child.next() or r
        return r
    def _matches(self):
        fields = self.searcher.stored_fields(self.child.id())
        print '>>> matches', fields


class RegexQuery(whoosh.query.Query):
    def __init__(self, fieldname, regex):
        self.fieldname = fieldname
        self.regex = regex
        self.term = Term(fieldname + '!trigram', regex) # XXX
    def estimate_size(self, ixreader):
        return ixreader.doc_count()
    def existing_terms(self, ixreader, termset=None, reverse=False, phrases=True, expand=False):
        return [] # xxx
    def matcher(self, searcher, context=None):
        return RegexMatcher(self.re, searcher, self.term.matcher(searcher, context))

class RegexNode(whoosh.qparser.syntax.TextNode):
    qclass = RegexQuery

    def r(self):
        print self.__dict__
        return "Regex %r" % self.regex


class RegexPlugin(whoosh.qparser.plugins.TaggingPlugin):
    expr = r'/(?P<regex>(?:[^\\]|\\.)*)/(?P<regopts>[a-zA-Z]*)'
    nodetype = RegexNode

class Index:
    def __init__(self, schema, path, create=False):
        mkdir_if_absent(path)
        self.ngrams = []
        for col, ty in schema.items():
            if ty is field.text:
                schema[col + '!trigram'] = field.ngram
                self.ngrams.append(col)
        schema = whoosh.fields.Schema(**schema)
        if not whoosh.index.exists_in(path):
            if not create:
                raise Exception('no existing index')
            self.idx = whoosh.index.create_in(path, schema)
        else:
            self.idx = whoosh.index.open_dir(path)
        qp = whoosh.qparser.QueryParser('text', schema)
        qp.add_plugin(whoosh.qparser.dateparse.DateParserPlugin())
        qp.add_plugin(RegexPlugin)
        self.qp = qp

    def begin(self):
        self.writer = self.idx.writer()

    def insert(self, data):
        for ng in self.ngrams:
            data[ng + '!trigram'] = data[ng]
        self.writer.add_document(**data)

    def commit(self):
        self.writer.commit()

if __name__ == '__main__':
    import glob, os, stuff
    try:
        shutil.rmtree('/tmp/foo.index')
    except: pass
    idx = Index({
        'num': field.name,
        'text': field.text,
    }, '/tmp/foo.index', True)
    idx.begin()
    for path in glob.glob(os.path.expanduser('~/cfj/cfj/*.txt'))[:100]:
        print path
        idx.insert({'num': unicode(path[:-4]), 'text': stuff.faildecode(open(path).read())})
    idx.commit()
