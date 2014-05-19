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

class MessagesDB(DocDB):
    path = 'messages.sqlite'
    doc_table = 'messages'
    doc_keycol = 'id'
    doc_textcol = 'text'
    version = 0
    def __init__(self, create=False):
        DB.__init__(self, create)
        if self.new:
            self.cursor.execute('''
                CREATE TABLE messages(
                    id integer primary key,
                    start integer,
                    end integer,
                    subject text,
                    from_ text,
                    to_ text,
					message_id text,
                    text text,
                    real_date integer,
                    list_id integer
                );
            ''')
        if config.use_search:
            self.idx = search.CombinedIndex('messages_search', self)
        self.get = lru_cache(1024)(self.get)
        self.lock = threading.Lock()

    def begin(self):
        DB.begin(self)
        self.dates = set(date for date, in self.cursor.execute('SELECT real_date FROM messages'))

    def cache(self, info):
        def fd(hdr):
            return stuff.faildecode(info.get(hdr, ''))
        id = info['real_date'] * 1000
        while id in self.dates: id += 1
        self.dates.add(id)
        text = 'id: %s\nFrom: %s\nTo: %s\nSubject: %s\nReal-Date: %s\nMessage-ID: %s\n\n%s' % (
			id,
            info['From'],
            info['To'],
            info['Subject'],
            formatdate(info['real_date']),
			info['Message-ID'],
            info['text']
        )
        bits = (
            id,
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
        self.cursor.execute('INSERT INTO messages(id, start, end, subject, from_, to_, message_id, text, real_date, list_id) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', bits)
        if config.use_search:
            self.idx.insert(id, text)

    def last_end(self, list_id):
        res = self.cursor.execute('SELECT end FROM messages WHERE list_id = ? ORDER BY rowid DESC limit 1', (list_id,))
        try:
            return next(res)[0]
        except StopIteration:
            return 0

    def finalize(self):
        self.cursor.execute('''
            CREATE INDEX mt ON messages(to);
            CREATE INDEX mrd ON messages(real_date);
            CREATE INDEX mli ON messages(list_id);
            CREATE INDEX mmi ON messages(message_id);
        ''')

class MessagesDatasource(Datasource):
    name = 'messages'
    urls = [
        ('http://agora:nomic@www.agoranomic.org/archives/agora-business.mbox', 'agora-business.mbox'),
        ('http://agora:nomic@www.agoranomic.org/archives/agora-discussion.mbox', 'agora-discussion.mbox'),
        ('http://agora:nomic@www.agoranomic.org/archives/agora-official.mbox', 'agora-official.mbox'),
    ]
    DB = MessagesDB

    def __init__(self):
        if config.local_dir:
            def check_local((url, fn)):
                local = os.path.join(config.local_dir, os.path.basename(fn))
                return (None, local) if os.path.exists(local) else (url, fn)
            self.urls = map(check_local, self.urls)
        Datasource.__init__(self)

    def download(self, *args, **kwargs):
        kwargs['use_cont'] = True
        return Datasource.download(self, *args, **kwargs)

    def cache(self, verbose=False):
        db = MessagesDB(create=True)
        db.begin()
        for list_id, (url, path) in enumerate(self.urls):
            if verbose:
                print >> sys.stderr, path
            mm = fnmmap(path)
            start = db.last_end(list_id)
            starts = [start + m.start() + 2 for m in re.finditer('\n\nFrom .*@', buffer(mm, start))]
            print >> sys.stderr, 'regex done'
            cnt = len(starts)
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
                        info['text'] = stuff.faildecode(part.get_payload(decode=True))
                        break
                else:
                    info['text'] = stuff.faildecode(em.get_payload(decode=True))
                db.cache(info)
        db.commit()