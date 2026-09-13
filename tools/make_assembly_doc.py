"""Assembly instruction package for the assembler (PCBWay "other files").

  python tools/make_assembly_doc.py

Builds hardware/dronemagnav/fab/dronemagnav-assembly-instructions.pdf:
  1. board overview, orientation / polarity table, handling rules
  2. IC programming instructions (ESP32-S3 via USB-C, esptool)
  3. functional test procedure with pass / fail limits
  4. appendix: KiCad top assembly drawing (F.Fab + silkscreen + outline,
     exported by kicad-cli to fab/_assembly-drawing-kicad.pdf beforehand)
and packs it with the firmware image into
  hardware/dronemagnav/fab/dronemagnav-assembly-other-files.zip
"""
import os
import zipfile

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HW = os.path.join(ROOT, "hardware", "dronemagnav")
FAB = os.path.join(HW, "fab")
BODY = os.path.join(FAB, "_assembly-instructions-body.pdf")
DRAWING = os.path.join(FAB, "_assembly-drawing-kicad.pdf")
OUT = os.path.join(FAB, "dronemagnav-assembly-instructions.pdf")
FW = os.path.join(ROOT, "firmware", "release", "dronemagnav-firmware.factory.bin")
ZIP = os.path.join(FAB, "dronemagnav-assembly-other-files.zip")

ss = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=ss["Heading1"], fontSize=15, spaceAfter=6)
H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=12, spaceBefore=8, spaceAfter=4)
P = ParagraphStyle("p", parent=ss["BodyText"], fontSize=9.5, leading=13)
S = ParagraphStyle("s", parent=P, fontSize=8.5, leading=11)
MONO = ParagraphStyle("m", parent=P, fontName="Courier", fontSize=8.5, leading=11,
                      backColor=colors.whitesmoke, borderPadding=4, leftIndent=4)


