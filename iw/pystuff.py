from types import FunctionType
import sys, os, argparse, time, mmap, dbhash, bsddb, shelve, UserDict

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

# this is pointless
def make_callback_vt(conn, mod_name, callback, cols, all_ids):
    import apsw
    class MyModule:
        def Create(self, connection, modulename, databasename, tablename, *args):
            assert len(args) == len(cols) + 1
            return ('CREATE TABLE foo(%s)' % ', '.join(args), MyTable())
        Connect = Create
    class MyCursor:
        def Close(self):
            pass
        def Column(self, num):
            if num == 0:
                return self.id
            else:
                return self.row[cols[num - 1]]
        def Eof(self):
            return self.row is None
        def Filter(self, indexnum, indexname, constraintargs):
            if indexnum == 1:
                ids = [constraintargs[0]]
            else:
                ids = all_ids
            self.rows = iter(ids)
            self.Next()
        def Next(self):
            try:
                self.id = next(self.rows)
            except StopIteration:
                self.row = None
            else:
                self.row = callback(self.id)
        def Rowid(self):
            return self.id
    class MyTable:
        def BestIndex(self, constraints, orderbys):
            cused = tuple([0 if col == 0 and op == apsw.SQLITE_INDEX_CONSTRAINT_EQ
                           else None
                           for (col, op) in constraints])
            if not remove_none(cused): return None
            return (cused, 1, 'rowid_idx', False, 0)
        def Destroy(self):
            pass
        Disconnect = Destroy
        def Open(self):
            return MyCursor()
        def Rename(self, newname):
            pass
        def UpdateChangeRow(self, *args):
            raise Exception("can't modify this table")
        UpdateDeleteRow = UpdateChangeRow
        UpdateInsertRow = UpdateChangeRow
    conn.createmodule(mod_name, MyModule())

if __name__ == '__main__':
    if sys.argv[1] == 'test-vt':
        import apsw
        conn = apsw.Connection(':memory:')
        def callback(id):
            return {'val': id + 5}
        ids = range(100, 1000)
        make_callback_vt(conn, 'foo', callback, ['val'], ids)
        cursor = conn.cursor()
        cursor.execute('CREATE VIRTUAL TABLE foo USING foo(id integer, val integer)')
        print list(cursor.execute('SELECT * FROM foo'))
        print list(cursor.execute('SELECT * FROM foo WHERE id = 400'))

# subclassing doesn't work
def fnmmap(path):
    fp = open(path, 'rb')
    mm = mmap.mmap(fp.fileno(), 0, access=mmap.ACCESS_READ)
    fp.close()
    return mm

# we need concurrency support
dbm = dbhash

def shelf(fn, mode, *args, **kwargs):
    return shelve.BsdDbShelf(bsddb.hashopen(fn, mode), *args, **kwargs)

import config_default
try:
    import config
except ImportError:
    config = config_default
else:
    for key in dir(config_default):
        if not key.startswith('_') and not hasattr(config, key):
            setattr(config, key, getattr(config_default, key))
