import sys, functools, builtins
print = functools.partial(builtins.print, flush=True)
import pcbnew
PCB = r"C:\Users\ahmad\Documents\ATC ROIP\DroneMagNav\hardware\dronemagnav\dronemagnav.kicad_pcb"
PHASE = sys.argv[1] if len(sys.argv) > 1 else "add"
board = pcbnew.LoadBoard(PCB)
nets = board.GetNetsByName()
F, B = pcbnew.F_Cu, pcbnew.B_Cu
def MM(v): return pcbnew.FromMM(v)
def near(p, x, y, tol=0.03): return abs(pcbnew.ToMM(p.x)-x) < tol and abs(pcbnew.ToMM(p.y)-y) < tol
if PHASE == "remove":
    kill = [("I2C_SCL", (136.92, 109.93), (136.92, 130.10)), ("I2C_SCL", (136.92, 130.10), (123.11, 143.91))]
    n = 0
    for t in list(board.GetTracks()):
        if t.GetNetname() in ("GNSS_TXD", "GNSS_RXD"):
            board.Remove(t); n += 1; continue
        if t.GetClass() != 'PCB_TRACK': continue
        s, e = t.GetStart(), t.GetEnd()
        for net, a, b in kill:
            if t.GetNetname() == net and ((near(s,*a) and near(e,*b)) or (near(s,*b) and near(e,*a))):
                board.Remove(t); n += 1; break
    print("removed:", n)
    pcbnew.SaveBoard(PCB, board); sys.exit(0)
def track(x1, y1, x2, y2, net, layer=F, w=0.2):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pcbnew.VECTOR2I(MM(x1), MM(y1))); t.SetEnd(pcbnew.VECTOR2I(MM(x2), MM(y2)))
    t.SetLayer(layer); t.SetWidth(MM(w)); t.SetNet(nets[net]); board.Add(t)
def via(x, y, net, dia=0.45, drill=0.2):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y))); v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetDrill(MM(drill)); v.SetWidth(MM(dia)); v.SetLayerPair(F, B); v.SetNet(nets[net]); board.Add(v)
# GNSS_TXD (outer loop): U1.11 (121.25,120.44) -> U5.2 (150.75,108.70)
track(121.25, 120.44, 116.0, 120.44, "GNSS_TXD"); via(116.0, 120.44, "GNSS_TXD")
track(116.0, 120.44, 116.0, 106.65, "GNSS_TXD", B)
track(116.0, 106.65, 149.55, 106.65, "GNSS_TXD", B)
track(149.55, 106.65, 149.55, 108.7, "GNSS_TXD", B); via(149.55, 108.7, "GNSS_TXD")
track(149.55, 108.7, 150.75, 108.7, "GNSS_TXD")
# GNSS_RXD (inner loop): U1.10 (121.25,119.17) -> U5.3 (150.75,109.80)
track(121.25, 119.17, 116.4, 119.17, "GNSS_RXD"); via(116.4, 119.17, "GNSS_RXD")
track(116.4, 119.17, 116.4, 107.0, "GNSS_RXD", B)
track(116.4, 107.0, 148.8, 107.0, "GNSS_RXD", B)
track(148.8, 107.0, 148.8, 109.8, "GNSS_RXD", B); via(148.8, 109.8, "GNSS_RXD")
track(148.8, 109.8, 150.75, 109.8, "GNSS_RXD")
# I2C_SCL diagonal moved 1.5 mm toward the module (x+y = 264.9), clear of the
# BMI088 vias-in-pad and the DBG/SDA bundle
track(136.92, 109.93, 136.92, 127.98, "I2C_SCL", B)
track(136.92, 127.98, 120.99, 143.91, "I2C_SCL", B)
track(120.99, 143.91, 123.11, 143.91, "I2C_SCL", B)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(PCB, board)
print("routes added")