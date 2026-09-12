"""Build the DroneMagNav PCB from the exported netlist.

Run with KiCad's Python:
  "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" tools/make_pcb.py

60 x 60 mm, 4-layer (F.Cu / In1 GND / In2 +3V3 / B.Cu), 30.5 mm Pixhawk-style
M3 mounting pattern, ESP32 antenna at the top edge with a copper keep-out,
USB-C left edge, microSD right edge, sensors centre, magnetometer bottom
centre (away from regulators), FC and mast JST-GH connectors bottom/right.
"""
import math
import os
import re

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HW = os.path.join(ROOT, "hardware", "dronemagnav")
NETLIST = os.path.join(HW, "netlist.net")
PCB = os.path.join(HW, "dronemagnav.kicad_pcb")
DSN = os.path.join(HW, "dronemagnav.dsn")
FPDIR = r"C:\Program Files\KiCad\10.0\share\kicad\footprints"

BX0, BY0, BX1, BY1 = 98.0, 100.0, 162.0, 160.0     # 64 x 60 mm
EDGE_MARGIN = 1.0
GAP = 0.35
ANT_KEEPOUT_Y = 106.4      # module antenna keep-out: no copper above (x 106..154)


def mm(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))


def parse_netlist(path):
    text = open(path, encoding="utf-8").read()
    comps = {}
    for m in re.finditer(
            r'\(comp\s+\(ref "([^"]+)"\)\s+\(value "([^"]+)"\)\s+'
            r'(?:\(footprint "([^"]*)"\))?', text):
        comps[m.group(1)] = (m.group(2), m.group(3) or "")
    nets = {}
    for m in re.finditer(r'\(net\s+\(code "\d+"\)\s+\(name "([^"]+)"\)', text):
        start = m.start()
        d = 0
        j = start
        while True:
            c = text[j]
            if c == '(':
                d += 1
            elif c == ')':
                d -= 1
                if d == 0:
                    break
            j += 1
        block = text[start:j + 1]
        nodes = re.findall(r'\(ref "([^"]+)"\)\s+\(pin "([^"]+)"\)', block)
        nets[m.group(1)] = [(r, p) for r, p in nodes]
    return comps, nets


ANCHORS = {"U1", "U2", "U3", "U4", "U5", "J1", "J2", "J3", "J4", "J5",
           "U6", "U7", "H1", "H2", "H3", "H4", "SW1", "SW2"}

PLACE = {
    # ESP32 module, antenna toward the top edge (keep-out x 106..154, y < 106.2)
    "U1": (130, 113, 0),
    "C8": (120, 128, 90), "C9": (123, 128, 90),
    "R2": (109, 128, 90), "C7": (112, 128, 90), "R3": (115, 128, 90),
    # buttons in the keep-out-free top-left strip (x < 106), rotated
    "SW1": (102.2, 106.5, 90), "SW2": (102.2, 117.5, 90),
    # USB-C flush with the left edge, ESD next to it
    "J1": (102.6, 130, 0),
    "U8": (112, 133, 0), "R16": (110, 137, 0), "R17": (114, 137, 0),
    # LEDs row under the module
    "R4": (127, 129, 0), "R5": (131, 129, 0), "R6": (135, 129, 0),
    "D3": (139, 129, 0), "D4": (127, 132, 0), "D5": (131, 132, 0),
    "D6": (135, 132, 0), "R1": (139, 132, 0),
    # sensors centre; magnetometer bottom-centre away from regulators
    "U2": (130, 138, 0),
    "C10": (124, 141, 90), "C11": (136, 141, 90),
    "U4": (140, 137, 0), "C14": (137, 141, 90), "C15": (140, 141, 90),
    "U3": (130, 149, 0), "C12": (126, 152, 90), "C13": (134, 152, 90),
    # GNSS right of the module, below the antenna keep-out, U.FL under it
    "U5": (155.5, 112, 0), "J4": (156, 121, 0),
    "R15": (157, 103.5, 90), "C16": (160, 119.5, 90), "C17": (160, 123, 90),
    # microSD right edge (card slot overhangs), pull-ups beside it
    "J3": (151, 133, 0),
    "R9": (150, 143, 90), "R10": (152.5, 143, 90), "R11": (155, 143, 90),
    "R12": (157.5, 143, 90), "R13": (150, 146.5, 90), "R14": (152.5, 146.5, 90),
    "C18": (150, 150, 90),
    # power, bottom-left corner
    "D1": (102, 142, 90), "D2": (105.5, 142, 90),
    "U6": (105, 154, 0), "C1": (101, 148, 90), "C2": (110, 150, 90),
    "C3": (110, 154, 90),
    "U7": (118, 155, 0), "C4": (114, 151, 90), "C5": (122, 151, 90),
    "C6": (122, 155, 90),
    # I2C pull-ups + debug header
    "R7": (117, 140, 90), "R8": (120, 140, 90), "J7": (118, 144.5, 0),
    # connectors bottom / right
    "J2": (157, 152, 0), "J5": (130, 156.5, 0),
}
FACE = {"J1": (-1, 0), "J3": (1, 0), "J2": (1, 0), "J5": (0, 1), "J7": (0, 1)}


