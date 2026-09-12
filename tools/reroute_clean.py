"""Strip all routing, export DSN with In1/In2 marked as power layers."""
import re

import pcbnew

HW = r"C:\Users\ahmad\Documents\ATC ROIP\DroneMagNav\hardware\dronemagnav"
PCB = HW + r"\dronemagnav.kicad_pcb"
DSN = HW + r"\dronemagnav-clean.dsn"

board = pcbnew.LoadBoard(PCB)
tracks = list(board.GetTracks())
for t in tracks:
    board.Remove(t)
print("removed", len(tracks), "tracks/vias")
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(PCB, board)

ok = pcbnew.ExportSpecctraDSN(board, DSN)
print("DSN export:", ok)

text = open(DSN, encoding="utf-8").read()
# mark the inner plane layers as power so the router keeps signals off them
for lname in ("In1.Cu", "In2.Cu"):
    pat = r'(\(layer\s+' + re.escape(lname) + r'\s*\(type)\s+signal\)'
    text, n = re.subn(pat, r'\1 power)', text)
    print(lname, "-> power:", n)
open(DSN, "w", encoding="utf-8").write(text)

