import os, re, sre_parse, sys, functools, threading
import email
from email.utils import parsedate_tz, mktime_tz, formatdate
from datasource import Datasource, DB, DocDB
from pystuff import mydir, fnmmap, config, lru_cache
import search, stuff

# faster replacement (may not be necessary on py3)
def qdecode(text):
    def repl(m):
        g = m.group(1)
        if g == '\n':
            return ''
        else:
            return chr(int(g, 16))
    return re.sub('=(\n|[0-9a-fA-F]{2})', repl, text)
email.utils._qdecode = qdecode

def parse_date(date):
    return mktime_tz(parsedate_tz(date))

class HeaderOperator:
    def __init__(self, mdb, hdr, dbcol, exact=False):
        self.mdb, self.hdr, self.dbcol, self.exact = mdb, hdr, dbcol, exact
        if not exact:
            self.idx = search.WordIndex('messages_search_' + dbcol, mdb)
    def search_word(self, query, *args, **kwargs):
        if self.exact:
            return [(id, []) for id, in self.mdb.cursor.execute('SELECT id FROM %s WHERE %s = ?' % (self.mdb.doc_table, self.dbcol), (query,))]
        else:
            return self.idx.search(*args, **kwargs)
    def search_get_all(self, asc=True):
        return self.mdb.cursor.execute('SELECT id, %s FROM %s ORDER BY id %s' % (self.dbcol, self.mdb.doc_table, 'ASC' if asc else 'DESC'))

class MessagesDB(DocDB):
    path = 'messages.sqlite'
    doc_table = 'messages'
    doc_keycol = 'uniq_message_id'
    doc_ordercol = 'id'
    doc_textcol = 'text'
    name = 'messages'
    version = 1

    def datasources(self):
        return [MessagesDatasource.instance()]

    def __init__(self):
        super(MessagesDB, self).__init__()
        self.search_operators['message-id'] = HeaderOperator(self, 'Message-ID', 'message_id', exact=True)
        self.search_operators['from']       = HeaderOperator(self, 'From',       'from_')
        self.search_operators['to']         = HeaderOperator(self, 'To',         'to_')
        self.search_operators['subject']    = HeaderOperator(self, 'Subject',    'subject')
        if self.new:
            self.cursor.execute('''
                CREATE TABLE messages(
                    id integer primary key,
                    uniq_message_id blob,
                    start integer,
                    end integer,
                    subject blob,
                    from_ blob,
                    to_ blob,
                    message_id blob,
                    text blob,
                    real_date integer,
                    list_id integer
                );
                CREATE UNIQUE INDEX mumi ON messages(uniq_message_id);
            ''')
        if config.use_search:
            self.idx = search.CombinedIndex('messages_search', self)
        self.get = lru_cache(1024)(self.get)
        self.lock = threading.Lock()

    def begin(self):
        DB.begin(self)
        self.dates = set(date for date, in self.cursor.execute('SELECT real_date FROM messages'))

    def insert(self, info):
        self.dates.add(id)
        text = 'From: %s\nTo: %s\nSubject: %s\nReal-Date: %s\nMessage-ID: %s\n\n%s' % (
            info['From'],
            info['To'],
            info['Subject'],
            formatdate(info['real_date']),
			info['Message-ID'],
            info['text']
        )
        umi = info['Message-ID']
        count = 0
        while True:
            bits = (
                umi,
                info['start'],
                info['end'],
                info['Subject'],
                info['From'],
                info['To'],
                info['Message-ID'],
                text,
                info['real_date'],
                info['list_id']
            )
            self.cursor.execute('INSERT OR IGNORE INTO messages(uniq_message_id, start, end, subject, from_, to_, message_id, text, real_date, list_id) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', bits)
            if self.conn.changes() != 0:
                break
            # we got a duplicate Message-ID
            umi = '%s.%s' % (info['Message-ID'], count)
            count += 1
        rowid = self.conn.last_insert_rowid()
        if config.use_search:
            self.idx.insert(rowid, text)
            for ho in self.search_operators.values():
                if ho is self or not hasattr(ho, 'idx'): continue
                ho.idx.insert(rowid, info[ho.hdr])

    def last_end(self, list_id):
        res = self.cursor.execute('SELECT end FROM messages WHERE list_id = ? ORDER BY rowid DESC limit 1', (list_id,))
        try:
            return next(res)[0]
        except StopIteration:
            return 0

    def finalize(self):
        self.cursor.execute('''
            CREATE INDEX IF NOT EXISTS mmi ON messages(message_id);
            CREATE INDEX IF NOT EXISTS mf ON messages(from_);
            CREATE INDEX IF NOT EXISTS mt ON messages(to_);
            CREATE INDEX IF NOT EXISTS ms ON messages(subject);
            CREATE INDEX IF NOT EXISTS mrd ON messages(real_date);
            CREATE INDEX IF NOT EXISTS mli ON messages(list_id);
        ''')

    def get_orig(self, row):
        return MessagesDatasource.instance().mmaps[row['list_id']][row['start']:row['end']]

    is_super_big = True

class MessagesDatasource(Datasource):
    name = 'messages'
    urls = [
        ('http://agora:nomic@www.agoranomic.org/archives/agora-business.mbox', 'agora-business.mbox'),
        ('http://agora:nomic@www.agoranomic.org/archives/agora-discussion.mbox', 'agora-discussion.mbox'),
        ('http://agora:nomic@www.agoranomic.org/archives/agora-official.mbox', 'agora-official.mbox'),
    ]

    def __init__(self):
        if config.local_dir:
            def check_local((url, fn)):
                local = os.path.join(config.local_dir, os.path.basename(fn))
                return (None, local) if os.path.exists(local) else (url, fn)
            self.urls = map(check_local, self.urls)
        super(MessagesDatasource, self).__init__()

    def download(self, *args, **kwargs):
        kwargs['use_cont'] = True
        return super(MessagesDatasource, self).download(*args, **kwargs)

    def cache(self, verbose=False):
        db = MessagesDB.instance()
        db.begin()
        for list_id, (url, path) in enumerate(self.urls):
            if verbose:
                print >> sys.stderr, path
            mm = fnmmap(path)
            start = min(db.last_end(list_id) - 2, 0)
            starts = [start + m.start() + 2 for m in re.finditer('\n\nFrom .*@', buffer(mm, start))]
            cnt = len(starts)
            print >> sys.stderr, 'got %s messages after %s' % (cnt, start)
            starts.append(len(mm))
            for i in xrange(cnt):
                if verbose and i % 1000 == 0:
                    print >> sys.stderr, '%s/%s' % (i, cnt)
                s, e = starts[i], starts[i+1]
                msg = buffer(mm, s, e - s)
                em = email.message_from_string(msg)
                info = {}
                info['start'], info['end'] = s, e
                rec = em['Received'] or ''
                info['real_date'] = parse_date(rec[rec.rfind('; ') + 2:])
                info['list_id'] = list_id
                for a in ('From', 'To', 'Subject', 'Date', 'Message-ID'):
                    info[a] = stuff.faildecode(em[a] or '')
                for part in em.walk():
                    if part.get_content_type() == 'text/plain':
                        info['text'] = stuff.maildecode(part)
                        stuff.faildecode(part.get_payload(decode=True))
                        break
                else:
                    info['text'] = stuff.maildecode(em)
                # It seems that a significant amount of overhead is apsw
                # encoding the data back to UTF-8.  But since I'm not sure
                # whether it's valid, I'm not sure it's worth fixing.
                db.insert(info)
            mm.close()
        db.commit()
        db.finalize()
