"""Move power vias out of SMD pads (dog-bone fanout).

The original fanout allowed a via anywhere >= 0.25 mm from the pad centre and
only checked *other-net* copper, so most GND/+3V3 vias ended up inside their
own pad. Vias in pads wick solder during reflow unless the fab fills and caps
them, so here every such via is re-placed just outside the pad with a short
stub. Vias stay in place only inside genuine thermal pads / tabs (smallest
pad dimension >= KEEP_MIN_MM), or where the diagnostics prove there is no room
(then the via goes back into the pad at 0.4 mm and is listed for fill & cap).

Two passes in two processes (pcbnew's SWIG wrappers go stale after Remove()):
  python.exe tools/dogbone_vias.py remove   -> writes fab/_dogbone.json
  python.exe tools/dogbone_vias.py add      -> re-places, fills zones, saves
  python.exe tools/dogbone_vias.py diag     -> like add, reports only
"""
import functools
import builtins
import json
import math
import os
import sys

print = functools.partial(builtins.print, flush=True)
import pcbnew

HW = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "hardware", "dronemagnav")
PCB = os.path.join(HW, "dronemagnav.kicad_pcb")
STATE = os.path.join(HW, "fab", "_dogbone.json")

VIA_DIA, VIA_DRILL, TRACK_W, CLR = 0.45, 0.2, 0.22, 0.155
PAD_GAP = 0.15          # mask web between via annulus and the pad copper
KEEP_MIN_MM = 2.0       # vias may stay inside pads at least this wide (thermal pads)
IN_PAD_GAP = 0.10       # via closer than this to a pad edge counts as "in pad"
EDGE_MARGIN = 0.5       # board-setup copper-to-edge clearance

PHASE = sys.argv[1] if len(sys.argv) > 1 else "remove"
DIAG = PHASE == "diag"
board = pcbnew.LoadBoard(PCB)
nets = board.GetNetsByName()
F, B = pcbnew.F_Cu, pcbnew.B_Cu


def MM(v):
    return pcbnew.FromMM(v)


def circ(x, y, dia=VIA_DIA):
    return pcbnew.SHAPE_CIRCLE(pcbnew.VECTOR2I(int(x), int(y)), MM(dia / 2))


def seg(x1, y1, x2, y2, w=TRACK_W):
    return pcbnew.SHAPE_SEGMENT(pcbnew.VECTOR2I(int(x1), int(y1)),
                                pcbnew.VECTOR2I(int(x2), int(y2)), MM(w))


def pad_layer(pad):
    return F if pad.IsOnLayer(F) else B


def pad_key(ref, pad):
    """pads are NOT unique by number (SW pads '2', J3 'SH', J4 '2'): key by position"""
    p = pad.GetPosition()
    return [ref, pad.GetNumber(), pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)]


def find_pad(key):
    fp = board.FindFootprintByReference(key[0])
    best = min(fp.Pads(), key=lambda q: math.hypot(pcbnew.ToMM(q.GetPosition().x) - key[2],
                                                    pcbnew.ToMM(q.GetPosition().y) - key[3]))
    return best


