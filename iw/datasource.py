import argparse, subprocess, traceback, os, urllib, sys, hashlib, re, shutil, apsw
from pystuff import mydir, remove_none, chdir, mkdir_if_absent, remove_if_present, config, Singleton, dict_execute, last
import pystuff, stuff, search

class DSLookupError(Exception): pass

class Datasource(Singleton):
    depends = []

    def __init__(self):
        self.did_download = set()
        if hasattr(self, 'urls'):
            self.urls = [(url, os.path.join(mydir, 'downloads', filename)) for (url, filename) in self.urls]

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

    def cli_download(self, args):
        self.download(not args.quiet, args.url_filter)
    def cli_cache(self, args):
        self.cache(not args.quiet)
    def add_cli_options(self, parser, argsf):
        if hasattr(self, 'urls'):
            parser.add_argument('--download-' + self.name, action=pystuff.action(lambda: self.cli_download(argsf())), help='download %s' % self.name)
        parser.add_argument('--cache-' + self.name, action=pystuff.action(lambda: self.cli_cache(argsf())), help='cache %s' % self.name)

class GitDatasource(Datasource):
    def download(self, verbose=False, url_filter=None, use_cont=False):
        # This will fail if the remote rebases.  Don't rebase.
        for url, filename in self.urls:
            if url_filter is not None and not re.search(url_filter, url): continue
            if os.path.exists(filename):
                subprocess.check_output(['git', 'pull'], cwd=filename)
            else:
                subprocess.check_output(['git', 'clone', url, filename])

class BaseDB(Singleton):
    def __init__(self):
        self.search_operators = {None: self}
        self.dirty = False

    def finalize(self, verbose=False):
        pass

    @classmethod
    def full_path(cls):
        mkdir_if_absent(os.path.join(mydir, 'cache'))
        return os.path.join(mydir, 'cache', cls.path)

    def add_cli_options(self, parser, argsf):
        if config.use_search and hasattr(self, 'search'):
            parser.add_argument('--search-' + self.name, action=pystuff.action(lambda expr: self.cli_search(argsf(), expr), nargs=1), help='search %s' % self.name)

        singular = self.name.rstrip('s')
        parser.add_argument('--' + singular, action=pystuff.action(lambda expr: self.cli_show(argsf(), expr), nargs=1), help='show %s by primary key' % singular)

        for source in self.datasources():
            source.add_cli_options(parser, argsf)

        # download and cache all datasources
        parser.add_argument('--update-' + self.name, action=pystuff.action(lambda: self.cli_update(argsf())), help='download and cache %s' % self.name)

    def cli_show(self, args, key):
        result = self.get(key)
        if result is None:
            print '(not found)'
        else:
            print result['text'] if isinstance(result, dict) else result

    def cli_update(self, args):
        for ds in self.datasources():
            if hasattr(ds, 'urls'):
                ds.cli_download(args)
            ds.cli_cache(args)

    def search(self, expr, *args, **kwargs):
        return search.do_query(expr, self.search_operators, *args, **kwargs)

    def cli_search(self, args, expr):
        ok, r = self.search(expr, limit=args.limit or None)
        if ok == 'empty':
            print '(empty query)'
        elif ok == 'errors':
            print 'Errors in search query:'
            for err in r:
                print ' ', err
        elif ok == 'timeout':
            print 'Timeout'
        elif ok == 'ok':
            first = True
            for id, ctxs in r:
                if first:
                    first = False
                else:
                    print '--'
                row = self.get_by_id(id)
                text = row['text']
                if args.full:
                    if args.color:
                        print search.highlight_all(text, ctxs).ansi()
                    else:
                        print text
                else:
                    print 'id:', row[self.doc_keycol]
                    hl = search.highlight_snippets(text, ctxs)
                    if args.color:
                        print hl.ansi()
                    else:
                        print hl.plain()
            if first and not args.quiet:
                print '(no results)'

