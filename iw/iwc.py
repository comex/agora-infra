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

parser.add_argument('--color', '-C', action='store_true')
parser.add_argument('--full', '-f', action='store_true')


parser.add_argument('--download', '-d', action=pystuff.action(lambda: [s.cli_download(args) for s in al_sources]), help='download everything')
parser.add_argument('--cache', '-c', action=pystuff.action(lambda: [s.cli_cache(args) for s in all_sources]), help='cache everything')
parser.add_argument('--update', '-u', action=pystuff.action(lambda: [s.cli_update(args) for s in all_sources]), help='update everything')

parser.add_argument('--quiet', '-q', action='store_true')
parser.add_argument('--log-queries', action='store_true')
parser.add_argument('--force-unindexed', action='store_true')
parser.add_argument('--print-trigram-hits', action='store_true')
parser.add_argument('--limit', action='store', dest='limit', help='limit for searches, or 0', type=int, default=10)

args = parser.parse_args()
for dbgopt in ('log_queries', 'force_unindexed', 'print_trigram_hits'):
    setattr(pystuff, dbgopt, getattr(args, dbgopt))
pystuff.run_actions(args)
