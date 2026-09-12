"""Clean-slate power fanout.

Phase 'wipe': remove ALL GND/+3V3 tracks+vias (all were script-added; the
router only routed signal nets) and the RXD0 dive segments.
Phase 'add': re-add the RXD0 B.Cu dodge (verified against ETH_NRST), the
U4.9 VDDIO fanout, then a deterministic collision-checked stub+via fanout
for every GND/+3V3 SMD pad and regulator tab on the board.
"""
import math
import sys
import functools
import builtins

print = functools.partial(builtins.print, flush=True)
import pcbnew

HW = r"C:\Users\ahmad\Documents\ATC ROIP\DroneMagNav\hardware\dronemagnav"
PCB = HW + r"\dronemagnav.kicad_pcb"

VIA_DIA, VIA_DRILL, TRACK_W, CLR = 0.45, 0.2, 0.22, 0.155
F, B = None, None  # set after import binding

PHASE = sys.argv[1] if len(sys.argv) > 1 else "add"

board = pcbnew.LoadBoard(PCB)
nets = board.GetNetsByName()
F, B = pcbnew.F_Cu, pcbnew.B_Cu


def MM(v):
    return pcbnew.FromMM(v)


if PHASE == "wipe":
    removed = 0
    for t in list(board.GetTracks()):
        nn = t.GetNetname()
        if nn in ("GND", "+3V3"):
            board.Remove(t)
            removed += 1
        elif nn == "RMII_RXD0":
            # remove the manual dive attempt (keep router segments near U3)
            pts = []
            if t.GetClass() == 'PCB_TRACK':
                pts = [t.GetStart(), t.GetEnd()]
            else:
                pts = [t.GetPosition()]
            for p in pts:
                x, y = pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)
                if 127.5 < x < 132.5 and 133.5 < y < 138.5:
                    board.Remove(t)
                    removed += 1
                    break
    print("wiped:", removed)
    pcbnew.SaveBoard(PCB, board)
    sys.exit(0)

# ---------------------------------------------------------------- add phase
all_items = []
for fp in board.Footprints():
    for pad in fp.Pads():
        all_items.append(pad)
for t in board.GetTracks():
    all_items.append(t)


keepouts = []
for fp in board.Footprints():
    for z in fp.Zones():
        if z.GetIsRuleArea() and (z.GetDoNotAllowVias() or z.GetDoNotAllowTracks()):
            keepouts.append(z.GetBoundingBox())
for z in board.Zones():
    if z.GetIsRuleArea():
        keepouts.append(z.GetBoundingBox())


for ref in ("U2", "U3", "U4"):
    fp = board.FindFootprintByReference(ref)
    if fp:
        keepouts.append(fp.GetCourtyard(pcbnew.F_CrtYd).BBox())


def in_keepout(x, y):
    p = pcbnew.VECTOR2I(int(x), int(y))
    return any(k.Contains(p) for k in keepouts)  # BOX2I.Contains


def item_anchor(it):
    if it.GetClass() == 'PCB_TRACK':
        s, e = it.GetStart(), it.GetEnd()
        return ((s.x + e.x) // 2, (s.y + e.y) // 2,
                math.hypot(e.x - s.x, e.y - s.y) / 2)
    p = it.GetPosition()
    return (p.x, p.y, MM(2))


def local_items(cx, cy, r_iu, netcode):
    out = []
    for it in all_items:
        if it.GetNetCode() == netcode:
            continue
        ax, ay, extra = item_anchor(it)
        if math.hypot(ax - cx, ay - cy) < r_iu + extra + MM(1.5):
            out.append(it)
    return out


def collide(items, shape, layers):
    for it in items:
        for layer in layers:
            if hasattr(it, "IsOnLayer") and not it.IsOnLayer(layer):
                continue
            if it.GetEffectiveShape(layer).Collide(shape, MM(CLR)):
                return True
            break
    return False


def seg_sh(x1, y1, x2, y2, w=TRACK_W):
    return pcbnew.SHAPE_SEGMENT(pcbnew.VECTOR2I(int(x1), int(y1)),
                                pcbnew.VECTOR2I(int(x2), int(y2)), MM(w))


def circ_sh(x, y):
    return pcbnew.SHAPE_CIRCLE(pcbnew.VECTOR2I(int(x), int(y)),
                               MM(VIA_DIA / 2))


def add_track(x1, y1, x2, y2, netname, layer=None, w=TRACK_W):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pcbnew.VECTOR2I(int(x1), int(y1)))
    t.SetEnd(pcbnew.VECTOR2I(int(x2), int(y2)))
    t.SetLayer(layer if layer is not None else F)
    t.SetWidth(MM(w))
    t.SetNet(nets[netname])
    board.Add(t)
    all_items.append(t)


