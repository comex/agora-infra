from datasource import Datasource
from flr import FLRDatasource

class RulesDatasource(Datasource):
    def download(cls, verbose=False):
        return FLRDatasource.download(verbose)
