import cPickle as pickle
from cStringIO import StringIO
import array, zlib, sys
import dateutil.parser
from datasource import Datasource, DSLookupError, BaseDB
from pystuff import remove_if_present, Singleton
import rcs, pystuff

class FLRDB(BaseDB):
    path = 'flr_revs.pickle'
    def __init__(self, create=False):
        self.load_pickle()

    def load_pickle(self):
        data = pickle.load(open(self.full_path(), 'rb'))
        self.revs = {}
        revs_list = []
        for rev in data['revs']:
            ar = array.array('I')
            ar.fromstring(rev['text'])
            rev['text'] = ar
            self.revs[rev['num']] = rev
            revs_list.append(rev)
        self.revs_list = revs_list[::-1]
        self.indirect = data['indirect']

    def keys(self):
        return self.revs.keys()

    def get(self, rev):
        try:
            ar = self.revs[rev].copy()
        except KeyError:
            return None
        data = StringIO()
        for off in ar['text']:
            line = self.indirect[off:self.indirect.find('\n', off) + 1]
            data.write(line)
        ar['text'] = data.getvalue()
        return ar

    def get_by_date(self, date):
        try:
            dt = dateutil.parser.parse(date)
        except ValueError:
            raise DSLookupError('bad date: %s' % date)
        for rev in self.revs_list:
            if rev['date'] < dt:
                return self.get(rev['num'])
        raise DSLookupError('date too early: %s' % dt)

class FLRDatasource(Datasource):
    name = 'flr'
    urls = [('https://www.eecs.berkeley.edu/~charles/agora/current_flr.txt_comma_v', 'current_flr.txt,v')]
    DB = FLRDB

    def cache(cls, verbose):
        indirect = StringIO()
        revs = rcs.RCSFile(open(cls.urls[0][1]).read()).get_revisions(indirect)
        for rev in revs:
            ar = array.array('I')
            ar.fromlist(rev['text'])
            rev['text'] = ar.tostring()
        data = {'revs': revs, 'indirect': indirect.getvalue()}
        pickle.dump(data, open(FLRDB.full_path(), 'wb'), -1)

    def cli_show_date(self, date):
        try:
            result = self.DB.instance().get_by_date(date)
        except DSLookupError as e:
            print '(%s)' % e
        else:
            print result['text']

    def add_cli_options(self, parser, argsf):
        Datasource.add_cli_options(self, parser, argsf)
        parser.add_argument('--flr-date', action=pystuff.action(lambda date: self.cli_show_date(date), nargs=1), help='show FLR by date')

if __name__ == '__main__':
    for i in xrange(100):
        x = FLRDB().get('1.1100')
    sys.stdout.write(x)

class RulesDatasource(Datasource):
    name = 'rules'
    cachefiles = ['rules.sqlite']
    def download(cls, verbose=False):
        return FLRDatasource().download(verbose)