def tbl(header, rows, widths):
    data = [[Paragraph(f"<b>{h}</b>", S) for h in header]] + \
           [[Paragraph(str(c), S) for c in r] for r in rows]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dde6f0")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def build_body():
    doc = SimpleDocTemplate(BODY, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title="DroneMagNav rev A - assembly instructions")
    W = A4[0] - 32 * mm
    el = []

    # ------------------------------------------------------------ page 1
    el.append(Paragraph("DroneMagNav rev A - assembly instructions", H1))
    el.append(Paragraph(
        "Magnetic-anomaly navigation module, 64 x 60 mm, 4 layers. 56 SMD parts, all on the "
        "TOP side, no through-hole parts. Files: Gerber ZIP (with FABRICATION-NOTES.md), "
        "BOM (PCBWay template), centroid file (mm, origin bottom-left, pad-1 position). "
        "This document: orientation and handling rules, IC programming, functional test, "
        "and the top assembly drawing (appendix).", P))
    el.append(Spacer(1, 6))
    img = os.path.join(HW, "board-top.png")
    if os.path.exists(img):
        el.append(Image(img, width=95 * mm, height=89 * mm))
        el.append(Paragraph("Top side, as assembled (3-D render from the CAD data).", S))

    el.append(Paragraph("1. Orientation and polarity", H2))
    el.append(Paragraph(
        "Rotations in the centroid file follow the KiCad / Altium convention (degrees, "
        "counter-clockwise positive, 0 deg = library orientation). Pad-1 coordinates are "
        "given for every part; the F.Fab layer in the appendix shows pin-1 marks and pad "
        "outlines with numbers.", P))
    el.append(tbl(["Ref", "Part", "Orientation / polarity"], [
        ["U1", "ESP32-S3-WROOM-1-N16R8", "Pin 1 = pad at the corner marked on F.Fab. The PCB antenna "
         "end of the module overhangs the TOP board edge (x 106-154 mm keep-out): do not clamp, "
         "solder or fixture that end. MSL 3: bake 24 h / 125 C if the bag was open > 168 h."],
        ["U2", "BMI088 LGA-16, 0.5 mm pitch", "Pin-1 dot on the package corner marked on F.Fab. "
         "Pads under the body: solder-paste stencil 0.1 mm, X-ray or AOI check recommended. "
         "Pads 2 and 4 contain filled-and-capped vias."],
        ["U3", "LIS3MDL LGA-12 (magnetometer)", "Pin-1 mark on F.Fab. NO magnetised tools, nozzles or "
         "trays near this part; keep it away from magnets during and after assembly."],
        ["U4", "BMP280 LGA-8", "Pin-1 mark on F.Fab. Do not cover the vent hole with flux residue."],
        ["U5", "MAX-M10S LCC-18", "Pin 1 marked on F.Fab (chamfered corner of the module). RF pin 11 "
         "faces U.FL J4."],
        ["U6", "AMS1117-3.3 SOT-223", "Tab = pin 2 (+3V3 output)."],
        ["U7 / U8", "SOT-23-5 / SOT-23-6", "Pin 1 per F.Fab mark."],
        ["D1, D2", "SS14 SMA Schottky", "Cathode band = pad 1 (silkscreen bar)."],
        ["D3-D6", "0603 LEDs: D3 green, D4 green, D5 blue, D6 yellow",
         "Cathode = pad 1 (silkscreen arrow / bar on the cathode side)."],
        ["J1", "USB-C HRO TYPE-C-31-M-12", "Keyed by the shell; opening faces the LEFT board edge."],
        ["J2, J5", "JST-GH SM06B-GHS-TB, 6-pin", "Pin 1 marked on silkscreen; openings face the board edge."],
        ["J3", "microSD Hirose DM3AT", "Card slot faces the RIGHT board edge; check shield pads for bridges."],
        ["J4", "U.FL-R-SMT-1", "Centre pin = signal, keep pad 1 free of flux residue."],
        ["SW1, SW2", "Tactile 6 x 6 mm", "Symmetric, no polarity."],
        ["R*, C*", "0603 / 0805", "No polarity."],
    ], [14 * mm, 46 * mm, W - 60 * mm]))

    el.append(Paragraph("2. Process and handling", H2))
    for s in [
        "Lead-free reflow per the sensor datasheets: peak 245-260 C, max 30 s above 217 C. No wave, "
        "no hand-soldering of U2/U3/U4.",
        "No ultrasonic cleaning (MEMS sensors U2, U3, U4). No-clean flux preferred.",
        "No magnetised tooling near U3 (magnetometer). Do not store finished boards on magnetic trays.",
        "PCB: 4-layer, ENIG, 1.6 mm, vias filled and capped (three vias sit inside SMD pads: U2 pads 2/4, "
        "J3 pad 4). Board edge clearance 0.5 mm; four 3.2 mm NPTH mounting holes.",
        "Nothing may be placed, printed or glued in the antenna keep-out at the top edge.",
        "Inspect J1 (USB-C) and J3 (microSD) shield pads and the U1 module pads for bridges; the "
        "U2 LGA joints by X-ray if available.",
    ]:
        el.append(Paragraph("- " + s, P))

    # ------------------------------------------------------------ page 2
    el.append(PageBreak())
    el.append(Paragraph("3. IC programming", H2))
    el.append(Paragraph(
        "No pre-programming of any part is required before assembly: the ESP32-S3 module boots "
        "into its factory ROM loader and is flashed over the USB-C connector after assembly. "
        "If the programming service is ordered, flash the supplied image "
        "<b>dronemagnav-firmware.factory.bin</b> (bootloader + partition table + application, "
        "1.16 MB) as follows:", P))
    el.append(tbl(["Step", "Action"], [
        ["1", "Connect the board to a PC with a USB-C data cable (5 V from USB is enough; no other supply)."],
        ["2", "Hold BOOT (SW2), press and release RESET (SW1), release BOOT. The board enumerates as a "
              "USB serial port (Espressif USB JTAG/serial debug unit)."],
        ["3", "With Python 3 and <i>pip install esptool</i> (any version >= 4), run the command below "
              "with the port name of that device."],
        ["4", "Press RESET. The green PWR LED (D3) is on; the serial port re-enumerates and prints the "
              "boot log (see section 4). Done."],
    ], [14 * mm, W - 14 * mm]))
    el.append(Spacer(1, 4))
    el.append(Paragraph(
        "esptool --chip esp32s3 --port COM5 --baud 921600 write-flash 0x0 dronemagnav-firmware.factory.bin",
        MONO))
    el.append(Paragraph(
        "SHA-256 of the image is listed in firmware/release/ in the repository. The image does not "
        "depend on the microSD card; the card only carries map data.", S))

    el.append(Paragraph("4. Functional test (after programming)", H2))
    el.append(Paragraph(
        "Equipment: USB-C cable, PC with a serial terminal (115200 baud), multimeter, a phone or "
        "laptop with WiFi, optionally a FAT32 microSD card and a passive GNSS antenna with U.FL.", P))
    el.append(tbl(["#", "Test", "Pass criteria"], [
        ["T1", "Visual / AOI", "No bridges, all 56 parts present and oriented per section 1."],
        ["T2", "Power-up on USB 5 V", "Green PWR LED D3 on. Supply current 60-250 mA "
               "(WiFi access point running). FAIL if < 20 mA or > 400 mA."],
        ["T3", "Rails", "+3V3 at U6 pin 2 (tab): 3.30 +/- 0.10 V. +3.3VA at U7 pin 5: 3.30 +/- 0.10 V."],
        ["T4", "USB enumeration", "A USB serial device appears on the PC within 3 s of RESET."],
        ["T5", "Boot log (serial 115200)", "Lines <b>[imu] ok</b>, <b>[mag] ok</b>, <b>[baro] ok</b> "
               "must appear. <b>[sd] ok</b> when a FAT32 card is inserted (without a card "
               "[sd] FAIL is expected and acceptable). <b>[web] AP DroneMagNav</b> must appear."],
        ["T6", "WiFi", "SSID <b>DroneMagNav</b> visible; password <b>magnav123</b>; "
               "http://192.168.4.1/ loads the map page; http://192.168.4.1/api/status returns JSON "
               "with non-zero magnetic field and pressure values."],
        ["T7", "Buttons", "RESET repeats the boot log. BOOT held during RESET stops the boot log "
               "(download mode) - then RESET again to resume."],
        ["T8", "GNSS (optional)", "Antenna on J4, board near a window: blue FIX LED D5 on within "
               "3 min; /api/status shows a latitude/longitude."],
        ["T9", "LEDs D4 NAV and D6 LINK", "Off during this test (they need a flight controller / "
               "navigation mode). They must not be stuck on."],
    ], [12 * mm, 44 * mm, W - 56 * mm]))
    el.append(Spacer(1, 6))
    el.append(Paragraph(
        "Record per board: serial port seen, T2 current, T3 voltages, T5 log lines, T6 result. "
        "A board passing T1-T7 is a good unit.", P))
    doc.build(el)


def main():
    build_body()
    w = PdfWriter()
    for p in PdfReader(BODY).pages:
        w.add_page(p)
    if os.path.exists(DRAWING):
        for p in PdfReader(DRAWING).pages:
            w.add_page(p)
    else:
        print("NOTE: no KiCad drawing found at", DRAWING)
    with open(OUT, "wb") as f:
        w.write(f)
    print("wrote", OUT, f"({len(w.pages)} pages)")
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(OUT, os.path.basename(OUT))
        if os.path.exists(FW):
            z.write(FW, os.path.basename(FW))
        else:
            print("NOTE: firmware image not found:", FW)
    print("wrote", ZIP, os.path.getsize(ZIP) // 1024, "KB")


if __name__ == "__main__":
    main()
