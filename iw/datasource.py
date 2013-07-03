from pystuff import singleton, mydir, remove_none, chdir, mkdir_if_absent
import argparse, subprocess, traceback, os, urllib, sys, hashlib

class Datasource(singleton):
    depends = []
    download_result = None

    def __init__(cls):
        if hasattr(cls, 'filename'):
            cls.filename = os.path.join(mydir, 'downloads', cls.filename)
        if hasattr(cls, 'cachefiles'):
            cls.cachefiles = [os.path.join(mydir, 'cache', cf) for cf in cls.cachefiles]

    def download(cls, verbose=False):
        if cls.download_result is not None: return cls.download_result
        mkdir_if_absent(os.path.join(mydir, 'downloads'))
        if verbose:
            print >> sys.stderr, 'Downloading %s...' % cls.url
        try:
            text = subprocess.check_output(remove_none(['curl', '-k', '-s' if not verbose else None, cls.url]))
        except subprocess.CalledProcessError:
            cls.download_result = False
            return False
        text = cls.preprocess(text)
        rcs = cls.filename + ',v'
        if os.path.exists(rcs):
            subprocess.check_call(['rcs', '-q', '-l', rcs])
            os.remove(cls.filename)
        open(cls.filename, 'wb').write(text)
        with chdir(os.path.dirname(rcs)):
            subprocess.check_call(remove_none(['ci', '-q' if not verbose else None, '-u', '-mupdate', '-t-iw download', rcs]))
        cls.download_result = True
        return True

    def cache(cls, verbose=False):
        mkdir_if_absent(os.path.join(mydir, 'cache'))
        # maybe prevent duplicate caching
        cls._cache(verbose)

    def preprocess(cls, text): return text

def all_sources():
    from cotc import CotCDatasource
    from flr import FLRDatasource
    from rules import RulesDatasource
    return [CotCDatasource, FLRDatasource, RulesDatasource]
