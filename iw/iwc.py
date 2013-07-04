import argparse
import datasource, pystuff, cotc

all_sources = datasource.all_sources()
parser = argparse.ArgumentParser(description='Agora database.')

the_filter = None
def url_filter(filter):
    the_filter = filter
parser.add_argument('--url-filter', action=pystuff.action(url_filter, nargs=1))

def add_options_for_source(source):
    if hasattr(source, 'download'):
        parser.add_argument('--download-' + source.name, action=pystuff.action(lambda: source.download(not args.quiet, the_filter)))
    parser.add_argument('--cache-' + source.name, action=pystuff.action(lambda: source.cache(not args.quiet)))

map(add_options_for_source, all_sources)

parser.add_argument('--download-all', '-d', action=pystuff.action(lambda: [source.download(not args.quiet, the_filter) for source in all_sources]))
parser.add_argument('--cache', '-c', action=pystuff.action(lambda: [source.cache(not args.quiet) for source in all_sources]))

parser.add_argument('--cfj-rematch', action=pystuff.action(lambda: cotc.CFJDB().rematch()))

parser.add_argument('--quiet', '-q', action='store_true', dest='quiet')

args = parser.parse_args()
pystuff.run_actions(args)
