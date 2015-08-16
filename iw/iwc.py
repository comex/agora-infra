import argparse
import datasource, pystuff

all_dbs = datasource.all_dbs()
parser = argparse.ArgumentParser(description='Agora database.')

the_filter = None
def url_filter(filter):
    the_filter = filter
parser.add_argument('--url-filter', action=pystuff.action(url_filter, nargs=1))

for db in all_dbs:
    db.add_cli_options(parser, lambda: args)

parser.add_argument('--color', '-C', action='store_true')
parser.add_argument('--full', '-f', action='store_true')


parser.add_argument('--update', '-u', action=pystuff.action(lambda: [db.cli_update(args) for db in all_dbs]), help='update everything')

parser.add_argument('--quiet', '-q', action='store_true')
parser.add_argument('--log-queries', action='store_true')
parser.add_argument('--force-unindexed', action='store_true')
parser.add_argument('--print-trigram-hits', action='store_true')
parser.add_argument('--limit', action='store', dest='limit', help='limit for searches, or 0', type=int, default=10)
parser.add_argument('--timeout', action='store', dest='timeout', help='timeout for searches', type=float)

args = parser.parse_args()
for dbgopt in ('log_queries', 'force_unindexed', 'print_trigram_hits'):
    setattr(pystuff, dbgopt, getattr(args, dbgopt))

try:
    pystuff.run_actions(args)
finally:
    for db in all_dbs:
        if db.dirty:
            db.finalize(not args.quiet)
