import argparse, subprocess, traceback, os, urllib, sys, hashlib, re, shutil, apsw
from pystuff import mydir, remove_none, chdir, mkdir_if_absent, remove_if_present, config, Singleton, dict_execute
import pystuff, stuff, search

class DSLookupError(Exception): pass

class Datasource(Singleton):
    depends = []

    def __init__(self):
        self.did_download = set()
        if hasattr(self, 'urls'):
            self.urls = [(url, os.path.join(mydir, 'downloads', filename)) for (url, filename) in self.urls]
        self.operators = {}

    def download(self, verbose=False, url_filter=None, use_cont=False):
        for url, filename in self.urls:
            cont = None
            if use_cont:
                try:
                    cont = os.path.getsize(filename)
                except OSError: pass
            if url is None: continue
            if url_filter is not None and not re.search(url_filter, url): continue
            if url in self.did_download: continue
            mkdir_if_absent(os.path.join(mydir, 'downloads'))
            if verbose:
                print >> sys.stderr, 'Downloading %s...' % url
            try:
                text = subprocess.check_output(
                    ['curl', '--compressed', '-L', '-k', url] +
                    (['-s'] if not verbose else []) +
                    (['-C', str(cont)] if cont is not None else []))
            except subprocess.CalledProcessError as e:
                if e.returncode == 33:
                    # curl thinks byte ranges aren't supported; actually there is nothing new
                    continue
            text = self.preprocess_download(text)
            if not use_cont:
                rcs = filename + ',v'
                if os.path.exists(rcs):
                    subprocess.check_call(['rcs', '-q', '-l', rcs])
                    remove_if_present(filename)
            open(filename, 'ab' if cont is not None else 'wb').write(text)
            if not use_cont:
                with chdir(os.path.dirname(rcs)):
                    subprocess.check_call(remove_none(['ci', '-q' if not verbose else None, '-u', '-mupdate', '-t-iw download', rcs]))
            self.did_download.add(url)

    def preprocess_download(self, text): return text

    def search(self, expr, *args, **kwargs):
        self.operators[None] = self.DB.instance()
        return search.do_query(expr, self.operators, *args, **kwargs)

    def cli_download(self, args):
        self.download(not args.quiet, args.url_filter)
    def cli_cache(self, args):
        self.cache(not args.quiet)
    def cli_update(self, args):
        self.cli_download(args)
        self.cli_cache(args)
    def cli_search(self, args, expr):
        db = self.DB.instance()
        ok, r = self.search(expr, limit=args.limit or None)
        if ok == 'empty':
            print '(empty query)'
        elif ok == 'errors':
            print 'Errors in search query:'
            for err in r:
                print ' ', err
        elif ok == 'ok':
            first = True
            for id, ctxs in r:
                if first:
                    first = False
                else:
                    print '--'
                row = db.get_by_id(id)
                text = row['text']
                if args.full:
                    if args.color:
                        print search.highlight_all(text, ctxs).ansi()
                    else:
                        print text
                else:
                    print 'id:', row[db.doc_keycol]
                    hl = search.highlight_snippets(text, ctxs)
                    if args.color:
                        print hl.ansi()
                    else:
                        print hl.plain()
            if first and not args.quiet:
                print '(no results)'

    def cli_show(self, args, key):
        result = self.DB.instance().get(key)
        if result is None:
            print '(not found)'
        else:
            print result['text'] if isinstance(result, dict) else result

    def add_cli_options(self, parser, argsf):
        if hasattr(self, 'download'):
            parser.add_argument('--download-' + self.name, action=pystuff.action(lambda: self.cli_download(argsf())), help='download %s' % self.name)
        parser.add_argument('--cache-' + self.name, action=pystuff.action(lambda: self.cli_cache(argsf())), help='cache %s' % self.name)
        # download and cache
        if hasattr(self, 'download'):
            parser.add_argument('--update-' + self.name, action=pystuff.action(lambda: self.cli_update(argsf())), help='download and cache %s' % self.name)

        if config.use_search and hasattr(self, 'DB') and hasattr(self.DB, 'search'):
            parser.add_argument('--search-' + self.name, action=pystuff.action(lambda expr: self.cli_search(argsf(), expr), nargs=1), help='search %s' % self.name)

        if hasattr(self, 'DB'):
            singular = self.name.rstrip('s')
            parser.add_argument('--' + singular, action=pystuff.action(lambda expr: self.cli_show(argsf(), expr), nargs=1), help='show %s by primary key' % singular)

    def cli_print_document(self, num, DB):
        document = DB.instance().get(num)
        if document is None:
            print >> sys.stderr, 'No such document:', num
            return
        print document

    def cli_add_print_document(self, parser, name, DB):
        parser.add_argument('--%s' % name, action=pystuff.action(lambda num: self.cli_print_document(num, DB), nargs=1))

class BaseDB(Singleton):
    @classmethod
    def full_path(cls):
        mkdir_if_absent(os.path.join(mydir, 'cache'))
        return os.path.join(mydir, 'cache', cls.path)

class DB(BaseDB):
    def __init__(self, create=False, **kwargs):
        self.conn = apsw.Connection(self.full_path())
        self.cursor = pystuff.CursorWrapper(self.conn.cursor())
        self.new = False
        try:
            version, = next(self.cursor.execute('SELECT version FROM version'))
        except apsw.SQLError:
            if not create:
                raise
            self.cursor.execute('CREATE TABLE version(version int); INSERT INTO version VALUES(?)', (self.version,))
            self.new = True
            version = self.version
        if version != self.version:
            if not create:
                raise Exception('bad version')
            else:
                os.remove(path)
                return self.__init__(path, create)

    def begin(self):
        self.cursor.execute('BEGIN')
        if hasattr(self, 'idx'): self.idx.begin()

    def commit(self):
        if hasattr(self, 'idx'): self.idx.commit()
        self.cursor.execute('COMMIT')

    def meta(self, name):
        return next(self.cursor.execute('SELECT %s FROM meta' % name))[0]

    def set_meta(self, name, value):
        self.cursor.execute('UPDATE meta SET %s = ?' % name, (value,))

class DocDB(DB):
    def keys(self):
        return [id for id, in self.cursor.execute('SELECT id FROM %s' % self.doc_table)]

    def items(self):
        return self.cursor.execute('SELECT %s, %s FROM %s' % (self.doc_keycol, self.doc_textcol, self.doc_table))


    def get(self, key):
        try:
            row = next(dict_execute(self.cursor, 'SELECT * FROM %s WHERE %s = ?' % (self.doc_table, self.doc_keycol), (key,)))
        except StopIteration:
            return None
        return row

    def get_by_id(self, id):
        if hasattr(self, 'kcache'):
            return self.kcache[id]
        return next(dict_execute(self.cursor, 'SELECT * FROM %s WHERE id = ?' % (self.doc_table), (id,)))

    def cache_keys(self, keys):
        self.kcache = {}
        for row in dict_execute(self.cursor, 'SELECT id, %s from %s WHERE id in (%s)' % (self.table, ','.join(map(str, keys)))):
            self.kcache[row['id']] = row

    def cache_keys_done(self):
        del self.kcache

def all_sources():
    from cfjs import CFJDatasource
    from flr import FLRDatasource, RulesDatasource
    from messages import MessagesDatasource
    return [CFJDatasource.instance(), FLRDatasource.instance(), RulesDatasource.instance(), MessagesDatasource.instance()]
