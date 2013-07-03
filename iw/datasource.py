from pystuff import singleton, mydir, remove_none
import argparse, subprocess, traceback, os, urllib, sys

class Datasource(singleton):
    def __init__(cls):
        if hasattr(cls, 'filename'):
            cls.filename = os.path.join(mydir, 'downloads', cls.filename)

    def download(cls, verbose=False):
        if verbose:
            print >> sys.stderr, 'Downloading %s...' % cls.url
        text = subprocess.check_output(remove_none(['curl', '-s' if not verbose else None, cls.url]))
        text = cls.preprocess(text)
        rcs = cls.filename + ',v'
        if os.path.exists(rcs):
            subprocess.check_call(['co', '-q', '-l', rcs])
        open(cls.filename, 'wb').write(text)
        with pystuff.chdir(os.path.dirname(rcs)):
            subprocess.check_call(remove_none(['ci', '-q' if not verbose else None, '-u', '-mupdate', '-t-iw download', rcs]))
        return True

    def preprocess(cls, text): return text

def all_sources():
    from cotc import CotCDatasource
    from flr import FLRDatasource
    return [CotCDatasource, FLRDatasource]
