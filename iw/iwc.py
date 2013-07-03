import argparse
import datasource, pystuff

all_sources = datasource.all_sources()
parser = argparse.ArgumentParser(description='Agora database.')

def add_options_for_source(source):
    parser.add_argument('--download-' + source.name, **pystuff.action(lambda: source.download(not args.quiet)))
    parser.add_argument('--cache-' + source.name, **pystuff.action(lambda: source.cache()))

map(add_options_for_source, all_sources)

parser.add_argument('--download-all', '-d', **pystuff.action(lambda: [source.download(not args.quiet) for source in all_sources]))
parser.add_argument('--cache', '-c', **pystuff.action(lambda: [source.cache() for source in all_sources]))
parser.add_argument('--quiet', '-q', action='store_true', dest='quiet')

args = parser.parse_args()
pystuff.run_actions(args)