class DB(BaseDB):
    def __init__(self, **kwargs):
        BaseDB.__init__(self)
        self.conn = apsw.Connection(self.full_path())
        self.conn.setbusytimeout(1000)
        self.cursor = pystuff.CursorWrapper(self.conn.cursor())
        self.new = False
        create = True # xxx
        try:
            version, = last(self.cursor.execute('SELECT version FROM version'))
        except apsw.SQLError:
            if not create:
                raise
            self.cursor.execute('''
                CREATE TABLE version(version int);
                INSERT INTO version VALUES(?);
                CREATE TABLE meta(key blob primary key, value blob);
            ''', (self.version,))
            self.new = True
            version = self.version
        if version != self.version:
            if not create:
                raise Exception('bad version')
            else:
                os.remove(self.full_path())
                return self.__init__(**kwargs)

    def begin(self):
        self.cursor.execute('BEGIN')
        if hasattr(self, 'idx'): self.idx.begin()

    def commit(self):
        if hasattr(self, 'idx'): self.idx.commit()
        self.cursor.execute('COMMIT')

    def search_word(self, *args, **kwargs):
        return self.idx.word.search(*args, **kwargs)

    def search_trigram(self, *args, **kwargs):
        return self.idx.trigram.search(*args, **kwargs)

    def search_get(self, id):
        return last(self.cursor.execute('SELECT %s FROM %s WHERE id = ?' % (self.doc_textcol, self.doc_table), (id,)))[0]

    ThrowException = object()

    def meta(self, name, default=ThrowException):
        try:
            return last(self.cursor.execute('SELECT value FROM meta WHERE key = ?', (name,)))[0]
        except StopIteration:
            if default is DB.ThrowException:
                raise KeyError(name)
            return default

    def set_meta(self, name, value):
        self.cursor.execute('REPLACE INTO meta VALUES(?, ?)', (name, value))

class DocDB(DB):
    def keys(self):
        return [id for id, in self.cursor.execute('SELECT %s FROM %s ORDER BY %s' % (self.doc_keycol, self.doc_table, self.doc_keycol))]

    def id_keys(self):
        return [id for id, in self.cursor.execute('SELECT id FROM %s ORDER BY %s' % (self.doc_table, self.doc_ordercol))]

    def items(self):
        return list(self.cursor.execute('SELECT %s, %s FROM %s' % (self.doc_keycol, self.doc_textcol, self.doc_table)))

    def get(self, key):
        try:
            row = last(dict_execute(self.cursor, 'SELECT * FROM %s WHERE %s = ?' % (self.doc_table, self.doc_keycol), (key,)))
        except StopIteration:
            return None
        return self.fix_row(row)

    def get_by_id(self, id):
        if hasattr(self, 'kcache'):
            return self.kcache[id]
        return self.fix_row(last(dict_execute(self.cursor, 'SELECT * FROM %s WHERE id = ?' % (self.doc_table), (id,))))

    def cache_keys(self, keys):
        self.kcache = {}
        for row in dict_execute(self.cursor, 'SELECT id, %s from %s WHERE id in (%s)' % (self.table, ','.join(map(str, keys)))):
            self.kcache[row['id']] = row

    def cache_keys_done(self):
        del self.kcache

    def fix_row(self, row):
        return row

    def reindex_if_necessary(self, verbose=False):
        # Can't delete from contentless FTS tables.
        if config.use_search and self.conn.totalchanges() > 0:
            if verbose:
                print >> sys.stderr, 'reindexing...'
            self.idx.clear()

            self.begin()
            self.idx.begin()

            for id, text in self.cursor.execute('SELECT id, %s FROM %s' % (self.doc_textcol, self.doc_table)):
                self.idx.insert(id, text)

            self.idx.end()
            self.end()

def all_dbs():
    from cfjs import CFJDB
    from messages import MessagesDB
    return [CFJDB.instance(), MessagesDB.instance()]

