#!/usr/bin/env python
import itertools, re, sys
# Since aword.py is completely unreadable and broken, here's a better version.

def is_sorta_bullety(running):
    return not re.match('[a-hj-zA-Z][a-hj-zA-Z]', running)

bullety = re.compile(r'''
    ^ \s* (
        (
            [-\*]+ \s* |
            [\(\[<]* ( i+ | [0-9]+ ) [\.\)\]>]+ |
            [\(\[<]* [a-zA-Z] [\)\]>]+
        )
        \s*
    )+
''', re.X)

def is_bullet_alignment(para_lines, para_indent, indent, verbose=False):
    if indent < para_indent or para_indent == -1:
        # no indented paragraphs in the ruleset (or blank line)
        return False
    last = para_lines[-1]
    if len(last) < indent + 1:
        return False
    running = last[para_indent:indent]
    m = bullety.match(running)
    ret = m and m.group(0) == running
    if not ret and verbose:
        print '! %r' % last, para_indent, indent
    return ret

def guess_true_indent(line, indent):
    m = bullety.match(line[indent:])
    if m:
        indent += len(m.group(0))
    return indent

def is_inline_bullets(input_lines, li, bullet, verbose=False):
    # genericize
    bullet = re.escape(bullet)
    for x in ('[0-9]', '[a-z]', '[A-Z]', 'i+'):
        bullet = re.sub(x, x, bullet)
    # expect it after text
    bullet = r'[a-z]{3}.* ' + bullet
    # just look around for similar stuff
    for direction in (-1, 1):
        for li2 in xrange(li + direction, li + 4 * direction, direction):
            line2 = input_lines[li2]
            if re.match('^\s+$', line2):
                # stop at paragraph breaks
                break
            if re.search(bullet, line2):
                if verbose:
                    print 'inline bullets! < %s / %s >' % (input_lines[li].strip(), line2.strip())
                return True
    return False



def smart_unwrap_para(para_lines):
    # Replace newlines (plus associated spaces) with single spaces, unless
    # preceded by a sentence end, unless the paragraph uses single spaces between
    # sentences elsewhere.
    out = ''
    was_period = False
    x = []
    for i, line in enumerate(para_lines):
        if was_period:
            x.append('<DBLSP>')
        line = line.strip()
        x.append(line)
        was_period = line.endswith('.') and not re.match(' [a-zA-Z]\.$', line)
    result = ' '.join(x)
    double = len(list(re.finditer('\.  [A-Z]', result)))
    single = len(list(re.finditer('\. [A-Z]', result)))
    result = result.replace('<DBLSP>', ' ' if double > single else '')
    return result

def unwrap(input_lines, verbose=False):
    input_lines = list(input_lines)
    input_lines.append('')

    para_lines = None
    para_indent = -1

    in_right_aligned_group = False

    prev_indents = []

    out = []

    for li, line in enumerate(input_lines):
        # cleanup, just in case
        line = line.replace('\t', '    ')
        line = re.sub('\s*$', '', line)

        m = re.match('^ *', line)
        indent = len(m.group(0))

        is_new_para = False

        bm = bullety.match(line[indent:])
        is_new_para = (
            # different indent
            (indent != para_indent and not is_bullet_alignment(para_lines, para_indent, indent, verbose)) or 
            # bullet, but sometimes we see paragraphs with (N) in them
            (bm and not is_inline_bullets(input_lines, li, bm.group(0), verbose))
        )

        if is_new_para:
            # ** new paragraph **
            if para_lines is not None:
                para_text = ' ' * orig_para_indent + smart_unwrap_para(para_lines)
                out.append(para_text)

            para_lines = []

            if para_indent != -1:
                if verbose and len(para_lines) > 1 and (para_indent == orig_para_indent < guessed_para_indent):
                    print 'Misaligned:', para_text
                if in_right_aligned_group and guessed_para_indent != prev_indents[-1]['guessed']:
                    real_align = prev_indents[-1]['guessed']
                    for i in xrange(len(prev_indents) - 1, -1, -1):
                        pi = prev_indents[i]
                        if pi['guessed'] != real_align:
                            break
                        oi = pi['out_idx']
                        bullet_len = pi['guessed'] - pi['orig']
                        out[oi] = ' ' * pi['guessed'] + 'RALIGN{' + out[oi][pi['orig']:pi['guessed']] + '}' + out[oi][pi['guessed']:]
                    in_right_aligned_group = False
                # check for right alignment
                if len(prev_indents) >= 1 and \
                   guessed_para_indent == prev_indents[-1]['guessed'] and \
                   orig_para_indent != prev_indents[-1]['orig'] and \
                   prev_indents[-1]['guessed'] > prev_indents[-1]['orig'] and \
                   guessed_para_indent > orig_para_indent:
                    in_right_aligned_group = True
                    if verbose:
                        print '>>>>', out[-1], '/', out[prev_indents[-1]['out_idx']]
                        print orig_para_indent, prev_indents[-1]
                prev_indents.append({'guessed': guessed_para_indent, 'orig': orig_para_indent, 'out_idx': len(out) - 1, 'line': line})

            # guessed: skipping (a) in "(a) foo",
            # orig: not skipping, and not changing if continuation lines are indented
            guessed_para_indent = guess_true_indent(line, indent)
            orig_para_indent = para_indent = indent
        elif indent != para_indent:
            # bullet alignment
            guessed_para_indent = para_indent = indent

        if line == '':
            para_indent = -1
        else:
            para_lines.append(line)

    return out

print '\n'.join(unwrap(open(sys.argv[1]), False))
