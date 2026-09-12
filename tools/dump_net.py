import re
import sys

text = open(sys.argv[1], encoding='utf-8').read()
pat = sys.argv[2]
for m in re.finditer(r'\(net\s+\(code "\d+"\)\s+\(name "([^"]+)"\)', text):
    if pat not in m.group(1):
        continue
    j = m.start()
    d = 0
    while True:
        c = text[j]
        if c == '(':
            d += 1
        elif c == ')':
            d -= 1
            if d == 0:
                break
        j += 1
    block = text[m.start():j + 1]
    nodes = re.findall(r'\(ref "([^"]+)"\)\s+\(pin "([^"]+)"\)', block)
    pins = sorted(set(r + '.' + p for r, p in nodes if not r.startswith('#')))
    print(m.group(1), f'({len(pins)} pins):', pins)
