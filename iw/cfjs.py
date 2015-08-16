import gzip, re, apsw, sys, datetime, time, os, tarfile, traceback, itertools, yaml
import cStringIO, StringIO
from datasource import Datasource, GitDatasource, DB, DocDB
from pystuff import remove_if_present, mydir, grab_lines_until, CursorWrapper, dict_execute, mydir, mkdir_if_absent, config
import stuff, pystuff, search

def unwrap(x):
    # temporary
    return re.sub('\s*\n\s*', ' ', x.strip())

class CotCDB:
    # vaguely ported from Murphy's PHP code
    def __init__(self):
        # case keys: id, num, typecode, statement, events, linked_events, exhibits
        # event keys: same as db
        self.cases_by_num = {}
        self.cases_by_id = {}
        self.events = {}
        self.decisions = {}
        self.players = {}
        self.last_date = 0

    def all_nums(self):
        return self.cases_by_num.keys()

    def nums_since(self, date):
        res = []
        for num, case in self.cases_by_num.iteritems():
            events = case['events']
            if events and events[-1]['date'] > date:
                res.append(num)
        return res

    def format(self, num):
        f = StringIO.StringIO()
        case = self.cases_by_num[num]
        typecode = case['typecode']
        statement = case['statement']
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

        case['events'] = sorted(case['events'], key=lambda event: event['date'])

        info = list(self.get_info(case))
        if not info: return None
        for bit in info:
            if bit is None:
                print >> f
            else:
                print >> f, ('%s:' % bit[0]).ljust(40) + stuff.twrap(bit[1] if bit[1] is not None else '', subsequent_indent=40)

        if info[-1] is not None: print >> f
        print >> f, eql
        print >> f, '\nHistory:\n'

        history = self.get_history(case)
        for left, right in history:
            left += ':'
            if len(left) > 38:
                print >> f, left
                print >> f, ' ' * 40 + right
            else:
                print >> f, left.ljust(40) + right

        print >> f
        print >> f, eql

        exhibits = self.get_exhibits(case)
        for label, text in exhibits:
            print >> f, '\n%s:\n' % label
            print >> f, stuff.twrap(text, width=78)
            print >> f
            print >> f, eql


        return f.getvalue()[:-1]

    @staticmethod
    def get_linked(event, typecode):
        for event2 in event['linked']:
            if event2['typecode'] == typecode:
                return event2
        return None

    def get_info(self, case):
        def decision(event):
            decision_ev = self.get_linked(event, 'decide')
            if decision_ev:
                return self.decisions.get(decision_ev['decision'], '')
            else:
                return ''
        case_typecode = case['typecode']

        for event in case['events']:
            typecode = event['typecode']
            if event['player']:
                player = self.players[event['player']]
            if typecode in ('submit', 'xbar'):
                if typecode == 'submit':
                    yield ('Caller', player)
                else:
                    yield ('Barred', player)
            elif typecode in ('assign', 'transfer'):
                reassign = any(1 for e2 in event['linked'] if e2['typecode'] in ('assign', 'transfer'))
                if not reassign:
                    yield None
                    dec = decision(event)
                    if case_typecode == 'Appeal':
                        yield ('Panelist', player)
                        yield ('Decision', dec)
                    elif case_typecode == 'Equity Case':
                        yield ('Judge', player)
                        # XXX
                        yield ('Judgement', '(see below)' if dec else '')
                    else:
                        yield ('Judge', player)
                        yield ('Judgement', dec)
                    yield None
            elif typecode == 'appeal':
                yield ('Appeal', self.cases_by_id[self.get_linked(event, 'open')['matter']]['num'])
                yield ('Decision', decision(event))
                yield None
            elif typecode == 'motion':
                yield ('Motion', '%s.%s' % (case['num'], event['id']))
                yield ('Decision', decision(event))
                yield None


    def get_exhibits(self, case):
        def player(event):
            return self.players[event['player']]
        case_typecode = case['typecode']
        num = case['num']
        for event in case['events']:
            typecode = event['typecode']
            for exhibit in event['exhibits']:
                xtypecode = exhibit['typecode']
                j = 'Panelist' if case_typecode == 'Appeal' else 'Judge'
                x = 'Arguments' if xtypecode == 'arguments' else 'Evidence'
                if typecode == 'open':
                    pass # XXX cfa cfas = linked_events
                elif typecode == 'decide':
                    label = "%s %s's %s" % (j, player(event['link']), x)
                elif typecode == 'submit':
                    label = "Caller's %s" % x
                elif typecode == 'order':
                    label = '%s Order(s) by %s' % ('Appellate' if case_typecode == 'Appeal' else 'Judicial', player(event))
                elif typecode == 'cfa':
                    label = "Appellant %s's %s" % (player(event), x)
                elif typecode == 'motion':
                    label = "Motion %s.%s by %s" % (num, event['id'], player(event))
                elif typecode == 'reconsider':
                    label = 'Request for reconsideration by %s' % player
                elif typecode == 'xdecide':
                    label = "Non-%s %s's %s" % (j, player(event), x)
                elif typecode == 'xcomment':
                    label = "Gratuitous %s by %s" % (x, player(event))
                else:
                    raise Exception('unknown typecode %s' % typecode)
                yield (label, exhibit['text'])

    def get_history(self, case):
        def player(event):
            return self.players[event['player']]
        remanded = False
        case_typecode = case['typecode']
        num = case['num']
        for event in case['events']:
            date = event['date']
            date = datetime.datetime.utcfromtimestamp(date)
            date = date.strftime('%d %b %Y %H:%M:%S GMT')
            fmt = None
            typecode = event['typecode']
            if typecode == 'submit':
                fmt = ('Called by %s' % player(event))
            elif typecode == 'assign':
                if remanded:
                    fmt = 'Remanded to %s' % player(event)
                    remanded = False
                else:
                    fmt = 'Assigned to %s%s' % (player(event), ' (panelist)' if case_typecode == 'Appeal' else '')
            elif typecode == 'decide':
                player2 = event['link']['player']
                if player2: player2 = self.players[player2]
                decision = self.decisions.get(event['decision'], '')
                if case_typecode == 'Appeal':
                    fmt = '%s moves to %s' % (player2, decision)
                elif player2:
                    if decision == 'DISMISS':
                        fmt = 'Dismissed by %s' % player2
                    elif decision == 'GRANT':
                        fmt = 'Motion %s.%s GRANTED by %s' % (num, event['link']['id'], player2)
                    elif decision == 'DENY':
                        fmt = 'Motion %s.%s DENIED by %s' % (num, event['link']['id'], player2)
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
                fmt = 'Reconsideration requested by %s' % player(event)
            elif typecode == 'appeal':
                fmt = 'Appeal %s' % self.cases_by_id[self.get_linked(event, 'open')['matter']]['num']
            elif typecode == 'cfa':
                fmt = 'Appealed by %s' % player(event)
            elif typecode == 'distribute':
                fmt = 'Judgement distributed'
            elif typecode == 'transfer':
                player2 = self.players[event['link']['player']]
                fmt = 'Transferred from %s to %s' % (player2, player(event))
            elif typecode == 'recuse':
                player2 = self.players[event['link']['player']]
                fmt = '%s recused%s' % (player2, ' (panelist)' if case_typecode == 'Appeal' else '')
            elif typecode == 'open':
                fmt = 'Appeal initiated'
            elif typecode == 'close':
                fmt = 'Final decision (%s)' % self.decisions[event['link']['decision']]
            elif typecode == 'order':
                fmt = 'Order(s) issued'
            elif typecode == 'stay':
                fmt = 'Order(s) stayed'
            elif typecode == 'vacate':
                fmt = 'Order(s) vacated'
            elif typecode == 'motion':
                fmt = 'Motion %s.%s by %s' % (num, event['id'], player(event))
            elif typecode == 'inform':
                try:
                    fmt = 'Defendant %s informed' % player(event)
                except KeyError:
                    fmt = 'Parties informed'
            elif typecode == 'ptend':
                fmt = 'Pre-trial phase ended'
            else:
                continue
            yield (fmt, date)

    def import_decisions(self, row):
        self.decisions[row['id']] = row['text']

    def import_events(self, row):
        row['exhibits'] = []
        row['linked'] = []
        case = self.cases_by_id.setdefault(row['matter'], {})
        case.setdefault('events', []).append(row)