# ------------------------------------------------------------------ remove
if PHASE == "remove":
    pads = [(fp.GetReference(), p) for fp in board.Footprints() for p in fp.Pads()
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD]
    # gather everything first: the SWIG wrappers go stale once Remove() runs
    tracks = list(board.GetTracks())
    vias = [t for t in tracks if t.GetClass() == "PCB_VIA"]
    segs = [t for t in tracks if t.GetClass() == "PCB_TRACK"]
    entries, keep, doomed, moved_pads = [], [], [], []
    for v in vias:
        vp = v.GetPosition()
        hit = None
        for ref, p in pads:
            if p.GetNetCode() != v.GetNetCode():
                continue
            L = pad_layer(p)
            if p.GetEffectiveShape(L).Collide(circ(vp.x, vp.y, pcbnew.ToMM(v.GetWidth(F))),
                                               MM(IN_PAD_GAP)):
                hit = (ref, p)
                break
        if not hit:
            continue
        ref, p = hit
        sz = p.GetSize()
        if pcbnew.ToMM(min(sz.x, sz.y)) >= KEEP_MIN_MM:
            keep.append(pad_key(ref, p) + [v.GetNetname()])
            continue
        entries.append({"key": pad_key(ref, p), "net": v.GetNetname(),
                        "layer": "F" if pad_layer(p) == F else "B",
                        "old": [pcbnew.ToMM(vp.x), pcbnew.ToMM(vp.y)]})
        moved_pads.append(p)
        doomed.append(v)
    # stubs that lie entirely inside a vacated pad become dead copper: drop them
    dropped = 0
    for t in segs:
        for p in moved_pads:
            if t.GetNetCode() != p.GetNetCode():
                continue
            sh = p.GetEffectiveShape(pad_layer(p))
            if sh.Collide(t.GetStart(), 0) and sh.Collide(t.GetEnd(), 0):
                doomed.append(t)
                dropped += 1
                break
    for it in doomed:
        board.Remove(it)
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump({"move": entries, "keep": keep}, open(STATE, "w"), indent=1)
    pcbnew.SaveBoard(PCB, board)
    print(f"removed {len(entries)} vias-in-pad (+{dropped} dead stubs); "
          f"kept {len(keep)} in thermal pads: {[k[:2] for k in keep]}")
    sys.exit(0)

# --------------------------------------------------------------------- add
state = json.load(open(STATE))
all_items = [p for fp in board.Footprints() for p in fp.Pads()] + list(board.GetTracks())
zones = list(board.Zones()) + [z for fp in board.Footprints() for z in fp.Zones()]
via_zones = [z for z in zones if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
trk_zones = [z for z in zones if z.GetIsRuleArea() and z.GetDoNotAllowTracks()]
edge = board.GetBoardEdgesBoundingBox()
inner = pcbnew.BOX2I(edge.GetPosition(), edge.GetSize())
inner.Inflate(-MM(EDGE_MARGIN + VIA_DIA / 2))


def via_in_keepout(x, y, dia):
    p = pcbnew.VECTOR2I(int(x), int(y))
    if not inner.Contains(p):
        return True
    return any(z.Outline().Collide(p, MM(dia / 2)) for z in via_zones)


def stub_in_keepout(sh):
    return any(z.Outline().Collide(sh, 0) for z in trk_zones)


def near(cx, cy, r):
    out = []
    for it in all_items:
        if it.GetClass() == "PCB_TRACK":
            s, e = it.GetStart(), it.GetEnd()
            ax, ay, ex = (s.x + e.x) / 2, (s.y + e.y) / 2, math.hypot(e.x - s.x, e.y - s.y) / 2
        else:
            q = it.GetPosition()
            ax, ay, ex = q.x, q.y, MM(2.5)
        if math.hypot(ax - cx, ay - cy) < r + ex + MM(1.0):
            out.append(it)
    return out


def collides(items, shape, layers, netcode, gap=CLR, same_net_pads_gap=None):
    """other-net copper at `gap`; same-net *pads* at `same_net_pads_gap` (so a
    via never lands under any pad, own net included)."""
    for it in items:
        is_pad = it.GetClass() == "PAD"
        if it.GetNetCode() == netcode:
            if not (is_pad and same_net_pads_gap is not None):
                continue
            g = same_net_pads_gap
        else:
            g = gap
        for L in layers:
            if hasattr(it, "IsOnLayer") and not it.IsOnLayer(L):
                continue
            if it.GetEffectiveShape(L).Collide(shape, MM(g)):
                return True
            break
    return False


def via_too_close(x, y):
    return any(it.GetClass() == "PCB_VIA" and
               math.hypot(it.GetPosition().x - x, it.GetPosition().y - y) < MM(VIA_DIA + 0.15)
               for it in all_items)


def add_track(x1, y1, x2, y2, net, layer, w=TRACK_W):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pcbnew.VECTOR2I(int(x1), int(y1)))
    t.SetEnd(pcbnew.VECTOR2I(int(x2), int(y2)))
    t.SetLayer(layer)
    t.SetWidth(MM(w))
    t.SetNet(nets[net])
    board.Add(t)
    all_items.append(t)


