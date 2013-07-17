from pystuff import mydir, remove_none, chdir, mkdir_if_absent, remove_if_present, dict_execute
import argparse, subprocess, traceback, os, urllib, sys, hashlib, re, shelf

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

    def add_cli_options(self, parser): pass

class DB(object):
    version = 0
    def get_path(self, ext):
        mkdir_if_absent(os.path.join(mydir, 'cache'))
        return os.path.join(mydir, 'cache', self.path) + '.' + ext
    def __init__(self, create=False, **kwargs):
        self.new = True
        meta_path = self.get_path('meta')
        exists = os.path.exists(meta_path)
        self.meta = shelve.open(meta_path, 'c' if create else 'r', -1)
        if exists:
            version = self.meta.get('version', 0)
            if version == self.version:
                self.new = False
                return
            if not create:
                raise Exception('old version: %s' % meta_path)
        else:
            if not create:
                raise Exception('no such file: %s' % meta_path)
        # delete any other files
        cdir = os.path.join(mydir, 'cache')
        for fn in os.path.listdir(cdir):
            if fn.startswith(self.path + '.') and fn != self.path + '.meta':
                os.path.remove(os.path.join(cdir, fn))

def all_sources():
    from cotc import CotCDatasource
    from flr import FLRDatasource, RulesDatasource
    from messages import MessagesDatasource
    return [CotCDatasource(), FLRDatasource(), RulesDatasource(), MessagesDatasource()]
