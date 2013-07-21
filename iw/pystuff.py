from types import FunctionType
import sys, os, argparse, time, mmap, UserDict, json

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
        a = time.time()
        ret = self.cursor.execute(*args)
        b = time.time()
        print >> sys.stderr, 'executing', args, 'took', (b - a)
        return ret

def dict_execute(cursor, *args, **kwargs):
    result = cursor.execute(*args, **kwargs)
    desc = cursor.getdescription()
    for row in result:
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

class LazySearch(object):
    def __getattribute__(self, at):
        import search
        return getattr(search, at)
search = LazySearch()
