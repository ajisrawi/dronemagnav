"""Audit the routed board and emit the numbers that go into the fabrication
notes: stackup, copper/drill extremes, via-in-pad locations, and the nets that
need controlled impedance.

Run with KiCad's Python:
  & "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" tools/fab_audit.py
"""
import json
import os
import sys

import pcbnew

HW = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "hardware", "dronemagnav")
PCB = os.path.join(HW, "dronemagnav.kicad_pcb")
IU = 1e6  # internal units per mm


def mm(v):
    return round(v / IU, 4)


def main():
    b = pcbnew.LoadBoard(PCB)
    bb = b.GetBoardEdgesBoundingBox()
    out = {"board_mm": [mm(bb.GetWidth()), mm(bb.GetHeight())],
           "layers": b.GetCopperLayerCount()}

    tw, vias = set(), []
    for t in b.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            vias.append((mm(t.GetPosition().x), mm(t.GetPosition().y),
                         mm(t.GetWidth(pcbnew.F_Cu)), mm(t.GetDrill()), t.GetNetname()))
        else:
            tw.add(mm(t.GetWidth()))
    out["track_widths_mm"] = sorted(tw)
    out["via_count"] = len(vias)
    out["via_sizes"] = sorted({(v[2], v[3]) for v in vias})

    # pads: find vias whose annulus overlaps (or nearly touches) a pad's copper
    vip = []
    holes = set()
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        for p in fp.Pads():
            d = p.GetDrillSize()
            if d.x > 0:
                holes.add(mm(d.x))
            if p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue
            L = pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
            sh = p.GetEffectiveShape(L)
            for v in vias:
                c = pcbnew.SHAPE_CIRCLE(pcbnew.VECTOR2I(int(v[0] * IU), int(v[1] * IU)),
                                        int(v[2] * IU / 2))
                if sh.Collide(c, int(0.10 * IU)):
                    vip.append({"ref": ref, "pad": p.GetNumber(), "net": v[4],
                                "x": v[0], "y": v[1], "dia": v[2], "drill": v[3],
                                "pad_size": [mm(p.GetSize().x), mm(p.GetSize().y)]})
    out["pad_hole_sizes_mm"] = sorted(holes)
    out["vias_in_pad"] = vip
    out["min_via_drill_mm"] = min((v[3] for v in vias), default=None)
    out["min_hole_mm"] = min(list(holes) + [v[3] for v in vias], default=None)

    # net classes / clearance
    ds = b.GetDesignSettings()
    out["min_clearance_mm"] = mm(ds.m_MinClearance)
    out["min_track_mm"] = mm(ds.m_TrackMinWidth)

    print(json.dumps(out, indent=1))
    with open(os.path.join(HW, "fab", "_audit.json"), "w") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    sys.exit(main())
