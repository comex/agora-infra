from pystuff import shelf
import sys
db = shelf(sys.argv[1], 'r')
if len(sys.argv) > 2:
    if len(sys.argv) == 3 and sys.argv[2] == '--keys':
        for key in sorted(db.iterkeys()):
            print repr(key)
    else:
        for word in sys.argv[2:]:
            print '%r: %r' % (word, db.get(word, None))
else:
    for key, value in db.iteritems():
        print '%r: %r' % (key, value)