#        if row['typecode'] == 'cfa':
#            lcase = self.cases_by_id.setdefault(row['link'], {})
#            lcase.setdefault('events', []).append(row)
        self.last_date = max(self.last_date, row['date'])
        self.events[row['id']] = row

    def post_events(self):
        for row in self.events.itervalues():
            link = row['link']
            if link:
                e2 = self.events[link]
                e2['linked'].append(row)
                row['link'] = e2

    def import_matters(self, row):
        if not row['number']:
            # bad row
            return
        case = self.cases_by_id.setdefault(row['id'], {})
        case['id'] = row['id']
        case['num'] = row['number']
        case['typecode'] = row['typecode']
        case['statement'] = row['statement']
        case['interest'] = row['interest']
        case.setdefault('events', [])
        self.cases_by_num[str(case['num'])] = case

    def import_players(self, row):
        self.players[row['id']] = row['name']

    def import_exhibits(self, row):
        self.events[row['event']]['exhibits'].append(row)

    def import_(self, fp, verbose):
        it = iter(fp)
        integer_keys = {}
        while True:
            try:
                line = next(it)
            except StopIteration: break
            if line.startswith('CREATE TABLE '):
                m = re.match('CREATE TABLE ([^\(]+?)\s*\(', line)
                tbl = m.group(1)
                text = ''.join(grab_lines_until(it, ');\n'))
                integer_keys[tbl] = set(re.findall('(\w+) integer', text))


            if line.startswith('COPY '):
                tbl, cols = re.match('^COPY ([^ ]*) \(([^\)]*)\) FROM stdin;', line).groups()
                lines = grab_lines_until(it, '\.\n')
                fn = getattr(self, 'import_' + tbl, None)
                if fn is None:
                    continue
                collist = cols.split(', ')
                ik = integer_keys[tbl]
                if not collist: continue
                for row in lines:
                    cells = {}
                    for col, cell in itertools.izip(collist, row[:-1].split('\t')):
                        if cell == '\N':
                            cell = None
                        elif col == 'date':
                            dt = datetime.datetime.strptime(cell[:-3], '%Y-%m-%d %H:%M:%S')
                            dt += datetime.timedelta(hours=-int(cell[-3:]))
                            cell = time.mktime(dt.timetuple())
                        elif col in ik:
                            cell = int(cell)
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
                        cells[col] = cell
                    fn(cells)
                fn = getattr(self, 'post_' + tbl, None)
                if fn is not None: fn()

