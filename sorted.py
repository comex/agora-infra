# TRANSFOOOORM!
import re, aword
f = open('current_slr.txt', 'r')
flr = f.read()
f.close()
SPL = '\n----------------------------------------------------------------------\n'
flrs = flr.split(SPL)

powers = {}

for k, v in enumerate(flrs):
	if 'January 2009' in v or 'February 2009' in v:
		pass #continue
	m = re.search('^\n*Rule ([0-9]+)/[0-9]+ \(Power=([0-9\.]+)\)', v)
	if m:
		powers.setdefault(float(m.group(2)), {})[int(m.group(1))] = v
print SPL
for pwr in sorted(powers.keys(), reverse=True):
    for rule, txt in powers[pwr].items():
        print txt.strip()
        print SPL
