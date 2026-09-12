"""Verify key nets of the DroneMagNav netlist."""
import re
import sys

path = sys.argv[1] if len(sys.argv) > 1 else 'netlist.net'
text = open(path, encoding='utf-8').read()

nets = {}
for m in re.finditer(r'\(net\s+\(code "\d+"\)\s+\(name "([^"]+)"\)', text):
    start = m.start()
    depth = 0
    j = start
    while j < len(text):
        c = text[j]
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                break
        j += 1
    block = text[start:j + 1]
    nodes = re.findall(r'\(ref "([^"]+)"\)\s+\(pin "([^"]+)"\)', block)
    nets[m.group(1)] = sorted(f"{r}.{p}" for r, p in nodes
                              if not r.startswith('#'))

checks = {
    "SPI_SCK": {"U1.20", "U2.8", "U3.1", "U4.4"},
    "SPI_MISO": {"U1.21", "U2.15", "U2.10", "U3.9", "U4.5"},
    "SPI_MOSI": {"U1.19", "U2.9", "U3.11", "U4.3"},
    "CS_ACC": {"U1.18", "U2.14"},
    "CS_MAG": {"U1.22", "U3.10"},
    "CS_BARO": {"U1.23", "U4.2"},
    "MAG_DRDY": {"U1.12", "U3.8"},
    "USB_DP": {"U1.14", "U8.6"},
    "USB_DP_RAW": {"J1.A6", "J1.B6", "U8.1"},
    "GNSS_TXD": {"U1.36", "U5.2"},
    "GNSS_RXD": {"U1.37", "U5.3"},
    "FC_TXD": {"U1.5", "J2.2"},
    "FC_RXD": {"U1.4", "J2.3"},
    "SD_CMD": {"U1.32", "J3.3", "R9.2"},
    "SD_CLK": {"U1.31", "J3.5"},
    "EN": {"U1.3", "R2.2", "C7.1", "SW1.1"},
    "I2C_SDA": {"U1.39", "R7.2", "J5.3"},
    "VBUS": {"J1.A4", "D1.2", "U8.5"},
    "5V_FC": {"J2.1", "D2.2"},
    "MAG_C1": {"U3.4", "C12.1"},
    "GNSS_RF": {"U5.11", "J4.1"},
}
ok = True
for net, want in checks.items():
    found = None
    for k, v in nets.items():
        if k == net or k.endswith('/' + net):
            found = (k, set(v))
            break
    if not found:
        print(f"FAIL {net}: net not found")
        ok = False
        continue
    k, have = found
    if want <= have:
        print(f"OK   {net}: {sorted(have)}")
    else:
        print(f"FAIL {net}: want {sorted(want)}, have {sorted(have)}")
        ok = False
for rail in ("+3V3", "+3.3VA", "+5V", "GND"):
    for k, v in nets.items():
        if k == rail:
            print(f"rail {rail}: {len(v)} pins")
print("total nets:", len(nets))
sys.exit(0 if ok else 1)