class CFJDB(DocDB):
    name = 'cfjs'

    doc_table = 'cfjs'
    doc_keycol = 'number'
    doc_ordercol = 'number_base'
    doc_textcol = 'text'

    path = 'cfjs.sqlite'
    version = 2

    def datasources(self):
        return [StaticCFJDatasource.instance(), CotCDatasource.instance(), GitCFJDatasource.instance()]

    def __init__(self):
        super(CFJDB, self).__init__()

        if self.new:
            self.cursor.execute('''
                CREATE TABLE cfjs(
                    id integer primary key,
                    number blob,
                    number_base integer,
                    text blob,
                    judges blob,
                    outcome blob,
                    caller blob,
                    summary blob
                );
                CREATE UNIQUE INDEX IF NOT EXISTS cfjs_number ON cfjs(number);
            ''')

        if config.use_search:
            self.idx = search.CombinedIndex('cfjs_search', self)

    def finalize(self, verbose=False):
        self.cursor.execute('''
            CREATE INDEX IF NOT EXISTS cfjs_number_base ON cfjs(number_base);
            CREATE INDEX IF NOT EXISTS cfjs_outcome ON cfjs(outcome);
            CREATE INDEX IF NOT EXISTS cfjs_caller ON cfjs(caller);
        ''')
        self.set_meta('update_date', time.time())
        self.rematch(verbose)

    def rematch(self, verbose=False):
        if verbose:
            print >> sys.stderr, 'rematch...'
        self.begin()
        updates = []
        for id, text in self.items():
            judges = '|%s|' % '|'.join(set(re.findall('^\s*(?:Judge|Panelist):\s*(.*?)\s*$', text, re.M)))
            outcomes = re.findall('^\s*(?:Judgement|Decision):\s*(.*?)\s*$', text, re.M)
            outcome = outcomes[-1] if outcomes else ''
            m = re.search('^(?:Caller|Called by):\s*(.*)$', text, re.M)
            caller = m.group(1) if m else ''
            summary = '?'
            if re.match('^[0-9]+$', id): # no statements for appeals
                m = re.search('^=======.*$((.|\n)*?)^=======', text, re.M)
                if m:
                    summary = m.group(1).strip()
                    summary = re.sub('^.*CFJ %s\s*\n' % id, '', summary)
                    summary = unwrap(summary)

            updates.append((judges, outcome, caller, summary, id))
        self.cursor.executemany('UPDATE cfjs SET judges = ?, outcome = ?, caller = ?, summary = ? WHERE number = ?', updates)

        self.commit()
        self.reindex_if_necessary(verbose)

    def insert(self, num, fmt):
        base = int(re.match('^[0-9]*', num).group(0))
        self.cursor.execute('INSERT OR REPLACE INTO cfjs(number, number_base, text) VALUES(?, ?, ?)', (num, base, fmt))
        # don't index here because values can change
        self.dirty = True

    def summaries(self):
        return list(self.cursor.execute('SELECT number, summary FROM cfjs ORDER BY number_base DESC, number'))

    def fix_row(self, row):
        row['title'] = 'CFJ %s' % row['number']
        return row

    def add_cli_options(self, parser, argsf):
        parser.add_argument('--cfj-rematch', action=pystuff.action(lambda: self.rematch(True)))
        super(CFJDB, self).add_cli_options(parser, argsf)


