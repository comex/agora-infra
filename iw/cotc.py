import gzip, re, apsw, sys, datetime, time, multiprocessing, os, tarfile, traceback
import cStringIO, StringIO
from datasource import Datasource, DB
from pystuff import remove_if_present, mydir, grab_lines_until, CursorWrapper, dict_execute
import stuff

def try_execute(cursor, stmt):
    try:
        cursor.execute(stmt)
    except apsw.SQLError:
        print >> sys.stderr, stmt
        raise

class CotCDB(DB):
    # vaguely ported from Murphy's PHP code
    path = 'cotc.sqlite'
    def __init__(self, create=False):
        if create:
            remove_if_present(self.full_path())
        DB.__init__(self, create)
        if not create:
            self.decisions = dict(self.cursor.execute('SELECT * FROM decisions'))

    def all_nums(self):
        return [num for num, in self.cursor.execute('SELECT number FROM matters ORDER BY number')]

    def last_date(self):
        return next(self.cursor.execute('SELECT MAX(date) FROM events'))[0]

    def nums_since(self, date):
        return [num for num, in self.cursor.execute('SELECT m.number FROM events e INNER JOIN matters m ON (m.id = e.matter) WHERE e.date > ?', (date,))]

    def format(self, num):
        f = StringIO.StringIO()
        id, typecode, statement = next(self.cursor.execute('SELECT id, typecode, statement FROM matters WHERE number = ?', (num,)))
        if typecode in ['Criminal', 'Equity', 'Victory']: typecode += ' Case'
        hdr = '%s %s' % (typecode, num)
        heql = '=' * (34 - len(hdr) / 2)
        eql = '=' * 72
        print >> f, '%s  %s  %s' % (heql, hdr, heql)
        print >> f
        if statement:
            print >> f, stuff.twrap(statement, indent=4)
            print >> f
            print >> f, eql
            print >> f

        info = list(self.get_info(typecode, num, id))
        if not info: return None
        for bit in info:
            if bit is None:
                print >> f
            else:
                print >> f, ('%s:' % bit[0]).ljust(40) + stuff.twrap(bit[1] if bit[1] is not None else '', subsequent_indent=40)

        if info[-1] is not None: print >> f
        print >> f, eql
        print >> f, '\nHistory:\n'

        history = self.get_history(typecode, num, id)
        for left, right in history:
            left += ':'
            if len(left) > 38:
                print >> f, left + ':'
                print >> f, ' ' * 40 + right
            else:
                print >> f, left.ljust(40) + right

        print >> f
        print >> f, eql

        exhibits = self.get_exhibits(typecode, num, id)
        for date, label, text in exhibits:
            print >> f, '\n%s:\n' % label
            print >> f, stuff.twrap(text, width=78)
            print >> f
            print >> f, eql


        return f.getvalue()[:-1]

    def get_exhibits(self, case_typecode, num, id):
        if case_typecode == 'Appeal':
            l, = next(self.cursor.execute("SELECT e1.link FROM events AS e1, events AS e2 WHERE e1.id = e2.link AND e2.typecode = 'open' AND e2.matter = ?", (id,)))
        else:
            l = None
        for eid, player, link, typecode, xtypecode, xtext, date in self.cursor.execute("SELECT e.id, players.name, e.link, e.typecode, exhibits.typecode AS etype, exhibits.text, e.date FROM events e, exhibits, players LEFT JOIN events f ON (f.id = e.link) WHERE (e.matter = ? OR (e.typecode = 'cfa' AND e.link = ?)) AND exhibits.event = e.id AND ((e.typecode = 'decide' AND players.id = f.player) OR players.id = e.player) ORDER BY e.date, e.id, exhibits.typecode", (id, l)):
            j = 'Panelist' if case_typecode == 'Appeal' else 'Judge'
            x = 'Arguments' if xtypecode == 'arguments' else 'Evidence'
            if typecode == 'decide':
                label = "%s %s's %s" % (j, player, x)
            elif typecode == 'submit':
                label = "Caller's %s" % x
            elif typecode == 'order':
                label = '%s Order(s) by %s' % ('Appellate' if case_typecode == 'Appeal' else 'Judicial', player)
            elif typecode == 'cfa':
                label = "Appellant %s's %s" % (player, x)
            elif typecode == 'motion':
                label = "Motion %s.%s by %s" % (num, eid, player)
            elif typecode == 'reconsider':
                label = 'Request for reconsideration by %s' % player
            elif typecode == 'xdecide':
                label = "Non-%s %s's %s" % (j, player, x)
            elif typecode == 'xcomment':
                label = "Gratuitous %s by %s" % (x, player)
            else:
                raise Exception('unknown typecode %s' % typecode)
            yield (date, label, xtext)

    def get_history(self, case_typecode, num, id):
        remanded = False
        for eid, link, date, typecode, player, decision, decision2, player2, num2  in self.cursor.execute("SELECT e.id, e.link, e.date, e.typecode, p.name AS player, e.decision, f.decision, q.name, m.number FROM events e LEFT JOIN players p ON (e.player = p.id) LEFT JOIN events f ON (f.id = e.link) LEFT JOIN events g ON (g.link = e.id AND g.typecode = 'open') LEFT JOIN players q ON (q.id = f.player) LEFT JOIN matters m ON (m.id = g.matter) WHERE e.matter = ? ORDER BY e.date, e.id", (id,)):
            date = datetime.datetime.utcfromtimestamp(date)
            date = date.strftime('%d %b %Y %H:%M:%S GMT')
            if decision: decision = self.decisions[decision]
            if decision2: decision2 = self.decisions[decision2]
            fmt = None
            if typecode == 'submit':
                fmt = ('Called by %s' % player)
            elif typecode == 'assign':
                if remanded:
                    fmt = 'Remanded to %s' % player
                    remanded = False
                else:
                    fmt = 'Assigned to %s%s' % (player, ' (panelist)' if case_typecode == 'Appeal' else '')
            elif typecode == 'decide':
                if case_typecode == 'Appeal':
                    fmt = '%s moves to %s' % (player2, decision)
                elif player2:
                    if decision == 'DISMISS':
                        fmt = 'Dismissed by %s' % player2
                    elif decision == 'GRANT':
                        fmt = 'Motion %s.%s GRANTED by %s' % (num, link, player2)
                    elif decision == 'DENY':
                        fmt = 'Motion %s.%s DENIED by %s' % (num, link, player2)
                    else:
                        fmt = 'Judged %s by %s' % (decision, player2)
                else:
                    if decision.startswith('OVERRULE/'):
                        fmt = 'OVERRULED to %s on Appeal' % decision[9:]
                    elif decision.endswith('E'):
                        fmt = '%sD on Appeal' % decision
                    elif decision == 'REMIT':
                        fmt = 'REMITTED on Appeal'
                    else:
                        fmt = '%sED on Appeal' % decision
            elif typecode == 'reconsider':
                fmt = 'Reconsideration requested by %s' % player
            elif typecode == 'appeal':
                fmt = 'Appeal %s' % num2
            elif typecode == 'cfa':
                fmt = 'Appealed by %s' % player
            elif typecode == 'distribute':
                fmt = 'Judgement distributed'
            elif typecode == 'transfer':
                fmt = 'Transferred from %s to %s' % (player2, player)
            elif typecode == 'recuse':
                fmt = '%s recused%s' % (player2, ' (panelist)' if case_typecode == 'Appeal' else '')
            elif typecode == 'open':
                fmt = 'Appeal initiated'
            elif typecode == 'close':
                fmt = 'Final decision (%s)' % decision2
            elif typecode == 'order':
                fmt = 'Order(s) issued'
            elif typecode == 'stay':
                fmt = 'Order(s) stayed'
            elif typecode == 'vacate':
                fmt = 'Order(s) vacated'
            elif typecode == 'motion':
                fmt = 'Motion %s.%s by %s' % (num, eid, player)
            elif typecode == 'inform':
                if player:
                    fmt = 'Defendant %s informed' % player
                else:
                    fmt = 'Parties informed'
            elif typecode == 'ptend':
                fmt = 'Pre-trial phase ended'
            else:
                continue
            yield (fmt, date)

    def get_info(self, case_typecode, num, id):
        for eid, link, typecode, player, reassign, decision, matter, matter_num in self.cursor.execute("SELECT e.id, e.link, e.typecode, players.name AS player, f.typecode, g.decision, h.matter, matters.number FROM events e LEFT JOIN players ON (e.player = players.id) LEFT JOIN events f ON (f.link = e.id AND f.typecode in ('assign', 'transfer')) LEFT JOIN events g ON (g.link = e.id AND g.typecode = 'decide') LEFT JOIN events h ON (h.link = e.id AND h.typecode = 'open') LEFT JOIN matters ON (matters.id = h.matter) WHERE e.matter = ? AND e.typecode IN ('appeal', 'assign', 'transfer', 'submit', 'motion', 'xbar') ORDER BY e.date, e.id", (id,)):
            if decision: decision = self.decisions[decision]
            if typecode == 'submit':
                yield ('Caller', player)
            elif typecode == 'xbar':
                yield ('Barred', player)
            elif typecode in ('assign', 'transfer'):
                if not reassign:
                    yield None
                    if case_typecode == 'Appeal':
                        yield ('Panelist', player)
                        yield ('Decision', decision)
                    elif case_typecode == 'Equity Case':
                        yield ('Judge', player)
                        # XXX
                        yield ('Judgement', '(see below)' if decision else '')
                    else:
                        yield ('Judge', player)
                        yield ('Judgement', decision)
                    yield None
            elif typecode == 'appeal':
                yield ('Appeal', str(matter_num))
                yield ('Decision', decision)
                yield None
            elif typecode == 'motion':
                yield ('Motion', '%s.%s' % (num, eid))
                yield ('Decision', decision)
                yield None
            else:
                raise Exception('unknown typecode %s' % typecode)

    def import_(self, path, verbose):
        conn, cursor = self.conn, self.cursor
        it = iter(open(path))
        indices = []
        while True:
            try:
                line = next(it)
            except StopIteration: break
            if line.startswith('CREATE TABLE '):
                stmt = ''.join([line] + grab_lines_until(it, ');\n', include=True))
                stmt = re.sub('DEFAULT .*?(,?)\n', r'\1', stmt)
                stmt = stmt.replace('id integer DEFAULT', 'id integer PRIMARY KEY DEFAULT')
                try_execute(cursor, stmt)
            if line.startswith('COPY '):
                tbl, cols = re.match('^COPY ([^ ]*) (\([^\)]*\)) FROM stdin;', line).groups()
                collist = re.split(', ', cols)
                if not collist: continue
                rows = []
                for row in grab_lines_until(it, '\.\n'):
                    cells = []
                    for col, cell in zip(collist, row[:-1].split('\t')):
                        if col == 'date':
                            if cell and cell != '\N':
                                dt = datetime.datetime.strptime(cell[:-3], '%Y-%m-%d %H:%M:%S')
                                dt += datetime.timedelta(hours=-int(cell[-3:]))
                                cell = time.mktime(dt.timetuple())
                            else:
                                cell = None
                        else:
                            if cell == '\N':
                                cell = None
                            else:
                                def unescape(m):
                                    if m.group(1):
                                        return {'b': '\b', 'f': '\f', 'n': '\n', 'r': '\r', 't': '\t', 'v': '\v', '\\': '\\'}[m.group(1)]
                                    elif m.group(2):
                                        return chr(int(m.group(2), 16))
                                    elif m.group(3):
                                        return chr(int(m.group(3), 8))
                                cell = re.sub(r'\\(([bfnrtv\\])|x([0-9a-fA-F]{1,2})|([0-7]{1,3}))', unescape, cell)
                                cell = stuff.faildecode(cell)
                        cells.append(cell)
                    rows.append(cells)
                istmt = 'INSERT INTO %s VALUES(%s)' % (tbl, ', '.join(['?'] * len(collist)))
                if verbose:
                    print >> sys.stderr, 'inserting %s rows into %s' % (len(rows), tbl)
                    sys.stderr.flush()
                cursor.execute('BEGIN')
                cursor.executemany(istmt, rows)
                cursor.execute('COMMIT')
                #stmt = 'INSERT INTO %s VALUES\n' % tbl
        for stmt in [
            'CREATE INDEX pn ON players (name)',
            'CREATE INDEX mn ON matters (number)',
            'CREATE INDEX em ON events (matter)',
            'CREATE INDEX ed ON events (date)',
            'CREATE INDEX elt ON events (link, typecode)',
            'CREATE INDEX xe ON exhibits (event)',
        ]:
            print >> sys.stderr, stmt.strip()
            cursor.execute(stmt)

