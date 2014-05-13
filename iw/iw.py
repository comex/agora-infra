#!/usr/bin/env python
import cfjs, pystuff
import web
import threading, re, __builtin__, urlparse

t_globals = {}
t_globals.update(__builtin__.__dict__)

render = web.template.render('templates', base='base', globals=t_globals)

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
    return urlparse.parse_qs(q[1:])

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
            title='CFJ %s' % cfj['number'],
            doc=text,
            txt='%s.txt' % (num,),
        )

class cfj_main:
    def GET(self):
        query = parse_query()
        if query.has_key('search'):
            return cfj_search(query['search'])
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


subdomains = []
for path, domain in domains.items():
    durls = sum(((subpath[len(path)+1:], handler) for (subpath, handler) in zip(urls[0::2], urls[1::2]) if subpath.startswith('/' + path)), [])
    print durls
    subdomains.extend([domain, web.application(durls, globals())])
subdomains.extend(['.*', web.application(urls, globals())])

lock = threading.Lock()
def lock_it(handler):
    with lock:
        return handler()

if __name__ == "__main__":
    web.config.debug = True
    app = web.subdomain_application(subdomains)
    app.add_processor(lock_it)
    app.run()