class CotCDatasource(Datasource):
    name = 'cotc'
    # No longer available
    #urls = [('http://cotc.psychose.ca/db_dump.tar.gz', 'dump.txt')]

    def __init__(self):
        super(CotCDatasource, self).__init__()
        self.db_dump = os.path.join(mydir, 'static_data', 'db_dump.tar.gz')

    def preprocess_download(self, text):
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

    def cache(self, verbose):
        cfj = CFJDB.instance()
        if os.path.getmtime(self.db_dump) < int(cfj.meta('cotc_last_date', 0)):
            return
        co = self.prepare_cotcdb(verbose)
        nums = (set(co.all_nums()) - set(cfj.keys())) | set(co.nums_since(int(cfj.meta('cotc_last_case', 0))))

        if verbose:
            print >> sys.stderr, 'Formatting %s new cases...' % len(nums)
        fmts = []
        for num in sorted(nums):
            try:
                assert int(num) % 10 == 0
            except: pass
            else:
                print >> sys.stderr, 'progress: formatting %s' % num
                sys.stderr.flush()
            try:
                fmts.append((num, co.format(num)))
            except:
                print >> sys.stderr, 'Error formatting %s:' % num
                raise
        if verbose:
            print >> sys.stderr, 'inserting...'
        cfj.begin()
        for num, fmt in fmts:
            if fmt is None: fmt = ''
            try:
                cfj.insert(num, fmt)
            except Exception, e:
                if isinstance(e, KeyboardInterrupt): raise
                print >> sys.stderr, 'failed to insert', num
                traceback.print_exc()
        cfj.commit()
        cfj.set_meta('cotc_last_case', co.last_date)
        cfj.set_meta('cotc_last_date', int(time.time()))

    def prepare_cotcdb(self, verbose):
        co = CotCDB()
        #co.import_(self.urls[0][1], verbose)
        zipped = open(self.db_dump, 'rb').read()
        unzipped = self.preprocess_download(zipped)
        co.import_(cStringIO.StringIO(unzipped), verbose)
        return co

