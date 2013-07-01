#!/usr/bin/env python
import re, sys, os
def wrap(text, width):
    """
    A word-wrap function that preserves existing line breaks
    and most spaces in the text. Expects that existing line
    breaks are posix newlines (\n).
    """
    return reduce(lambda line, word, width=width: '%s%s%s' %
                  (line,
                   ' \n'[(len(line)-line.rfind('\n')-1
                         + len(word.split('\n',1)[0]
                              ) >= width)],
                   word),
                  text.split(' ')
                 )        

forward_regexp = '(-|\*|\(?\s*([\+\-]?[a-zA-Z0-9\.]{,2}|[i\.]+)\s*\)|\*.*- )'
backward_regexp = '[ivx0-9]+\.'
def final_strip(stuff):
    return re.sub(re.compile('[ \t]+$', re.M), '', stuff)
def fix(data, temp):
    if len(temp) > 0:
        if temp[0][3] == 'fwd':
            maxpl = max([len(i[2]) for i in temp])
            for i in temp: i[1] += maxpl
        data += temp
def awrap(text, start=6, width=70):
    if len(text) > 0 and text[-1] == '\n': text = text[:-1]
    text = text.replace('\t', ' ' * 4)
    data = []
    temp = []
    for line in text.split('\n'):
        my_start = start
        ls = re.split('^(\s*)', line)
        my_start += len(re.split('[^\s]', line)[0])
        line = line.lstrip()
        m = re.match('^%s\s*' % backward_regexp, line)
        if m:
            prefix = m.group(0)
            prefix_type = 'bwd'
        else:
            m = re.match('^%s\s+' % forward_regexp, line)
            if m:
                prefix = m.group(0)
                prefix_type = 'fwd'
            else:
                prefix = ''
                prefix_type = None
        if (len(temp) == 0 and len(data) == 0) or (my_start == temp[-1][1] and prefix_type == temp[-1][3]):
            temp.append([line, my_start, prefix, prefix_type])
        else:
            fix(data, temp)
            temp = [[line, my_start, prefix, prefix_type]]
    fix(data, temp)
    ret = []
    for line, my_start, prefix, prefix_type in data:
        out = ' ' * (my_start - len(prefix)) + prefix + wrap(line[len(prefix):], width - my_start).replace('\n', '\n' + ' ' * my_start)
        ret.append(out)
    return final_strip('\n'.join(ret))
def aunwrap_helper(m):
    l = len(m.group(0))
    a = ''
    while l > 4:
        l -= 4
        a += '\t'
    a += ' ' * l
    return a
def aunwrap(text, start=6, _=None):
    text = text.replace('\xa0', ' ')
    text = text.replace('\t', ' ' * 4)
    
    lines = text.split('\n')
    temp = ''
    last_leading_spaces = -1
    last_leading_spaces_ft = None
    ret = ''
    for line in lines:
        leading_spaces = len(re.split('[^\s]', line)[0])
        #print '%d <%s>' % (leading_spaces, repr(line))
        leading_spaces_ft = leading_spaces
        line = line.lstrip()
        m = re.match('^%s\s*' % backward_regexp, line)
        if m:
            leading_spaces += len(m.group(0))
            leading_spaces_ft += len(m.group(0))
        else:
            m = re.match('^%s\s*' % forward_regexp, line)
            if m:
                leading_spaces += len(m.group(0))
                
        
        #print '%s: %s / %s ; %s / %s' % tuple(map(repr, (line, leading_spaces, last_leading_spaces, leading_spaces_ft, last_leading_spaces_ft)))
        if leading_spaces == last_leading_spaces and not m:
            if len(temp) == 0 or len(line) == 0 or re.match('\s', temp[-1]) or re.match('\s', line[0]):
                temp += line
            elif temp[-1] == '.':
                temp += '  ' + line
            else:
                temp += ' ' + line
        else:
            if last_leading_spaces_ft is not None:
                #print '<%s: %d>' % (repr(temp), last_leading_spaces_ft)
                ret += (' ' * (last_leading_spaces_ft - start)) + temp + '\n'
            else:
                ret += temp + '\n'
            temp = line
            last_leading_spaces_ft = leading_spaces_ft
        last_leading_spaces = leading_spaces
    ret += re.sub('^ +', aunwrap_helper, temp)
    # Note: ret starts with an extra \n
    ret = final_strip(ret.lstrip('\n')).lstrip('\n').rstrip() # final_strip(ret.
    # dual rstrip probably not necessary
    # but kate adds lots of newlines
    return ret
def amerge(text, start=6, width=70):
    text = aunwrap(text, start, width)
    text = re.sub(re.compile('^\s+', re.M), '', text).replace('\n', '  ').strip()
    return awrap(text, start, width)
def usage():
    print '''
Run me as awrap / aunwrap, or call as:
   %s --awrap
   %s --aunwrap
'''.strip() % (sys.argv[0], sys.argv[0])
    sys.exit(0)  
if __name__ == '__main__':
    tools = {'awrap': awrap, 'aunwrap': aunwrap, 'amerge': amerge}
    tool = (tools.get(os.path.basename(sys.argv[0]).lower())) or \
           (len(sys.argv) > 1 and sys.argv[1][:2] == '--' and tools.get(sys.argv.pop(1)[2:]))
    if not tool: usage()
    sys.argv.pop(0)
    files = []
    start = 6
    width = 70
    while sys.argv:
        arg = sys.argv.pop(0)
        if arg == '-s':
            start = int(sys.argv.pop(0))
        elif arg == '-w':
            width = int(sys.argv.pop(0))
        else:
            files.append(arg)
    if not files: files.append(sys.stdin)
    for file in files:
        if isinstance(file, basestring): file = open(file)
        print tool(file.read(), start, width)
        file.close()
            
