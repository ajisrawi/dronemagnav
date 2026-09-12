import functools, builtins
print = functools.partial(builtins.print, flush=True)
import pcbnew
PCB = r"C:\Users\ahmad\Documents\ATC ROIP\DroneMagNav\hardware\dronemagnav\dronemagnav.kicad_pcb"
board = pcbnew.LoadBoard(PCB)
nets = board.GetNetsByName()
F, B = pcbnew.F_Cu, pcbnew.B_Cu
def MM(v): return pcbnew.FromMM(v)
u1 = board.FindFootprintByReference('U1')
none = board.GetNetInfo().GetNetItem(0)
for pad in u1.Pads():
    n = pad.GetName()
    if n == '37': pad.SetNet(nets['GNSS_RXD'])
    elif n == '36': pad.SetNet(nets['GNSS_TXD'])
    elif n in ('10', '11'): pad.SetNet(none)
print('U1 pads reassigned')
def track(x1, y1, x2, y2, net, layer=F, w=0.2):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pcbnew.VECTOR2I(MM(x1), MM(y1))); t.SetEnd(pcbnew.VECTOR2I(MM(x2), MM(y2)))
    t.SetLayer(layer); t.SetWidth(MM(w)); t.SetNet(nets[net]); board.Add(t)
def via(x, y, net, dia=0.45, drill=0.2):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y))); v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetDrill(MM(drill)); v.SetWidth(MM(dia)); v.SetLayerPair(F, B); v.SetNet(nets[net]); board.Add(v)
# GNSS_RXD: U1.37 (138.75,111.55) -> U5.3 (150.75,109.80); crosses PPS on B.Cu
track(138.75, 111.55, 149.0, 111.55, "GNSS_RXD"); via(149.0, 111.55, "GNSS_RXD")
track(149.0, 111.55, 149.0, 109.8, "GNSS_RXD", B); via(149.0, 109.8, "GNSS_RXD")
track(149.0, 109.8, 150.75, 109.8, "GNSS_RXD")
# GNSS_TXD: U1.36 (138.75,112.82) -> U5.2 (150.75,108.70)
track(138.75, 112.82, 139.9, 112.82, "GNSS_TXD")
track(139.9, 112.82, 140.3, 112.4, "GNSS_TXD")
track(140.3, 112.4, 148.3, 112.4, "GNSS_TXD"); via(148.3, 112.4, "GNSS_TXD")
track(148.3, 112.4, 148.3, 108.7, "GNSS_TXD", B); via(148.3, 108.7, "GNSS_TXD")
track(148.3, 108.7, 150.75, 108.7, "GNSS_TXD")
# I2C_SCL: back into the slot vacated by DBG_RX (x+y = 267.5)
track(136.92, 109.93, 136.92, 130.58, "I2C_SCL", B)
track(136.92, 130.58, 123.59, 143.91, "I2C_SCL", B)
track(123.59, 143.91, 123.11, 143.91, "I2C_SCL", B)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(PCB, board)
print("routes added")