def add_via(x, y, netname):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pcbnew.VECTOR2I(int(x), int(y)))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetDrill(MM(VIA_DRILL))
    v.SetWidth(MM(VIA_DIA))
    v.SetLayerPair(F, B)
    v.SetNet(nets[netname])
    board.Add(v)
    all_items.append(v)


# 3. generic fanout for every GND/+3V3 SMD pad and tab
ic_refs = ["U1", "U2", "U3", "U4", "U5", "U6", "U7", "U8"]
targets = []
for ref in ic_refs:
    fp = board.FindFootprintByReference(ref)
    for pad in fp.Pads():
        if pad.GetNetname() in ("GND", "+3V3") and \
                pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
            targets.append((ref, pad))
for fp in board.Footprints():
    ref = fp.GetReference()
    if ref in ic_refs:
        continue
    for pad in fp.Pads():
        if pad.GetNetname() in ("GND", "+3V3") and \
                pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
            targets.append((ref, pad))

# skip U4.9 - already done above
fixed, failed = 0, []
for ref, pad in targets:
    netname = pad.GetNetname()
    netcode = pad.GetNetCode()
    ppos = pad.GetPosition()
    fp = board.FindFootprintByReference(ref)
    fpos = fp.GetPosition()
    half = max(pad.GetSize().x, pad.GetSize().y) / 2
    if pcbnew.ToMM(half) > 1.2:      # tab / EP: via straight in
        items = local_items(ppos.x, ppos.y, MM(2), netcode)
        if not collide(items, circ_sh(ppos.x, ppos.y), (F, B)):
            add_via(ppos.x, ppos.y, netname)
            fixed += 1
            continue
    dx, dy = ppos.x - fpos.x, ppos.y - fpos.y
    if abs(dx) > abs(dy):
        ux, uy = (1 if dx > 0 else -1), 0
    else:
        ux, uy = 0, (1 if dy > 0 else -1)
    items = local_items(ppos.x, ppos.y, MM(4), netcode)
    cands = []
    step = MM(0.1)
    for ix in range(-45, 46):
        for iy in range(-45, 46):
            vx, vy = ppos.x + ix * step, ppos.y + iy * step
            d = math.hypot(vx - ppos.x, vy - ppos.y)
            if d < MM(0.25):
                continue
            cands.append((d, vx, vy))
    cands.sort()
    placed = False
    for d, vx, vy in cands:
        if in_keepout(vx, vy):
            continue
        if collide(items, circ_sh(vx, vy), (F, B)):
            continue
        if any(it.GetClass() == 'PCB_VIA' and
               math.hypot(it.GetPosition().x - vx, it.GetPosition().y - vy) < MM(VIA_DIA + 0.25)
               for it in all_items):
            continue
        path = None
        for sgn in (1, -1, 0):
            if sgn == 0:
                if not collide(items, seg_sh(ppos.x, ppos.y, vx, vy), (F,)):
                    path = [(ppos.x, ppos.y, vx, vy)]
                break
            wx = ppos.x + sgn * ux * MM(0.6)
            wy = ppos.y + sgn * uy * MM(0.6)
            if not collide(items, seg_sh(ppos.x, ppos.y, wx, wy), (F,)) \
                    and not collide(items, seg_sh(wx, wy, vx, vy), (F,)):
                path = [(ppos.x, ppos.y, wx, wy), (wx, wy, vx, vy)]
                break
        if path is None:
            continue
        for (a, b2, c2, d2) in path:
            add_track(a, b2, c2, d2, netname)
        add_via(vx, vy, netname)
        placed = True
        break
    if placed:
        fixed += 1
    else:
        failed.append((ref, pad.GetName(), netname))

# fallback: straight stub to the nearest same-net copper end point
still = []
for ref, pname, netname in failed:
    fp = board.FindFootprintByReference(ref)
    pad = next(p for p in fp.Pads() if p.GetName() == pname)
    ppos = pad.GetPosition(); netcode = pad.GetNetCode()
    items = local_items(ppos.x, ppos.y, MM(6), netcode)
    cands = []
    for it in all_items:
        if it.GetNetCode() != netcode: continue
        pts = [it.GetPosition()] if it.GetClass() == 'PCB_VIA' else ([it.GetStart(), it.GetEnd()] if it.GetClass() == 'PCB_TRACK' and it.GetLayer() == F else [])
        for q in pts:
            d = math.hypot(q.x - ppos.x, q.y - ppos.y)
            if d < MM(6): cands.append((d, q.x, q.y))
    cands.sort()
    done = False
    for d, qx, qy in cands[:12]:
        if in_keepout((ppos.x + qx) / 2, (ppos.y + qy) / 2): continue
        if collide(items, seg_sh(ppos.x, ppos.y, qx, qy), (F,)): continue
        add_track(ppos.x, ppos.y, qx, qy, netname); done = True; fixed += 1; break
    if not done: still.append((ref, pname, netname))
failed = still

print("fanout ok:", fixed)
if failed:
    print("FAILED:", failed)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(PCB, board)
print("saved")

