"""Regenerate the manufacturing package for the routed board.

  python tools/make_fab.py

Produces in hardware/dronemagnav/:
  fab/gerbers/*            Gerber X2 (all copper, mask, paste, silk, fab,
                           courtyard, edge) + Excellon drill + drill map
  fab/dronemagnav-pos.csv  pick-and-place (mm, both sides)
  fab/FABRICATION-NOTES.md board spec, stackup, via-in-pad list, assembly notes
  fab/dronemagnav-gerbers.zip  gerbers + drill + notes, ready to upload
  board-top.png / board-bottom.png  3-D renders
The numbers in the notes come from tools/fab_audit.py (run first, with
KiCad's python) and from the dog-bone pass (fab/_dogbone.json).
"""
import json
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HW = os.path.join(ROOT, "hardware", "dronemagnav")
PCB = os.path.join(HW, "dronemagnav.kicad_pcb")
FAB = os.path.join(HW, "fab")
GERB = os.path.join(FAB, "gerbers")
CLI = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"
KPY = r"C:\Program Files\KiCad\10.0\bin\python.exe"


def run(*args):
    print("$", " ".join(os.path.basename(a) if i == 0 else a for i, a in enumerate(args)))
    subprocess.run(args, check=True)


def main():
    run(KPY, os.path.join(ROOT, "tools", "fab_audit.py"))
    audit = json.load(open(os.path.join(FAB, "_audit.json")))
    dog = json.load(open(os.path.join(FAB, "_dogbone.json")))

    if os.path.isdir(GERB):
        shutil.rmtree(GERB)
    os.makedirs(GERB)
    run(CLI, "pcb", "export", "gerbers", "-o", GERB + os.sep, "--subtract-soldermask", PCB)
    run(CLI, "pcb", "export", "drill", "-o", GERB + os.sep, "--format", "excellon",
        "--excellon-units", "mm", "--generate-map", "--map-format", "gerberx2", PCB)
    run(CLI, "pcb", "export", "pos", "-o", os.path.join(FAB, "dronemagnav-pos.csv"),
        "--format", "csv", "--units", "mm", "--side", "both", "--use-drill-file-origin", PCB)
    run(sys.executable, os.path.join(ROOT, "tools", "make_jlc.py"),
        "--pos", os.path.join(FAB, "dronemagnav-pos.csv"),
        "--bom", os.path.join(ROOT, "docs", "BOM.csv"),
        "--out", os.path.join(FAB, "dronemagnav"),
        "--lcsc", os.path.join(ROOT, "docs", "lcsc-parts.csv"))
    run(KPY, os.path.join(ROOT, "tools", "make_pcbway.py"))
    if not os.path.exists(os.path.join(FAB, "dronemagnav-bom-pcbway.xlsx")):
        run(sys.executable, os.path.join(ROOT, "tools", "make_pcbway_xlsx.py"))
    for side in ("top", "bottom"):
        run(CLI, "pcb", "render", "-o", os.path.join(HW, f"board-{side}.png"),
            "--side", side, "--width", "1600", "--height", "1500", "--zoom", "0.92",
            "--quality", "high", PCB)

    # ---------------------------------------------------------------- notes
    vip = audit["vias_in_pad"]
    thermal = [v for v in vip if min(v["pad_size"]) >= 2.0]
    # a via inside a thermal pad also "hits" that pad's paste sub-pads
    # (ESP32 module EP): count it once, as thermal
    tpos = {(v["x"], v["y"]) for v in thermal}
    small = [v for v in vip if min(v["pad_size"]) < 2.0 and (v["x"], v["y"]) not in tpos]
    w, h = audit["board_mm"]
    lines = [
        "# DroneMagNav rev A - fabrication and assembly notes",
        "",
        "## Board",
        f"- Size {w:.1f} x {h:.1f} mm, {audit['layers']} copper layers, 1.6 mm FR-4 (TG >= 150), "
        "1 oz outer / 0.5 oz inner copper.",
        "- Stackup: F.Cu signal / In1.Cu GND plane / In2.Cu +3V3 plane / B.Cu signal.",
        "- Surface finish: ENIG (flat pads for the 0.5 mm-pitch BMI088 LGA and the USB-C receptacle).",
        "- Solder mask green, silkscreen white, both sides. Mask clearance per Gerber files.",
        f"- Minimum track {audit['min_track_mm']:.2f} mm, minimum clearance "
        f"{audit['min_clearance_mm']:.2f} mm, minimum hole {audit['min_hole_mm']:.2f} mm.",
        "- Via sizes (diameter / drill, mm): " +
        ", ".join(f"{d:.2f}/{dr:.2f}" for d, dr in audit["via_sizes"]) +
        f"; {audit['via_count']} vias total.",
        "- Plated holes (drill, mm): " +
        ", ".join(f"{d:.2f}" for d in audit["pad_hole_sizes_mm"] if d > 0.25) +
        "; four 3.2 mm mounting holes on the 30.5 mm Pixhawk pattern are non-plated.",
        "- Controlled impedance: the GNSS RF trace from U.FL J4 to U5 RF_IN is 50 ohm single-ended "
        "over the In1 ground plane. Please adjust the trace width to your stackup if it differs "
        "from 0.2 mm prepreg between F.Cu and In1.Cu.",
        "- Copper keep-out under the ESP32-S3-WROOM-1 antenna (top edge, x 106-154 mm) on all layers: "
        "do not add copper, thieving or fiducials there.",
        "",
        "## Vias in pads (IMPORTANT)",
        f"- {len(dog.get('placed', []))} power vias were moved out of their pads into dog-bone stubs, "
        "so the vast majority of pads carry no via.",
        f"- {len(small)} vias remain inside small pads because the surrounding routing leaves no room. "
        "These MUST be filled and capped (IPC-4761 Type VII, epoxy fill + plated cap) or at minimum "
        "plugged and tented on the component side, otherwise solder wicks into the hole and the joint "
        "is starved:",
    ]
    for v in small:
        lines.append(f"    - {v['ref']} pad {v['pad']} ({v['net']}), via {v['dia']:.2f}/{v['drill']:.2f} mm "
                     f"at ({v['x']:.3f}, {v['y']:.3f}) mm, pad {v['pad_size'][0]:.2f} x {v['pad_size'][1]:.2f} mm")
    lines += [
        f"- {len(thermal)} vias sit inside large thermal pads / tabs (normal practice; tented or "
        "filled, either is fine):",
    ]
    for v in thermal:
        lines.append(f"    - {v['ref']} pad {v['pad'] or 'EP'} ({v['net']}) at ({v['x']:.3f}, {v['y']:.3f}) mm")
    lines += [
        "",
        "## Assembly",
        "- All components are on the top side (see dronemagnav-pos.csv, mm, origin = drill/place origin).",
        "- Reflow profile per BMI088 / LIS3MDL / BMP280 datasheets (lead-free, peak <= 260 C). "
        "Do not clean the sensors ultrasonically.",
        "- U1 ESP32-S3-WROOM-1: keep the antenna end overhanging the board edge free of solder and fixtures.",
        "- J3 microSD (Hirose DM3AT) and J1 USB-C: hand-inspect the shield pads for bridges.",
        "- U3 LIS3MDL magnetometer: keep away from magnetised tools and fixtures; no magnetic "
        "nozzles or trays during placement.",
        "- Fiducials: none on the board; use the mounting holes as datums.",
        "",
        "## Files",
        "- gerbers/*.gtl .g1 .g2 .gbl .gts .gbs .gtp .gbp .gto .gbo .gm1  copper, mask, paste, silk, edge",
        "- gerbers/dronemagnav.drl + dronemagnav-drl_map.gbr  Excellon drill (all plated except the "
        "3.2 mm mounting holes) and drill map",
        "- gerbers/dronemagnav-job.gbrjob  Gerber job file with the stackup",
        "- dronemagnav-pos.csv  pick-and-place (KiCad format)",
        "- dronemagnav-cpl-jlcpcb.csv + dronemagnav-bom-jlcpcb.csv  the same placement list and BOM "
        "in JLCPCB's upload format (LCSC column left blank: let the uploader match on MPN and confirm)",
        "- dronemagnav-centroid-pcbway.csv + dronemagnav-bom-pcbway.csv/.xlsx  PCBWay-format centroid "
        "(mm, origin bottom-left, Y up, pad-1 position, T/B layer) and BOM (PCBWay template columns)",
        "- ../docs/BOM.csv  bill of materials with manufacturer part numbers",
        "",
        "Generated by tools/make_fab.py from the routed board; via/pad numbers from tools/fab_audit.py.",
    ]
    notes = os.path.join(FAB, "FABRICATION-NOTES.md")
    with open(notes, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("wrote", notes)

    zpath = os.path.join(FAB, "dronemagnav-gerbers.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(os.listdir(GERB)):
            z.write(os.path.join(GERB, name), name)
        z.write(notes, "FABRICATION-NOTES.md")
        for extra in ("dronemagnav-pos.csv", "dronemagnav-cpl-jlcpcb.csv",
                      "dronemagnav-bom-jlcpcb.csv", "dronemagnav-centroid-pcbway.csv",
                      "dronemagnav-bom-pcbway.csv", "dronemagnav-bom-pcbway.xlsx"):
            p = os.path.join(FAB, extra)
            if os.path.exists(p):
                z.write(p, extra)
    print("wrote", zpath, os.path.getsize(zpath) // 1024, "KB")


if __name__ == "__main__":
    sys.exit(main())
