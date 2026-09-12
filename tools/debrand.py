"""Replace the leftover 'ATC RoIP' title-block branding in the generated
schematic sheets and netlist with DroneMagNav's own. Idempotent."""
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HW = os.path.join(ROOT, "hardware", "dronemagnav")

SUBS = [('(company "ATC RoIP Gateway Project")', '(company "DroneMagNav Project")'),
        ('(generator "atc_roip_gen")', '(generator "dronemagnav_gen")'),
        ('generator "atc_roip_gen"', 'generator "dronemagnav_gen"'),
        # netlist records the absolute export path; keep it project-relative
        ('"C:\\\\Users\\\\ahmad\\\\Documents\\\\ATC ROIP\\\\DroneMagNav\\\\hardware'
         '\\\\dronemagnav\\\\dronemagnav.kicad_sch"',
         '"hardware/dronemagnav/dronemagnav.kicad_sch"')]

files = [f for f in os.listdir(HW) if f.endswith(".kicad_sch")] + ["netlist.net"]
for name in files:
    path = os.path.join(HW, name)
    if not os.path.exists(path):
        continue
    s = io.open(path, encoding="utf-8").read()
    orig = s
    for old, new in SUBS:
        s = s.replace(old, new)
    if s != orig:
        io.open(path, "w", encoding="utf-8", newline="\n").write(s)
        print("patched", name)
    else:
        print("clean  ", name)
