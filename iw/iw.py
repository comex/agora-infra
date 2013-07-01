#!/usr/bin/env python
import web

urls = (
    '(.*)', 'index'
)

class index:
    def GET(self, path):
        return "Hello, world!<%s>" % (path,)

if __name__ == "__main__":
    web.config.debug = True
    app = web.application(urls, globals())
    app.run()

