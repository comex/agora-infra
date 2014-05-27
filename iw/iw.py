#!/usr/bin/env python
import cfjs, pystuff, search
import web
pystuff.fix_web()
import os, threading, re, __builtin__, urlparse

t_globals = {}
t_globals.update(__builtin__.__dict__)

render = web.template.render(os.path.join(pystuff.mydir, 'templates'), base='base', globals=t_globals)

if pystuff.config.is_qoid_us:
    domains = {
        'cfj': 'cfj.qoid.us',
    }
else:
    domains = {}

def fix_link(link):
    try:
        firstdir, rest = link.split('/', 1)
    except ValueError:
        firstdir, rest = link, ''
    domain = domains.get(firstdir)
    if domain is not None:
        return 'http://%s/%s' % (domain, rest)
    else:
        return '/%s' % (link,)
t_globals['fix_link'] = fix_link

def link_to(link, text):
    return '<a href="%s">%s</a>' % (web.websafe(fix_link(link)), text)

def autolink(text, kind=''):
    text = web.websafe(text)
    text = re.sub('(Appeal|CFJ)[\s\n]*([0-9]+[a-z]?)',
        lambda m: link_to('cfj/%s' % m.group(2), m.group(0)), text)
    if kind == 'cfj':
        # Appeal:                                 1831
        text = re.sub(re.compile('(^Appeal:\s+)([0-9]+[a-z]?)', re.M),
            lambda m: m.group(1) + link_to('cfj/%s' % m.group(2), m.group(2)), text)

    return text

def plaintext(text):
     web.header('Content-Type', 'text/plain')
     return text

def parse_query():
    q = web.ctx.query
    if q == '':
        return {}
    return urlparse.parse_qs(q[1:], keep_blank_values=True)

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

def cfj_search(expr):
    cfjdb = cfjs.CFJDB.instance()
    kind, snd = cfjdb.search(expr, limit=None)
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
            row = cfjdb.get_by_id(id)
            results.append((
                row['title'],
                fix_link('cfj/%s' % row['number']),
                search.highlight_snippets(row['text'], ctxs).html()
            ))
    else:
        assert False

    return render.searchresults(expr, errors, results)

class cfj_main:
    def GET(self):
        query = parse_query()
        if query.has_key('search'):
            if len(query.get('search', ())) >= 1:
                result = cfj_search(query['search'][0])
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

urls = [
    '/cfj/([0-9]+[a-z]?)(\.txt)?', 'cfj_num',
    '/cfj/?', 'cfj_main',
    '/', 'index',
]


lock = threading.Lock()
def lock_it(handler):
    with lock:
        return handler()

if __name__ == "__main__":
    web.config.debug = True
    app = web.application(urls, globals())
    app.add_processor(lock_it)
    app.run()