class StaticCFJDatasource(Datasource):
    name = 'static-cfjs'
    def cache(self, verbose):
        cfj = CFJDB.instance()
        nums = set(cfj.keys())
        sd = os.path.join(mydir, 'static_data', 'stare_detail')
        cfj.begin()
        for fn in os.listdir(sd):
            num = fn.replace('.txt', '').lstrip('0')
            if num not in nums:
                fn = os.path.join(sd, fn)
                cfj.insert(num, stuff.faildecode(open(fn).read().rstrip().replace('\r', '')))
        cfj.commit()

class GitCFJDatasource(GitDatasource):
    name = 'git-cfjs'
    urls = [('https://github.com/comex/agora-cfjs.git', 'agora-cfjs')]
    def cache(self, verbose):
        cfj = CFJDB.instance()
        nums = set(cfj.keys())
        fmts = []
        last_date = int(cfj.meta('git_last_date', 0))
        for fn in os.listdir(self.urls[0][1]):
            m = re.match('^([0-9].*)\.yaml', fn)
            if not m:
                continue
            fn = os.path.join(self.urls[0][1], fn)
            if os.path.getmtime(fn) < last_date:
                continue
            num = m.group(1).lstrip('0')
            if num not in nums:
                fmts.append((num, self.format(num, fn)))
        cfj.begin()
        for num, fmt in fmts:
            cfj.insert(num, fmt)
        cfj.commit()
        cfj.set_meta('git_last_date', int(time.time()))

    def format(self, num, fn):
        root = yaml.load(open(fn))
        f = StringIO.StringIO()
        eql = '=' * 72
        hdr = 'CFJ %s' % (num,)
        heql = '=' * (34 - len(hdr) / 2)
        print >> f, '%s  %s  %s' % (heql, hdr, heql)
        print >> f
        print >> f, stuff.twrap(root['statement'], indent=4)
        print >> f
        print >> f, eql
        print >> f

        judge = None
        for event in root['events']:
            ty = event['type']
            if ty == 'called':
                desc = 'Called by %s' % (event['who'],)
            elif ty == 'assigned':
                desc = 'Assigned to %s' % (event['who'],)
                judge = event['who']
            elif ty == 'recused':
                if judge is None:
                    raise Exception("'recused' without previous 'assigned'")
                desc = '%s recused' % (judge,)
            elif ty == 'judged':
                desc = 'Judged %s' % (event['judgement'],)
            elif ty == 'appealed':
                desc = 'Appealed by %s' % (event['who'],)
            elif ty == 'reconsider?':
                desc = 'Reconsideration requested by %s' % (event['who'],)
            elif ty == 'reconsider!':
                desc = 'Reconsideration initiated by %s' % (event['who'],)
            elif ty == 'moot?':
                desc = 'Moot intent by %s' % (event['who'],)
            elif ty == 'moot!':
                desc = 'Mooted by %s' % (event['who'],)
            else:
                raise Exception('unknown event type %r' % ty)
            date = event['date']
            if not isinstance(date, basestring):
                assert isinstance(date, datetime.datetime)
                date = date.strftime('%d %b %Y %H:%M:%S')
            print >> f, ('%-52s%s' % (desc + ':', stuff.twrap(date, subsequent_indent=40)))

        print >> f
        print >> f, eql

        for ex in root['exhibits']:
            who = ex['who']
            mid = ex['mid']
            text = ex['text']
            ty = {'judgement': 'Judgement', 'exhibit': 'Exhibit'}[ex.get('type', 'exhibit')]

            print >> f
            print >> f, mid
            print >> f, '%s by %s:' % (ty, who,)
            print >> f
            print >> f, stuff.twrap(text, width=78)
            print >> f
            print >> f, eql

        print >> f

        return f.getvalue()[:-1]

if __name__ == '__main__':
    if sys.argv[1].endswith('.yaml'):
        print GitCFJDatasource.instance().format('XXXX', sys.argv[1])
    else:
        co = CotCDatasource().prepare_cotcdb(False)
        print co.format(sys.argv[1])