class CFJDB(DB):
    path = 'cfjs.sqlite'
    version = 1

    def __init__(self, create=False):
        DB.__init__(self, create)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS documents(
                id integer primary key,
                number blob,
                text blob,
                judges blob,
                outcome blob,
                caller blob
            );
            CREATE TABLE IF NOT EXISTS meta(
                id integer primary key,
                last_date integer default 0,
                update_date intege default 0
            );
            INSERT OR IGNORE INTO meta(id) VALUES(0);
        ''')
        self.cd_update_date = 0

    def finalize(self, verbose=False):
        self.cursor.execute('''
            CREATE INDEX IF NOT EXISTS documents_number ON documents(number);
            CREATE INDEX IF NOT EXISTS documents_outcome ON documents(outcome);
        ''')
        self.set_meta('update_date', time.time())
        self.rematch(verbose)

    def rematch(self, verbose=False):
        if verbose:
            print >> sys.stderr, 'rematch...'
        self.begin()
        cmds = []
        for id, text in self.cursor.execute('SELECT id, text FROM documents'):
            judges = '|%s|' % '|'.join(set(re.findall('^\s*(?:Judge|Panelist):\s*(.*?)\s*$', text, re.M)))
            outcomes = re.findall('^\s*(?:Judgement|Decision):\s*(.*?)\s*$', text, re.M)
            outcome = outcomes[-1] if outcomes else ''
            m = re.search('^(?:Caller|Called by):\s*(.*)$', text, re.M)
            caller = m.group(1) if m else ''
            cmds.append(('UPDATE documents SET judges = ?, outcome = ?, caller = ? WHERE id = ?', (judges, outcome, caller, id)))
        for cmd in cmds:
            self.cursor.execute(*cmd)
        self.commit()

    def insert(self, num, fmt):
        self.cursor.execute('INSERT INTO documents(number, text) VALUES(?, ?)', (num, fmt))

    def all_nums(self):
        return [num for num, in self.cursor.execute('SELECT number FROM documents ORDER BY number')]

    def cached_documents(self):
        ud = self.meta('update_date')
        while self.cd_update_date != ud:
            self.cd = list(dict_execute(self.cursor, 'SELECT * FROM documents'))
            if self.meta('update_date') == ud:
                self.cd_update_date = ud
        return self.cd

pco = None
def do_format((num, verbose)):
    global pco
    if verbose:
        try:
            assert int(num) % 10 == 0
        except: pass
        else:
            print >> sys.stderr, 'progress: formatting %s' % num
            sys.stderr.flush()
    if pco is None:
        pco = CotCDB()
    try:
        return num, pco.format(num)
    except:
        print >> sys.stderr, 'Error formatting case', num
        traceback.print_exc()
        raise

class CotCDatasource(Datasource):
    name = 'cotc'
    urls = [('http://cotc.psychose.ca/db_dump.tar.gz', 'dump.txt')]
    def preprocess_download(cls, text):
        data = gzip.GzipFile(fileobj=cStringIO.StringIO(text)).read()
        try:
            # no point being clever, can't pass GzipFile as fileobj anyway
            tar = tarfile.open('dump.tar', fileobj=cStringIO.StringIO(data))
        except tarfile.ReadError:
            # not a tar file
            pass
        else:
            data = tar.extractfile('cotc.sql').read()
        return data

    def cache(cls, verbose):
        cls.prepare_cotcdb(verbose)
        co = CotCDB()
        cfj = CFJDB(create=True)
        if cfj.new:
            sd = os.path.join(mydir, 'static_data', 'stare_detail')
            for fn in os.listdir(sd):
                num = fn.replace('.txt', '').lstrip('0')
                fn = os.path.join(sd, fn)
                cfj.begin()
                cfj.insert(num, stuff.faildecode(open(fn).read().rstrip()))
                cfj.commit()
        nums = (set(co.all_nums()) - set(cfj.all_nums())) | set(co.nums_since(cfj.meta('last_date')))

        nums = [(num, verbose) for num in nums]
        if verbose:
            print >> sys.stderr, 'Formatting %s new cases...' % len(nums)
        if 1:
            p = multiprocessing.Pool(4)
            fmts = p.map(do_format, nums)
        else:
            fmts = map(do_format, nums)
        if verbose:
            print >> sys.stderr, 'inserting...'
        cfj.begin()
        for num, fmt in fmts:
            if fmt is None: continue
            try:
                cfj.insert(num, fmt)
            except:
                print 'failed to insert', num
        cfj.commit()
        cfj.set_meta('last_date', co.last_date())
        cfj.finalize(verbose)

    def prepare_cotcdb(cls, verbose):
        co = CotCDB(True)
        co.import_(cls.urls[0][1], verbose)

if __name__ == '__main__':
    co = CotCDB()
    print co.format(sys.argv[1])

