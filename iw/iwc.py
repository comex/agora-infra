import argparse
import datasource, pystuff

all_sources = datasource.all_sources()
parser = argparse.ArgumentParser(description='Agora database.')

the_filter = None
def url_filter(filter):
    the_filter = filter
parser.add_argument('--url-filter', action=pystuff.action(url_filter, nargs=1))

for source in all_sources:
    source.add_cli_options(parser, lambda: args)

parser.add_argument('--download', '-d', action=pystuff.action(lambda: [s.cli_download(args) for s in sources]))
parser.add_argument('--cache', '-c', action=pystuff.action(lambda: [s.cli_cache(args) for s in sources]))
parser.add_argument('--update', '-u', action=pystuff.action(lambda: [s.cli_update(args) for s in sources]))

parser.add_argument('--quiet', '-q', action='store_true', dest='quiet')

args = parser.parse_args()
pystuff.run_actions(args)
