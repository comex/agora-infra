import sys, subprocess, re, email.utils, datetime, stuff, yaml
kind, who, excerpt = sys.argv[1:]
assert kind in (
    'called',
    'assigned',
    'recused',
    'judged',
    'argued',
    'reconsider?',
    'reconsider!',
    'moot?',
    'moot!',
)
results = subprocess.check_output(['python', 'iw/iwc.py', '--search-messages', '"%s"' % excerpt]).rstrip().split('\n--\n')
ids = []
for result in results:
    ids.append(re.match('id: (.*)', result).group(1))
    print '[%d]' % len(ids)
    print result
    print '--'
while True:
    try:
        num = int(raw_input())
    except ValueError:
        continue
    break

id = ids[num - 1]
full = subprocess.check_output(['python', 'iw/iwc.py', '--message', id]).rstrip()
date = re.search('Real-Date: (.*)', full).group(1)
dt = datetime.datetime.fromtimestamp(email.utils.mktime_tz(email.utils.parsedate_tz(date)))

print; print

if kind != 'argued':
    print '    -'
    yd = yaml.dump(dt)
    yd = yd[:yd.find('\n')]
    print '        date: %s' % yd
    print '        type: %s' % kind
    if kind == 'judged':
        print '        judgement: '
    if kind not in ('recused', 'judged'):
        print '        who: %s' % who
    print; print

if kind in ('called', 'judged', 'argued'):
    em = email.message_from_string(full)
    body = ''
    for part in em.walk():
        if part.get_content_type() == 'text/plain':
            body = stuff.faildecode(part.get_payload(decode=True))
            break
    body = body.strip('\n')
    print '    -'
    print '        who: %s' % who
    print '        mid: %s' % em['Message-ID']
    if kind != 'argued':
        print '        date: %s' % yd

    print '        text: |-'
    print '            ' + re.sub(re.compile('\s*$', re.M), '', body.replace('\n', '\n            ').encode('utf-8'))
    print
