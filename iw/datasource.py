from pystuff import mydir, remove_none, chdir, mkdir_if_absent, remove_if_present, dict_execute
import argparse, subprocess, traceback, os, urllib, sys, hashlib, apsw, re

class Datasource():
    depends = []

    def __init__(self):
        self.did_download = set()
        if hasattr(self, 'urls'):
            self.urls = [(url, os.path.join(mydir, 'downloads', filename)) for (url, filename) in self.urls]
        if hasattr(self, 'cachefiles'):
            self.cachefiles = [os.path.join(mydir, 'cache', cf) for cf in self.cachefiles]

    def download(self, verbose=False, url_filter=None, use_cont=False):
        for url, filename in self.urls:
            if use_cont:
                try:
                    cont = os.path.getsize(filename)
                except OSError: cont = None
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
            text = self.preprocess(text)
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

    def cache(self, verbose=False):
        mkdir_if_absent(os.path.join(mydir, 'cache'))
        # maybe prevent duplicate caching
        self._cache(verbose)

    def preprocess(self, text): return text

class DB(object):
    version = 0
    def __init__(self, create=False, **kwargs):
        self.conn = apsw.Connection(self.path(**kwargs))
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
        if 0:
            self.cursor = CursorWrapper(self.cursor)

    def begin(self):
        self.cursor.execute('BEGIN')

    def commit(self):
        self.cursor.execute('COMMIT')

    def meta(self, name):
        return next(self.cursor.execute('SELECT %s FROM meta' % name))[0]

    def set_meta(self, name, value):
        self.cursor.execute('UPDATE meta SET %s = ?' % name, (value,))

    def document(self, **kwargs):
        assert len(kwargs) == 1
        k, v = kwargs.items()[0]
        return dict_execute(self.cursor, 'SELECT * FROM documents WHERE %s = ?' % k, (v,))

def all_sources():
    from cotc import CotCDatasource
    from flr import FLRDatasource, RulesDatasource
    from messages import MessagesDatasource
    return [CotCDatasource(), FLRDatasource(), RulesDatasource(), MessagesDatasource()]
