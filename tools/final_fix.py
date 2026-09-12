import functools, builtins
print = functools.partial(builtins.print, flush=True)
import pcbnew
PCB = r"C:\Users\ahmad\Documents\ATC ROIP\DroneMagNav\hardware\dronemagnav\dronemagnav.kicad_pcb"
board = pcbnew.LoadBoard(PCB)
nets = board.GetNetsByName()
F, B = pcbnew.F_Cu, pcbnew.B_Cu
def MM(v): return pcbnew.FromMM(v)
def track(x1, y1, x2, y2, net, layer=F, w=0.2):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pcbnew.VECTOR2I(MM(x1), MM(y1))); t.SetEnd(pcbnew.VECTOR2I(MM(x2), MM(y2)))
    t.SetLayer(layer); t.SetWidth(MM(w)); t.SetNet(nets[net]); board.Add(t)
def via(x, y, net, dia=0.45, drill=0.2):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y))); v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetDrill(MM(drill)); v.SetWidth(MM(dia)); v.SetLayerPair(F, B); v.SetNet(nets[net]); board.Add(v)

# --- GNSS_TXD: U1 pad11 (121.25,120.44) -> U5 pad2 (150.75,108.70) ---------
track(121.25, 120.44, 119.5, 120.44, "GNSS_TXD")
via(119.5, 120.44, "GNSS_TXD")
track(119.5, 120.44, 119.5, 126.9, "GNSS_TXD", B)
track(119.5, 126.9, 148.6, 126.9, "GNSS_TXD", B)
track(148.6, 126.9, 148.6, 108.7, "GNSS_TXD", B)
via(148.6, 108.7, "GNSS_TXD")
track(148.6, 108.7, 150.75, 108.7, "GNSS_TXD")
# --- GNSS_RXD: U1 pad10 (121.25,119.17) -> U5 pad3 (150.75,109.80) ---------
track(121.25, 119.17, 118.7, 119.17, "GNSS_RXD")
via(118.7, 119.17, "GNSS_RXD")
track(118.7, 119.17, 118.7, 127.3, "GNSS_RXD", B)
track(118.7, 127.3, 148.2, 127.3, "GNSS_RXD", B)
track(148.2, 127.3, 148.2, 109.8, "GNSS_RXD", B)
via(148.2, 109.8, "GNSS_RXD")
track(148.2, 109.8, 150.75, 109.8, "GNSS_RXD")
# --- U2 GND pads 2,4 -> comb above the top row joining pad 6's stub ---------
for x in (129.0, 130.0, 131.0):
    track(x, 136.7375, x, 136.05, "GND")
track(129.0, 136.05, 131.0, 136.05, "GND")
# --- U4 pad 7 (139.675,137.8) -> outward then down to the GND track end -----
track(139.675, 137.8, 140.5, 137.8, "GND")
track(140.5, 137.8, 140.5, 139.45, "GND")
track(140.5, 139.45, 140.0, 139.45, "GND")

pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(PCB, board)
print("manual routes added")