def orient_connector(fp, face):
    best, best_dot = 0, 1e9
    for rot in (0, 90, 180, 270):
        fp.SetOrientationDegrees(rot)
        body = fp.GetBoundingBox(False)
        pads_x = pads_y = n = 0
        for pad in fp.Pads():
            p = pad.GetPosition()
            pads_x += p.x
            pads_y += p.y
            n += 1
        cx, cy = body.GetCenter().x, body.GetCenter().y
        vx, vy = pads_x / n - cx, pads_y / n - cy
        dot = vx * face[0] + vy * face[1]
        if dot < best_dot:
            best_dot, best = dot, rot
    fp.SetOrientationDegrees(best)


def boxes_overlap(a, b, margin_iu):
    return (a.GetLeft() - margin_iu < b.GetRight() and
            b.GetLeft() - margin_iu < a.GetRight() and
            a.GetTop() - margin_iu < b.GetBottom() and
            b.GetTop() - margin_iu < a.GetBottom())


def fp_box(fp):
    try:
        poly = fp.GetCourtyard(pcbnew.F_CrtYd)
        if poly.OutlineCount() > 0:
            return poly.BBox()
    except Exception:
        pass
    return fp.GetBoundingBox(False)


def deoverlap(board, movable):
    fps = {fp.GetReference(): fp for fp in board.Footprints()}
    margin = pcbnew.FromMM(GAP)
    for _ in range(400):
        moved = False
        items = list(fps.values())
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, b = items[i], items[j]
                ra, rb = a.GetReference(), b.GetReference()
                ba, bb = fp_box(a), fp_box(b)
                if not boxes_overlap(ba, bb, margin):
                    continue
                px = min(ba.GetRight(), bb.GetRight()) - \
                    max(ba.GetLeft(), bb.GetLeft()) + margin
                py = min(ba.GetBottom(), bb.GetBottom()) - \
                    max(ba.GetTop(), bb.GetTop()) + margin
                move_a, move_b = ra in movable, rb in movable
                if not (move_a or move_b):
                    continue
                if px < py:
                    d = px
                    sign = 1 if ba.GetCenter().x < bb.GetCenter().x else -1
                    da, db = (-sign * d, 0), (sign * d, 0)
                else:
                    d = py
                    sign = 1 if ba.GetCenter().y < bb.GetCenter().y else -1
                    da, db = (0, -sign * d), (0, sign * d)
                if move_a and move_b:
                    da = (da[0] // 2, da[1] // 2)
                    db = (db[0] // 2, db[1] // 2)
                for fp2, dd, can in ((a, da, move_a), (b, db, move_b)):
                    if not can:
                        continue
                    p = fp2.GetPosition()
                    nx, ny = p.x + int(dd[0]), p.y + int(dd[1])
                    bbx = fp_box(fp2)
                    hw, hh = bbx.GetWidth() // 2, bbx.GetHeight() // 2
                    nx = max(pcbnew.FromMM(BX0 + EDGE_MARGIN) + hw,
                             min(pcbnew.FromMM(BX1 - EDGE_MARGIN) - hw, nx))
                    ny = max(pcbnew.FromMM(BY0 + EDGE_MARGIN) + hh,
                             min(pcbnew.FromMM(BY1 - EDGE_MARGIN) - hh, ny))
                    if (nx, ny) != (p.x, p.y):
                        fp2.SetPosition(pcbnew.VECTOR2I(nx, ny))
                        moved = True
        if not moved:
            return True
    return False


def load_fp(fpid):
    lib, name = fpid.split(":", 1)
    return pcbnew.FootprintLoad(os.path.join(FPDIR, lib + ".pretty"), name)


def main():
    comps, nets = parse_netlist(NETLIST)
    if os.path.exists(PCB):
        os.remove(PCB)
    board = pcbnew.NewBoard(PCB)
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(4)
    ds.m_ViasMinSize = pcbnew.FromMM(0.45)
    ds.m_MinThroughDrill = pcbnew.FromMM(0.2)
    ds.m_HoleToHoleMin = pcbnew.FromMM(0.2)

    netmap = {}
    for name in nets:
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        netmap[name] = ni
    padnet = {}
    for name, nodes in nets.items():
        for ref, pad in nodes:
            padnet[(ref, pad)] = name

    issues, movable = [], set()
    for ref, (value, fpid) in sorted(comps.items()):
        if ref.startswith("#"):
            continue
        fp = load_fp(fpid) if fpid else None
        if fp is None:
            issues.append((ref, fpid or "no footprint"))
            continue
        fp.SetReference(ref)
        fp.SetValue(value)
        board.Add(fp)
        x, y, rot = PLACE.get(ref, (130, 145, 0))
        if ref not in PLACE:
            issues.append((ref, "no placement -> parked"))
        fp.SetPosition(mm(x, y))
        if ref in FACE:
            orient_connector(fp, FACE[ref])
        else:
            fp.SetOrientationDegrees(rot)
        if ref not in ANCHORS:
            movable.add(ref)
        for pad in fp.Pads():
            key = (ref, pad.GetName())
            if key in padnet:
                pad.SetNet(netmap[padnet[key]])

    # 30.5 mm Pixhawk-style mounting pattern centred on the board
    cx, cy = (BX0 + BX1) / 2, (BY0 + BY1) / 2
    for i, (hx, hy) in enumerate([(cx - 15.25, cy - 15.25), (cx + 15.25, cy - 15.25),
                                  (cx - 15.25, cy + 15.25), (cx + 15.25, cy + 15.25)],
                                 1):
        fp = pcbnew.FootprintLoad(os.path.join(FPDIR, "MountingHole.pretty"),
                                  "MountingHole_3.2mm_M3")
        fp.SetReference(f"H{i}")
        fp.SetValue("M3")
        board.Add(fp)
        fp.SetPosition(mm(hx, hy))

    converged = deoverlap(board, movable)

    for fp in board.Footprints():
        bb = fp.GetBoundingBox(False)
        ref = fp.Reference()
        ref.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(0.8), pcbnew.FromMM(0.8)))
        ref.SetTextThickness(pcbnew.FromMM(0.13))
        ref.SetTextAngleDegrees(0)
        ref.SetPosition(pcbnew.VECTOR2I(bb.GetCenter().x,
                                        bb.GetTop() - pcbnew.FromMM(0.8)))

    pts = [(BX0, BY0), (BX1, BY0), (BX1, BY1), (BX0, BY1)]
    for i in range(4):
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetStart(mm(*pts[i]))
        seg.SetEnd(mm(*pts[(i + 1) % 4]))
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetWidth(pcbnew.FromMM(0.1))
        board.Add(seg)

    npth = []
    for fp in board.Footprints():
        for pad in fp.Pads():
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                p = pad.GetPosition()
                r = max(pad.GetDrillSize().x, pad.GetDrillSize().y) / 2
                npth.append((p.x, p.y, r + pcbnew.FromMM(0.6)))

    def add_zone(layer, netname, pts):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNetCode(netmap[netname].GetNetCode())
        ol = z.Outline()
        ol.NewOutline()
        for px, py in pts:
            ol.Append(pcbnew.FromMM(px), pcbnew.FromMM(py))
        x0, y0 = min(p[0] for p in pts), min(p[1] for p in pts)
        x1, y1 = max(p[0] for p in pts), max(p[1] for p in pts)
        for hx, hy, hr in npth:
            if not (pcbnew.FromMM(x0) < hx < pcbnew.FromMM(x1) and
                    pcbnew.FromMM(y0) < hy < pcbnew.FromMM(y1)):
                continue
            hole = ol.NewHole()
            for k in range(12):
                a = 2 * math.pi * k / 12
                ol.Append(int(hx + hr * math.cos(a)), int(hy + hr * math.sin(a)),
                          0, hole)
        z.SetLocalClearance(pcbnew.FromMM(0.22))
        z.SetMinThickness(pcbnew.FromMM(0.15))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        board.Add(z)

    E = 0.65
    # planes: full board minus the module antenna notch (x 106..154 above y 107.5)
    AX0, AX1 = 106.0, 154.0
    plane_pts = [(BX0 + E, BY0 + E), (AX0, BY0 + E), (AX0, ANT_KEEPOUT_Y),
                 (AX1, ANT_KEEPOUT_Y), (AX1, BY0 + E), (BX1 - E, BY0 + E),
                 (BX1 - E, BY1 - E), (BX0 + E, BY1 - E)]
    add_zone(pcbnew.In1_Cu, "GND", plane_pts)
    add_zone(pcbnew.In2_Cu, "+3V3", plane_pts)

    # board-level keep-out over the antenna so the autorouter (which ignores
    # footprint rule areas) keeps tracks and vias out of it on every layer
    ko = pcbnew.ZONE(board)
    ko.SetIsRuleArea(True)
    ko.SetDoNotAllowTracks(True)
    ko.SetDoNotAllowVias(True)
    if hasattr(ko, 'SetDoNotAllowZoneFills'):
        ko.SetDoNotAllowZoneFills(True)
    else:
        ko.SetDoNotAllowCopperPour(True)
    ko.SetZoneName("antenna_keepout")
    ls = pcbnew.LSET()
    for layer in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
        ls.addLayer(layer)
    ko.SetLayerSet(ls)
    kol = ko.Outline()
    kol.NewOutline()
    for px, py in [(AX0, BY0), (AX1, BY0), (AX1, ANT_KEEPOUT_Y), (AX0, ANT_KEEPOUT_Y)]:
        kol.Append(pcbnew.FromMM(px), pcbnew.FromMM(py))
    board.Add(ko)

    # 0.8 mm keep-out ring along the board edge (tracks + vias) so the router
    # honours KiCad's 0.5 mm copper-to-edge rule
    RW = 0.8
    for rect in [(BX0, BY0, BX1, BY0 + RW), (BX0, BY1 - RW, BX1, BY1),
                 (BX0, BY0, BX0 + RW, BY1), (BX1 - RW, BY0, BX1, BY1)]:
        kz = pcbnew.ZONE(board)
        kz.SetIsRuleArea(True)
        kz.SetDoNotAllowTracks(True)
        kz.SetDoNotAllowVias(True)
        kz.SetLayerSet(ls)
        ko2 = kz.Outline()
        ko2.NewOutline()
        x0, y0, x1, y1 = rect
        for px, py in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]:
            ko2.Append(pcbnew.FromMM(px), pcbnew.FromMM(py))
        board.Add(kz)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(PCB, board)
    print("wrote", PCB, "| de-overlap converged:", converged)
    if issues:
        print("ISSUES:", issues)
    print("DSN export:", pcbnew.ExportSpecctraDSN(board, DSN))


if __name__ == "__main__":
    main()
