# TRANSFOOOORM!
import re, aword
f = open('current_flr.txt', 'r')
flr = f.read()
f.close()
SPL = '\n----------------------------------------------------------------------\n'
flrs = flr.split(SPL)

def mmax(things):
	return 0 if len(things) == 0 else max(things)

assns = {
	'Rules': [105, 1688, 2140, 693, 107, 683, 208, 955, 106, 1607, 2137],
	'Administration': [1006, 2143, 2160, 2154, 2217, 2138],
	'Judiciary': [991, 2158, 1868, 591, 2157, 911],
	'Crime': [2230, 1504, 2228, 2229],
	'Finance': [2166, 2181, 2126, 2199],
	'Entrepreneurship': [1742, 2173, 2197, 2198, 2178, 2191, 2145, 2169],
	'Indian Affairs': [2179, 2136, 2232, 2233, 2187],
	'Foreign Relations': [2200, 2148, 2185, 2147, 2159, 2206, 2207]
}
ls = sum(assns.values(), [])
assert sorted(ls) == sorted(list(set(ls)))
def fullname(name):
	if name == 'Judiciary':
		return 'Committee on the Judiciary'
	if name == 'Entrepreneurship':
		return 'Committee on Small Business and Entrepreneurship'
	return 'Committee on %s' % name

for k, v in enumerate(flrs):
	if 'January 2009' in v or 'February 2009' in v:
		pass #continue
	m = re.search('^\n*Rule ([0-9]+)/[0-9]+ \(Power=[0-9\.]+\)', v)
	if m:
		ruleno = int(m.group(1))
		print repr(v)
		committees = [i for i in assns if ruleno in assns[i]]
		assert len(committees) <= 1
		if len(committees) == 1:
			ls.remove(ruleno)
			n = len(m.group(0))
			print ruleno
			#amendmentno = 1 + mmax([int(i) for i in re.findall('\(([0-9]+)\)', v[v.find('History:'):])])
			amen = aword.awrap('Assigned to %s by Proposal 6053 (Murphy, woggle, ais523), 23 January 2009\n' % (fullname(committees[0])), 0).replace('\n', '\n  ')
			v2 = v[:n] + (' [%s]' % ', '.join(committees)) + v[n:] + amen
			#v2 = re.sub('\/[0-9]+( \(Power=[^\)]+\))', '/' + str(amendmentno) + '\\1', v2)
			flrs[k] = v2
#print ls
newflr = re.sub(re.compile(' +$', re.M), '', SPL.join(flrs))
print newflr
