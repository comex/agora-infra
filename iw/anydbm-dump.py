import anydbm, sys
db = anydbm.open(sys.argv[1])
if len(sys.argv) > 2:
    for word in sys.argv[2:]:
        print '%r: %r' % (word, db.get(word, None))
else:
    for key, value in db.iteritems():
        print '%r: %r' % (key, value)
