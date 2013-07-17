import argparse
import datasource, pystuff, cotc

all_sources = datasource.all_sources()
parser = argparse.ArgumentParser(description='Agora database.')

the_filter = None
def url_filter(filter):
    the_filter = filter
parser.add_argument('--url-filter', action=pystuff.action(url_filter, nargs=1))

def download(source):
    source.download(not args.quiet, the_filter)
def cache(source):
    source.cache(not args.quiet)
def update(source):
    download(source)
    cache(source)

def add_default_source_options(source):
    if hasattr(source, 'download'):
        parser.add_argument('--download-' + source.name, action=pystuff.action(lambda: download(source)))
    parser.add_argument('--cache-' + source.name, action=pystuff.action(lambda: cache(source)))
    # download and cache
    parser.add_argument('--update-' + source.name, action=pystuff.action(lambda: update(source)))

for source in all_sources:
    # this must be a function
    add_default_source_options(source)
    source.add_cli_options(parser)

parser.add_argument('--download', '-d', action=pystuff.action(lambda: map(download, sources)))
parser.add_argument('--cache', '-c', action=pystuff.action(lambda: map(cache, sources)))
parser.add_argument('--update', '-u', action=pystuff.action(lambda: map(update, sources)))

parser.add_argument('--cfj-rematch', action=pystuff.action(lambda: cotc.CFJDB().rematch()))

parser.add_argument('--quiet', '-q', action='store_true', dest='quiet')

args = parser.parse_args()
pystuff.run_actions(args)
