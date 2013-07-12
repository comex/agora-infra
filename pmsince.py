import sys, os, mmap, time, re
from email.utils import parsedate_tz, mktime_tz
from dateutil.parser import parse
arcdir, since = sys.argv[1:]
since = parse(since)
since = time.mktime(since.timetuple())
for path in ['agora-official.mbox', 'agora-business.mbox']:
    path = os.path.join(arcdir, path)
    if not os.path.exists(path): continue
    fp = open(path, 'rb')
    mm = mmap.mmap(fp.fileno(), 0, access=mmap.ACCESS_READ)
    z = len(mm)
    msgs = []
    while True:
        nz = mm.rfind('\n\nFrom ', 0, z)
        if nz == -1:
            break
        msg = buffer(mm, nz + 2, z - nz)
        date = re.search('; (.*:.*)\n', msg).group(1)
        ts = mktime_tz(parsedate_tz(date))
        if ts < since: break
        msgs.append((ts, msg))
        z = nz - 1
    first = True
    for ts, msg in sorted(msgs):
        if not first: print '--'
        print str(msg).replace('\n--\n', '\n>--\n')
        first = False
        sys.stdout.flush()
