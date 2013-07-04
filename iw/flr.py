import cPickle as pickle
from cStringIO import StringIO
import array, zlib, sys
from datasource import Datasource
from pystuff import remove_if_present
import rcs

class FLRDB(object):
    def __init__(self, create=False):
        self.load_pickle()

    def load_pickle(self):
        data = pickle.load(open(FLRDatasource.cachefiles[0], 'rb'))
        self.revs = {}
        for rev in data['revs']:
            ar = array.array('I')
            ar.fromstring(rev['text'])
            rev['text'] = ar
            self.revs[rev['num']] = rev
        self.indirect = data['indirect']

    def get_revision(self, rev):
        ar = self.revs[rev]['text']
        data = StringIO()
        for off in ar:
            line = self.indirect[off:self.indirect.find('\n', off) + 1]
            data.write(line)
        return data.getvalue()

class FLRDatasource(Datasource):
    name = 'flr'
    urls = [('https://www.eecs.berkeley.edu/~charles/agora/current_flr.txt_comma_v', 'current_flr.txt,v')]
    cachefiles = ['flr_revs.pickle']

    def _cache(cls, verbose):
        indirect = StringIO()
        revs = rcs.RCSFile(open(cls.urls[0][1]).read()).get_revisions(indirect)
        for rev in revs:
            ar = array.array('I')
            ar.fromlist(rev['text'])
            rev['text'] = ar.tostring()
        data = {'revs': revs, 'indirect': indirect.getvalue()}
        pickle.dump(data, open(cls.cachefiles[0], 'wb'), -1)

if __name__ == '__main__':
    for i in xrange(100):
        x = FLRDB().get_revision('1.1100')
    sys.stdout.write(x)

class RulesDatasource(Datasource):
    name = 'rules'
    def download(cls, verbose=False):
        return FLRDatasource.download(verbose)
    name = 'rules'
    cachefiles = ['rules.sqlite']

