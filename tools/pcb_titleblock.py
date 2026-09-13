"""Set the PCB title block and tidy the U1 fab-layer reference text.

Run with KiCad's Python:
  & "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" tools/pcb_titleblock.py

The stock ESP32-S3-WROOM-1 footprint carries a second ${REFERENCE} text on
F.Fab placed relative to its (very large) antenna keep-out, which lands far
outside the board on the assembly drawing. It is moved next to the module.
"""
import datetime
import os

import pcbnew

HW = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "hardware", "dronemagnav")
PCB = os.path.join(HW, "dronemagnav.kicad_pcb")

board = pcbnew.LoadBoard(PCB)
tb = board.GetTitleBlock()
tb.SetTitle("DroneMagNav - magnetic anomaly navigation board")
tb.SetCompany("DroneMagNav Project")
tb.SetRevision("A")
tb.SetDate(datetime.date.today().isoformat())
tb.SetComment(0, "Top assembly drawing: F.Fab + F.Silkscreen + Edge.Cuts, all parts top side")
board.SetTitleBlock(tb)

u1 = board.FindFootprintByReference("U1")
moved = 0
if u1:
    pos = u1.GetPosition()
    for item in u1.GraphicalItems():
        if item.GetClass() in ("PCB_TEXT", "PCB_FIELD") and hasattr(item, "GetText") \
                and item.GetLayer() == pcbnew.F_Fab and "REFERENCE" in item.GetText():
            item.SetPosition(pcbnew.VECTOR2I(pos.x, pos.y + pcbnew.FromMM(11)))
            moved += 1
    # the silkscreen reference is auto-placed above the huge bounding box too
    # (off the board); park it under the module body where the fab drawing
    # still shows it and the gerbers stay clean
    u1.Reference().SetPosition(pcbnew.VECTOR2I(pos.x, pos.y))
    moved += 1
print("moved U1 reference texts:", moved)
pcbnew.SaveBoard(PCB, board)
print("saved title block")
