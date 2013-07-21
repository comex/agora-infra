import argparse, subprocess, traceback, os, urllib, sys, hashlib, re, shutil
from pystuff import mydir, remove_none, chdir, mkdir_if_absent, remove_if_present, config
import pystuff

class Datasource():
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

    def reindex(self):
        for DB in self.dbs:
            DB(create=True).reindex()

    def add_cli_options(self, parser, args):
        def download():
            self.download(not args.quiet, args.url_filter)
        def cache():
            self.cache(not args.quiet)))
        def update():
            download()
            cache()
        if hasattr(self, 'download'):
            parser.add_argument('--download-' + self.name, action=pystuff.action(download))
        parser.add_argument('--cache-' + self.name, action=pystuff.action(cache)
        # download and cache
        if hasattr(self, 'download'):
            parser.add_argument('--update-' + self.name, action=pystuff.action(update))
        if config.use_search and hasattr(self, 'dbs'):
            parser.add_argument('--reindex-' + self.name, action=pystuff.action(self.reindex)

    def cli_print_document(self, num, DB):
        document = DB.instance().get(num)
        if document is None:
            print >> sys.stderr, 'No such document:', num
            return
        print document

    def cli_add_print_document(self, parser, name, DB):
        parser.add_argument('--%s' % name, action=pystuff.action(lambda num: self.cli_print_document(num, DB), nargs=1))

class DB(object):
    def get_path(self, ext):
        mkdir_if_absent(os.path.join(mydir, 'cache'))
        return os.path.join(mydir, 'cache', self.base_path) + '.' + ext
    def __init__(self, create=False, **kwargs):
        self.new = True
        meta_path = self.get_path('meta')
        exists = os.path.exists(meta_path)
        self.meta = JSONStore(meta_path, create)
        if exists:
            version = self.meta.get('version', 0)
            if version == self.version:
                self.new = False
            elif not create:
                raise Exception('old version: %s' % meta_path)
        else:
            assert create
            self.meta['version'] = self.version
            self.meta.save()

        if self.new:
            # delete any other files
            cdir = os.path.join(mydir, 'cache')
            for fn in os.listdir(cdir):
                if fn.startswith(self.base_path + '.') and fn != self.base_path + '.meta':
                    path = os.path.join(cdir, fn)
                    if os.path.isdir(path):
                        assert path.endswith('.index') # better not delete anything important
                        shutil.rmtree(path)
                    else:
                        os.remove(path)

        if config.use_search:
            self.open_index(create)

    def open_index(self, create):
        pass

    def index(self, key, data, transaction=False):
        if transaction: self.idx.begin()
        self.idx.insert(self.index_info(key, data))
        if transaction: self.idx.commit()

    def reindex(self):
        if config.use_search:
            path = self.get_path('index')
            if os.path.exists(path):
                shutil.rmtree(path)
            self.open_index(True)
            self.idx.begin()
            for key in self.keys():
                self.index(w, key, self.get(key))
            self.idx.commit()

    _instance = None
    @classmethod
    ef instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

def all_sources():
    from cfjs import CFJDatasource
    from flr import FLRDatasource, RulesDatasource
    from messages import MessagesDatasource
    return [CFJDatasource(), FLRDatasource(), RulesDatasource(), MessagesDatasource()]