def add_via(x, y, net, dia=VIA_DIA):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pcbnew.VECTOR2I(int(x), int(y)))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetDrill(MM(VIA_DRILL))
    v.SetWidth(MM(dia))
    v.SetLayerPair(F, B)
    v.SetNet(nets[net])
    board.Add(v)
    all_items.append(v)


placed, restored = [], []
for e in state["move"]:
    pad = find_pad(e["key"])
    fp = board.FindFootprintByReference(e["key"][0])
    L = F if e["layer"] == "F" else B
    pp, fpos = pad.GetPosition(), fp.GetPosition()
    netcode, net = pad.GetNetCode(), e["net"]
    # outward = away from the footprint centre (keeps the via off the body)
    ox, oy = pp.x - fpos.x, pp.y - fpos.y
    on = math.hypot(ox, oy) or 1.0
    ox, oy = ox / on, oy / on
    pad_sh = pad.GetEffectiveShape(L)
    items = near(pp.x, pp.y, MM(4))
    stub_w = min(TRACK_W, max(0.2, pcbnew.ToMM(min(pad.GetSize().x, pad.GetSize().y))))
    cands = []
    for r10 in range(4, 36):                     # 0.4 .. 3.5 mm from pad centre
        r = MM(r10 / 10)
        for a in range(0, 360, 10):
            vx = pp.x + r * math.cos(math.radians(a))
            vy = pp.y + r * math.sin(math.radians(a))
            dot = ((vx - pp.x) * ox + (vy - pp.y) * oy) / r
            cands.append((r - MM(0.6) * dot, vx, vy))  # prefer outward
    cands.sort()
    ok = None
    why = {}
    for dia in (VIA_DIA, 0.4):
        for gap in (PAD_GAP, 0.12):
            for _, vx, vy in cands:
                if via_in_keepout(vx, vy, dia):
                    why["keepout"] = why.get("keepout", 0) + 1
                    continue
                if via_too_close(vx, vy):
                    why["via-spacing"] = why.get("via-spacing", 0) + 1
                    continue
                if pad_sh.Collide(circ(vx, vy, dia), MM(gap)):
                    why["own-pad"] = why.get("own-pad", 0) + 1
                    continue                              # still over the pad
                if collides(items, circ(vx, vy, dia), (F, B), netcode, same_net_pads_gap=gap):
                    why["copper"] = why.get("copper", 0) + 1
                    continue
                # straight stub, else an L via a 0.6 mm outward waypoint
                wx, wy = pp.x + ox * MM(0.6), pp.y + oy * MM(0.6)
                for path in ([(pp.x, pp.y, vx, vy)],
                             [(pp.x, pp.y, wx, wy), (wx, wy, vx, vy)]):
                    bad = False
                    for (a, b_, c_, d_) in path:
                        s = seg(a, b_, c_, d_, stub_w)
                        if collides(items, s, (L,), netcode) or stub_in_keepout(s):
                            bad = True
                            break
                    if not bad:
                        ok = (vx, vy, dia, path)
                        break
                if ok:
                    break
                why["stub"] = why.get("stub", 0) + 1
            if ok:
                break
        if ok:
            break
    if not ok:
        print(f"  {e['key'][:2]} {net}: no room, rejections {why} -> via back in pad (fill & cap)")
        if not DIAG:
            add_via(MM(e["old"][0]), MM(e["old"][1]), net, 0.4)
        restored.append(e["key"] + [net])
        continue
    vx, vy, dia, path = ok
    if not DIAG:
        for (a, b_, c_, d_) in path:
            add_track(a, b_, c_, d_, net, L, stub_w)
        add_via(vx, vy, net, dia)
    placed.append(e["key"][:2] + [round(pcbnew.ToMM(vx), 3), round(pcbnew.ToMM(vy), 3), dia])

print(f"dog-boned {len(placed)} vias; {len(restored)} left in pad for fill & cap: "
      f"{[r[:2] for r in restored]}")
if DIAG:
    print("diag only, board not saved")
    sys.exit(0)
state["placed"] = placed
state["fillcap"] = restored
json.dump(state, open(STATE, "w"), indent=1)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(PCB, board)
print("saved")
