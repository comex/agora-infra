import cfjs, messages, pystuff, search
import web
pystuff.fix_web()
import os, threading, re, __builtin__, urlparse, urllib2

t_globals = {}
t_globals.update(__builtin__.__dict__)

render = web.template.render(os.path.join(pystuff.mydir, 'templates'), base='base', globals=t_globals)

if pystuff.config.is_qoid_us:
    domains = {
        'cfj': 'cfj.qoid.us',
        '*root*': 'iw.qoid.us',
    }
else:
    domains = {}

def render_section_link(page, kind, link, title):
    if page.page == kind:
        return title
    else:
        s = ''
        is_kind = page.get('kind') == kind
        if is_kind: s += '<i>'
        s += '<a href="%s">%s</a>' % (fix_link(link), title)
        if is_kind: s += '</i>'
        return s
t_globals['render_section_link'] = render_section_link

def fix_link(link):
    try:
        firstdir, rest = link.split('/', 1)
    except ValueError:
        firstdir, rest = link, ''
    domain = domains.get(firstdir)
    if domain is not None:
        return 'http://%s/%s' % (domain, rest)
    elif domains.has_key('*root*'):
        return 'http://%s/%s' % (domains['*root*'], link)
    else:
        return '/%s' % (link,)
t_globals['fix_link'] = fix_link

def link_to(link, text):
    return '<a href="%s">%s</a>' % (fix_link(link), text)

def autolink(text, kind=''):
    text = web.websafe(text)
    text = re.sub('(Appeal|CFJ)[\s\n]*([0-9]+[a-z]?)',
        lambda m: link_to('cfj/%s' % m.group(2), m.group(0)), text)
    if kind == 'cfj':
        # Appeal:                                 1831
        text = re.sub(re.compile('(^Appeal:\s+)([0-9]+[a-z]?)', re.M),
            lambda m: m.group(1) + link_to('cfj/%s' % m.group(2), m.group(2)), text)
    def mess(m):
        mid = m.group(2) or m.group(3)
        unmid = mid.replace('&lt;', '<').replace('&gt;', '>') # xxx
        return (m.group(1) or '') + link_to('message/?search=message-id:%s' % urllib2.quote(unmid), mid)
    text = re.sub('(Message-ID: )(&lt;[^&]*&gt;)|(&lt;([^&@]{25,}|[0-9A-F]{5,}[^&@]*)@[^&]*&gt;)', mess, text)
    return text

def plaintext(text):
     web.header('Content-Type', 'text/plain')
     return text

def do_search(expr, db, base, redirect_if_one, get_title):
    # todo: pagination
    opts = {}
    limit = None
    if base == 'message':
        opts['require_trigrams'] = True
        limit = 100
    kind, snd = db.search(expr, limit=limit, opts=opts)
    errors = results = None
    if kind == 'empty':
        return
    elif kind == 'errors':
        errors = snd
    elif kind == 'timeout':
        errors = ['Query timeout.']
    elif kind == 'ok':
        results = []
        for id, ctxs in snd:
            row = db.get_by_id(id)
            results.append((
                get_title(row),
                fix_link('%s/%s' % (base, row[db.doc_keycol])),
                search.highlight_snippets(row[db.doc_textcol], ctxs).html()
            ))
        if len(results) == 1 and redirect_if_one:
            raise web.seeother(results[0][1])
    else:
        assert False

    return render.searchresults(expr, errors, results, base)

def parse_query():
    q = web.ctx.query
    if q == '':
        return {}
    return urlparse.parse_qs(q[1:], keep_blank_values=True)

class messages_uid:
    def GET(self, uid, extension):
        db = messages.MessagesDB.instance()
        row = db.get(uid)
        if row is None:
            raise web.NotFound(render.fourohfour())
        if extension == '.txt':
            return plaintext(db.get_orig(row))
        text = autolink(row['text'], 'message')
        return render.message(
            title=row['subject'],
            doc=text,
            txt='%s.txt' % (uid,),
        )

class messages_main:
    def GET(self):
        query = parse_query()
        db = messages.MessagesDB.instance()
        if query.has_key('search'):
            if len(query.get('search', ())) >= 1:
                expr = query['search'][0]
                redirect_if_one = bool(re.match('^message-id:[^"/\s()]+$', expr))
                result = do_search(expr, db, 'message', redirect_if_one,
                    lambda row: row['subject'])
                if result is not None:
                    return result
            return render.searchhelp()
        return plaintext('todo')

class cfj_num:
    def GET(self, num, extension):
        cfj = cfjs.CFJDB.instance().get(num)
        if cfj is None:
            raise web.NotFound(render.fourohfour())
        text = cfj['text']
        if extension == '.txt':
            return plaintext(text)
        text = autolink(text, 'cfj')
        return render.doc(
            title=cfj['title'],
            doc=text,
            txt='%s.txt' % (num,),
        )

class cfj_main:
    def GET(self):
        query = parse_query()
        if query.has_key('search'):
            if len(query.get('search', ())) >= 1:
                result = do_search(query['search'][0], cfjs.CFJDB.instance(), 'cfj', False,
                    lambda row: row['title'])
                if result is not None:
                    return result
            return render.searchhelp()
        # just list all CFJs
        summaries = cfjs.CFJDB.instance().summaries()
        return render.cfjs(
            summaries=summaries,
        )

class index:
    def GET(self):
        return "Hello, world!"

lock = threading.Lock()
def lock_it(handler):
    with lock:
        return handler()

def main():
    web.config.debug = True
    cfj_app = web.application([
        '/([0-9]+[a-z]?)(\.txt)?', 'cfj_num',
        '/?', 'cfj_main',
    ], globals())
    iw_app = web.application([
        '/message/?', 'messages_main',
        '/message/(.*?)(\.txt)?', 'messages_uid',
        '/cfj', cfj_app,
        '/', 'index',
    ], globals())
    app = web.subdomain_application([
        'cfj.qoid.us', cfj_app,
        '.*', iw_app,
    ])
    app.add_processor(lock_it)
    app.run()

