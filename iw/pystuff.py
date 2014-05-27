from types import FunctionType
import sys, os, argparse, time, mmap, UserDict, json, collections, codecs, signal
sys.stdout = codecs.getwriter('utf-8')(sys.stdout)

mydir = os.path.dirname(__file__)

def action(callback, nargs=0):
    class MyAction(argparse.Action):
        def __init__(self, **kwargs):
            kwargs['nargs'] = nargs
            argparse.Action.__init__(self, **kwargs)
        def __call__(self, parser, namespace, values, option_string=None):
            namespace.__dict__.setdefault('actions', []).append((callback, values))
    return MyAction

def run_actions(args):
    for action, args in args.__dict__.get('actions', []):
        action(*args)

def remove_none(lst):
    return filter(lambda x: x is not None, lst)

class chdir:
    def __init__(self, path):
        self.path = path
    def __enter__(self):
        self.old = os.getcwd()
        os.chdir(self.path)
    def __exit__(self, *args):
        os.chdir(self.old)

def mkdir_if_absent(path):
    if not os.path.exists(path):
        os.mkdir(path)

def remove_if_present(path):
    if os.path.exists(path):
        os.remove(path)

def grab_lines_until(it, end, include=False):
    lst = []
    while True:
        line = next(it)
        if line == end:
            if include: lst.append(line)
            return lst
        lst.append(line)

class CursorWrapper:
    def __init__(self, cursor):
        self.cursor = cursor
    def __getattr__(self, x):
        return getattr(self.cursor, x)
    def execute(self, *args):
        global log_quries
        if not log_queries:
            return self.cursor.execute(*args)
        a = time.time()
        ret = self.cursor.execute(*args)
        b = time.time()
        print >> sys.stderr, 'executing', args, 'took', (b - a)
        return ret

def dict_execute(cursor, *args, **kwargs):
    result = cursor.execute(*args, **kwargs)
    desc = None
    # apsw.ExecutionCompleteError
    for row in result:
        if desc is None: desc = [col for (col, ty) in cursor.getdescription()]
        yield dict(zip(desc, row))

# subclassing doesn't work
def fnmmap(path):
    fp = open(path, 'rb')
    mm = mmap.mmap(fp.fileno(), 0, access=mmap.ACCESS_READ)
    fp.close()
    return mm

import config_default
try:
    import config
except ImportError:
    config = config_default
else:
    for key in dir(config_default):
        if not key.startswith('_') and not hasattr(config, key):
            setattr(config, key, getattr(config_default, key))

class Singleton(object):
    _instance = None
    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

# modeled on Python 3's functools.lru_cache
class LRUItem: pass
class LRUCache:
    def __init__(self, size):
        self.map = collections.OrderedDict()
        self.size = size
    def __getitem__(self, key):
        val = self.map[key]
        self.map[key] = val
        return val
    def __setitem__(self, key, val):
        self.map[key] = val
        if len(self.map) > self.size:
            del self.map[next(iter(self.map.iterkeys()))]

def lru_cache(maxsize):
    cache = LRUCache(maxsize)
    def f(func):
        def replacement(*args, **kwargs):
            info = (args, tuple(kwargs.items()))
            try:
                return cache[info]
            except KeyError:
                result = func(*args, **kwargs)
                cache[info] = result
                return result
        return replacement
    return f

# This is not just for debugging.  apsw seems to not unlock cursors until you
# actually get the StopIteration, not after the last row.
def last(iterator):
    val = next(iterator)
    try:
        other = next(iterator)
    except StopIteration:
        return val
    else:
        raise ValueError('last() not last - got %s' % other)

def fix_web():
    # web.py includes a bad workaround for a non-bug in lighttpd.
    import web.application
    old_load = web.application.load
    def new_load(self, env):
        if 'SERVER_SOFTWARE' in env: del env['SERVER_SOFTWARE']
        return old_load(self, env)
    web.application.load = new_load

    # Keep-Alive messes up Ctrl-C
    import web.wsgiserver
    web.wsgiserver.HTTPRequest.close_connection = True

# debugging options
log_queries = False
force_unindexed = False
print_trigram_hits = False
