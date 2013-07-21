import argparse, subprocess, traceback, os, urllib, sys, hashlib, re, shutil, apsw
from pystuff import mydir, remove_none, chdir, mkdir_if_absent, remove_if_present, config
import pystuff

class Datasource():
    depends = []

    def __init__(self):
        self.did_download = set()
        if hasattr(self, 'urls'):
            self.urls = [(url, os.path.join(mydir, 'downloads', filename)) for (url, filename) in self.urls]
        self.operators = {None: self}

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

    def reindex(self):
        for DB in self.dbs:
            DB(create=True).reindex()

    def search(self, expr, start=):
        l = search.lex_query(expr)
        ok, p = search.parse_query(l, self.operators)
        if ok != 'ok':
            return (ok, p)
        o = search.optimize_query(p)
        it = iter(search.run_query(o, self.operators))
        results = []

    def cli_download(self, args):
        self.download(not args.quiet, args.url_filter)
    def cli_cache(self, args):
        self.cache(not args.quiet)
    def cli_update(self, args):
        self.cli_download(args)
        self.cli_cache(args)
    def cli_search(self, args, expr):
        print self.search(expr)

    def add_cli_options(self, parser, argsf):
        if hasattr(self, 'download'):
            parser.add_argument('--download-' + self.name, action=pystuff.action(lambda: self.cli_download(argsf())))
        parser.add_argument('--cache-' + self.name, action=pystuff.action(lambda: self.cli_cache(argsf())))
        # download and cache
        if hasattr(self, 'download'):
            parser.add_argument('--update-' + self.name, action=pystuff.action(lambda: self.cli_update(argsf())))

        parser.add_Argument('--search-' + self.name, action=pystuff.action(lambda expr: self.cli_search(argsf(), expr), nargs=1))

    def cli_print_document(self, num, DB):
        document = DB.instance().get(num)
        if document is None:
            print >> sys.stderr, 'No such document:', num
            return
        print document

    def cli_add_print_document(self, parser, name, DB):
        parser.add_argument('--%s' % name, action=pystuff.action(lambda num: self.cli_print_document(num, DB), nargs=1))


class DB(object):
    def full_path(self):
        mkdir_if_absent(os.path.join(mydir, 'cache'))
        return os.path.join(mydir, 'cache', self.path)
    def __init__(self, create=False, **kwargs):
        self.conn = apsw.Connection(self.full_path())
        self.cursor = self.conn.cursor()
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
        if 0: # log queries
            self.cursor = CursorWrapper(self.cursor)

    def begin(self):
        self.cursor.execute('BEGIN')

    def commit(self):
        self.cursor.execute('COMMIT')

    def meta(self, name):
        return next(self.cursor.execute('SELECT %s FROM meta' % name))[0]

    def set_meta(self, name, value):
        self.cursor.execute('UPDATE meta SET %s = ?' % name, (value,))

    _instance = None
    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

def all_sources():
    from cfjs import CFJDatasource
    from flr import FLRDatasource, RulesDatasource
    from messages import MessagesDatasource
    return [CFJDatasource(), FLRDatasource(), RulesDatasource(), MessagesDatasource()]
