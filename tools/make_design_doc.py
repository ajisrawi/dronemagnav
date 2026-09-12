"""Build the DroneMagNav design document PDF (styled, with diagrams)."""
import csv
import os
from datetime import date

from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph,
                                Spacer, Table, TableStyle, PageBreak,
                                NextPageTemplate, Image)
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon
from pypdf import PdfReader, PdfWriter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HW = os.path.join(ROOT, "hardware", "dronemagnav")
BODY_PDF = os.path.join(HW, "_design-doc-body.pdf")
SCH_PDF = os.path.join(HW, "dronemagnav-schematic.pdf")
OUT_PDF = os.path.join(ROOT, "DroneMagNav-Design-Document.pdf")

NAVY = HexColor("#14213D"); BLUE = HexColor("#2A6F97"); SKY = HexColor("#D6E6F2")
SLATE = HexColor("#5B6B7A"); LIGHT = HexColor("#EEF3F8"); LINE = HexColor("#C3D0DC")
AMBER = HexColor("#C8871E"); AMBER_L = HexColor("#F7EBD4"); GREEN = HexColor("#2E7D4F")
GREEN_L = HexColor("#DFEEE5"); INK = HexColor("#1C242C"); GRAY = HexColor("#8A97A3")

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm
USABLE = PAGE_W - 2 * MARGIN
DOC_TITLE = "DroneMagNav - Design Document"


def S(name, **kw):
    base = dict(fontName="Helvetica", fontSize=9.5, leading=13.5, textColor=INK,
                spaceAfter=5, alignment=TA_LEFT)
    base.update(kw)
    return ParagraphStyle(name, **base)


st_h1 = S("h1", fontName="Helvetica-Bold", fontSize=16, leading=20, textColor=NAVY,
          spaceBefore=14, spaceAfter=6)
st_h2 = S("h2", fontName="Helvetica-Bold", fontSize=11.5, leading=15, textColor=BLUE,
          spaceBefore=10, spaceAfter=4)
st_body = S("body")
st_bullet = S("bullet", leftIndent=10, spaceAfter=3)
st_caption = S("caption", fontSize=8, textColor=SLATE, alignment=TA_CENTER,
               spaceBefore=2, spaceAfter=10)
st_th = S("th", fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=white,
          spaceAfter=0)
st_td = S("td", fontSize=8.5, leading=11, spaceAfter=0)
st_td_b = S("td_b", fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=NAVY,
            spaceAfter=0)


def P(t, s=st_body):
    return Paragraph(t, s)


def bullets(items):
    return [Paragraph("-  " + t, st_bullet) for t in items]


def tbl(headers, rows, widths):
    data = [[Paragraph(h, st_th) for h in headers]]
    for r in rows:
        data.append([Paragraph(c, st_td_b if i == 0 else st_td) for i, c in enumerate(r)])
    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6)]))
    return t


def box(d, x, y, w, h, title, sub=None, fill=LIGHT, stroke=BLUE, fs=8.5, sub_fs=6.5):
    d.add(Rect(x, y, w, h, rx=4, ry=4, fillColor=fill, strokeColor=stroke, strokeWidth=1.1))
    cy = y + h / 2 + (3 if sub else -fs * 0.36)
    d.add(String(x + w / 2, cy, title, fontName="Helvetica-Bold", fontSize=fs,
                 fillColor=NAVY, textAnchor="middle"))
    if sub:
        yy = cy - 9
        for ln in (sub if isinstance(sub, list) else [sub]):
            d.add(String(x + w / 2, yy, ln, fontName="Helvetica", fontSize=sub_fs,
                         fillColor=SLATE, textAnchor="middle"))
            yy -= 8


def arrow(d, x1, y1, x2, y2, color=SLATE, both=False, label=None):
    import math
    d.add(Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=1.2))
    a = math.atan2(y2 - y1, x2 - x1)

    def head(px, py, ang):
        s = 5
        d.add(Polygon(points=[px, py, px - s * math.cos(ang - .42), py - s * math.sin(ang - .42),
                              px - s * math.cos(ang + .42), py - s * math.sin(ang + .42)],
                      fillColor=color, strokeColor=color, strokeWidth=.5))
    head(x2, y2, a)
    if both:
        head(x1, y1, a + math.pi)
    if label:
        d.add(String((x1 + x2) / 2, (y1 + y2) / 2 + 5, label, fontName="Helvetica-Oblique",
                     fontSize=6.5, fillColor=color, textAnchor="middle"))


def diagram_system():
    W, H = 493, 180
    d = Drawing(W, H)
    box(d, 4, 118, 90, 44, "Phone", ["WiFi AP page", "map · route · status"], fill=SKY)
    box(d, 130, 118, 100, 44, "DroneMagNav", ["ESP32-S3 board", "this design"],
        fill=GREEN_L, stroke=GREEN, fs=9)
    box(d, 270, 118, 96, 44, "Flight controller", ["ArduPilot / PX4", "MAVLink TELEM"],
        fill=SKY)
    box(d, 400, 118, 90, 44, "Radios / GNSS", ["u-blox on board", "for init + truth"],
        fill=LIGHT, stroke=SLATE)
    arrow(d, 94, 140, 130, 140, both=True, label="HTTP")
    arrow(d, 230, 140, 270, 140, both=True, label="GPS_INPUT / mission")
    arrow(d, 366, 140, 400, 140, both=True)
    box(d, 4, 40, 110, 50, "Sensors", ["LIS3MDL magnetometer", "BMI088 IMU", "BMP280 baro"],
        fill=AMBER_L, stroke=AMBER)
    box(d, 150, 40, 110, 50, "microSD maps", ["WDMAM anomaly grid", "WMM coefficients",
                                                "coastline + web UI"], fill=LIGHT, stroke=SLATE)
    box(d, 300, 40, 190, 50, "MagNav filter",
        ["Tolles-Lawson compensation -> particle filter", "measured field vs WMM + WDMAM",
         "-> position without GNSS"], fill=GREEN_L, stroke=GREEN)
    arrow(d, 59, 90, 160, 118)
    arrow(d, 205, 90, 180, 118)
    arrow(d, 395, 90, 200, 118)
    d.add(String(246, 12, "Signal path: sensors -> compensation -> particle filter against "
                 "the magnetic map -> position -> autopilot; route planned on the phone.",
                 fontName="Helvetica-Oblique", fontSize=7, fillColor=SLATE,
                 textAnchor="middle"))
    return d


def diagram_board():
    W, H = 493, 250
    d = Drawing(W, H)
    d.add(Rect(60, 20, 373, 220, rx=8, ry=8, fillColor=None, strokeColor=NAVY, strokeWidth=1.4))
    d.add(String(246, 244, "DroneMagNav PCB  64 x 60 mm, 4 layers", fontName="Helvetica-Bold",
                 fontSize=8, fillColor=NAVY, textAnchor="middle"))
    box(d, 190, 176, 116, 52, "ESP32-S3-WROOM-1", ["WiFi/BLE, USB, PSRAM", "antenna at top edge"],
        fill=SKY, fs=9)
    d.add(Rect(190, 228, 116, 10, fillColor=AMBER_L, strokeColor=AMBER, strokeWidth=.8))
    d.add(String(248, 231, "antenna keep-out", fontName="Helvetica", fontSize=5.5,
                 fillColor=AMBER, textAnchor="middle"))
    box(d, 66, 176, 60, 40, "Buttons", ["RESET · BOOT"], fill=LIGHT, stroke=SLATE)
    box(d, 66, 120, 60, 40, "USB-C", ["power + USB", "ESD protected"], fill=SKY)
    box(d, 340, 176, 88, 40, "GNSS", ["MAX-M10S", "U.FL antenna"], fill=LIGHT, stroke=SLATE)
    box(d, 340, 110, 88, 52, "microSD", ["SDMMC 4-bit", "map storage"], fill=LIGHT, stroke=SLATE)
    box(d, 190, 110, 60, 40, "BMI088", ["IMU"], fill=AMBER_L, stroke=AMBER)
    box(d, 258, 110, 60, 40, "BMP280", ["baro"], fill=AMBER_L, stroke=AMBER)
    box(d, 210, 48, 80, 40, "LIS3MDL", ["magnetometer", "away from LDOs"],
        fill=AMBER_L, stroke=AMBER)
    box(d, 66, 48, 100, 40, "Power", ["diode-OR 5 V in", "3V3 + 3.3VA LDOs"],
        fill=LIGHT, stroke=SLATE)
    box(d, 340, 40, 88, 40, "FC TELEM", ["JST-GH, MAVLink", "5 V in"], fill=SKY)
    box(d, 190, 24, 100, 18, "Sensor mast JST-GH (I2C)", fill=SKY, fs=6.5)
    for (hx, hy) in ((140, 204), (352, 204), (140, 60), (352, 60)):
        d.add(Rect(hx - 4, hy - 4, 8, 8, rx=4, ry=4, fillColor=white, strokeColor=NAVY))
    d.add(String(150, 8, "M3 holes on the 30.5 mm Pixhawk pattern", fontName="Helvetica-Oblique",
                 fontSize=6.5, fillColor=SLATE))
    return d


def diagram_filter():
    W, H = 493, 150
    d = Drawing(W, H)
    y, bh = 84, 40
    box(d, 4, y, 88, bh, "Magnetometer", ["Bx By Bz body frame", "80 Hz"], fill=AMBER_L, stroke=AMBER)
    box(d, 112, y, 96, bh, "Tolles-Lawson", ["18-term aircraft", "field compensation"],
        fill=LIGHT, stroke=SLATE)
    box(d, 228, y, 84, bh, "Scalar |B|", ["compensated nT"], fill=LIGHT, stroke=SLATE)
    box(d, 332, y, 156, bh, "Particle filter update", ["w_i *= exp(-(|B| - pred_i)^2 / 2s^2)",
                                                        "pred_i = WMM(p_i) + WDMAM(p_i) + bias"],
        fill=GREEN_L, stroke=GREEN)
    for xa, xb in ((92, 112), (208, 228), (312, 332)):
        arrow(d, xa, y + bh / 2, xb, y + bh / 2)
    y2 = 14
    box(d, 4, y2, 120, bh, "Velocity", ["FC GLOBAL_POSITION_INT", "or IMU dead reckoning"],
        fill=SKY)
    box(d, 150, y2, 130, bh, "Particle predict", ["p_i += v dt + noise", "600 particles"],
        fill=GREEN_L, stroke=GREEN)
    box(d, 310, y2, 178, bh, "Estimate", ["weighted mean lat/lon, 1-sigma",
                                          "resample when ESS < N/2 -> GPS_INPUT"],
        fill=SKY)
    arrow(d, 124, y2 + bh / 2, 150, y2 + bh / 2)
    arrow(d, 280, y2 + bh / 2, 310, y2 + bh / 2)
    arrow(d, 410, y, 400, y2 + bh)
    return d


def on_content_page(canv, doc):
    canv.saveState()
    canv.setStrokeColor(LINE); canv.setLineWidth(.6)
    canv.line(MARGIN, PAGE_H - 14 * mm, PAGE_W - MARGIN, PAGE_H - 14 * mm)
    canv.setFont("Helvetica", 7.5); canv.setFillColor(SLATE)
    canv.drawString(MARGIN, PAGE_H - 12.2 * mm, DOC_TITLE)
    canv.drawRightString(PAGE_W - MARGIN, PAGE_H - 12.2 * mm,
                         "Rev A · " + date.today().strftime("%d %b %Y"))
    canv.line(MARGIN, 13 * mm, PAGE_W - MARGIN, 13 * mm)
    canv.drawString(MARGIN, 9.5 * mm, "Prototype - not certified for any regulated use")
    canv.drawRightString(PAGE_W - MARGIN, 9.5 * mm, f"Page {doc.page}")
    canv.restoreState()


def on_cover_page(canv, doc):
    canv.saveState()
    canv.setFillColor(NAVY); canv.rect(0, PAGE_H - 118 * mm, PAGE_W, 118 * mm, stroke=0, fill=1)
    canv.setFillColor(AMBER); canv.rect(0, PAGE_H - 119.6 * mm, PAGE_W, 1.6 * mm, stroke=0, fill=1)
    canv.setFillColor(HexColor("#9FB8D0")); canv.setFont("Helvetica-Bold", 10)
    canv.drawString(MARGIN, PAGE_H - 40 * mm, "DESIGN DOCUMENT · REV A")
    canv.setFillColor(white); canv.setFont("Helvetica-Bold", 28)
    canv.drawString(MARGIN, PAGE_H - 54 * mm, "DroneMagNav")
    canv.setFont("Helvetica", 14); canv.setFillColor(HexColor("#D3E1EE"))
    canv.drawString(MARGIN, PAGE_H - 64 * mm,
                    "Magnetic-anomaly navigation board and route planner for drones")
    canv.setFont("Helvetica", 9.5)
    y = PAGE_H - 80 * mm
    for line in ("ESP32-S3  ·  BMI088 IMU  ·  LIS3MDL magnetometer  ·  BMP280  ·  u-blox MAX-M10S",
                 "WDMAM world anomaly map on microSD  ·  particle-filter MagNav  ·  MAVLink to the autopilot",
                 "Phone web app: offline world map, tap start/destination, great-circle route upload"):
        canv.drawString(MARGIN, y, line); y -= 6.5 * mm
    meta = [("Project", "DroneMagNav (GNSS-denied drone navigation)"),
            ("Revision", "A - schematic + routed PCB + firmware release"),
            ("Date", date.today().strftime("%d %B %Y")),
            ("Prepared by", "eng.ahmad@gmail.com · generated with KiCad 10"),
            ("Design status", "ERC clean · netlist verified · PCB routed, 0 electrical DRC"),
            ("Classification", "Prototype / experimental - not certified")]
    y = PAGE_H - 145 * mm
    canv.setStrokeColor(LINE); canv.setLineWidth(.6)
    for k, v in meta:
        canv.setFont("Helvetica-Bold", 9.5); canv.setFillColor(NAVY); canv.drawString(MARGIN, y, k)
        canv.setFont("Helvetica", 9.5); canv.setFillColor(INK); canv.drawString(MARGIN + 40 * mm, y, v)
        canv.line(MARGIN, y - 2.6 * mm, PAGE_W - MARGIN, y - 2.6 * mm); y -= 9 * mm
    canv.setFont("Helvetica", 8); canv.setFillColor(SLATE)
    canv.drawString(MARGIN, 20 * mm, "Appendix A contains the full KiCad schematic set (5 sheets, A3).")
    canv.restoreState()


def build_body():
    frame = Frame(MARGIN, 18 * mm, USABLE, PAGE_H - 38 * mm, id="f")
    cover = Frame(MARGIN, 15 * mm, USABLE, PAGE_H - 30 * mm, id="c")
    doc = BaseDocTemplate(BODY_PDF, pagesize=A4, title=DOC_TITLE, author="DroneMagNav Project")
    doc.addPageTemplates([PageTemplate(id="Cover", frames=[cover], onPage=on_cover_page),
                          PageTemplate(id="Content", frames=[frame], onPage=on_content_page)])
    el = [NextPageTemplate("Content"), Spacer(1, 1), PageBreak()]

    el.append(P("1   Executive summary", st_h1))
    el.append(P("DroneMagNav is a 64 x 60 mm navigation module for drones that estimates position "
                "<b>without GNSS</b> by matching the measured total magnetic field against the World "
                "Digital Magnetic Anomaly Map (WDMAM), fused with inertial dead reckoning in a "
                "particle filter. A u-blox GNSS receiver on the board initialises the filter and "
                "provides a truth reference; when GNSS is lost the MagNav estimate is streamed to "
                "the flight controller as a MAVLink <i>GPS_INPUT</i> source. A phone connects to the "
                "board's WiFi access point, shows an offline world map, and lets the operator tap a "
                "start and a destination; the board computes the shortest (great-circle) route and "
                "uploads it to the autopilot as a mission."))
    el.append(P("This release contains the complete KiCad schematic set, a routed four-layer PCB with "
                "manufacturing outputs, a bill of materials with part numbers, the ESP32-S3 firmware "
                "with the navigation algorithms and web interface, and the tools that convert the "
                "WDMAM data for the microSD card."))

    el.append(P("2   System architecture", st_h1))
    el.append(diagram_system())
    el.append(P("Figure 1 - System context", st_caption))
    el.append(P("The Earth's crustal magnetic anomalies form a fixed, GNSS-independent map. Subtracting "
                "the smooth core field (World Magnetic Model) from the compensated scalar "
                "measurement leaves the anomaly, which the particle filter compares with the WDMAM "
                "grid at every particle's position. The filter is drift-free but its resolution is "
                "bounded by the map: the 3-arc-minute WDMAM grid (upward-continued to 5 km) gives "
                "kilometre-class positioning; a local aeromagnetic survey loaded in the same format "
                "brings that to tens of metres at drone altitude."))

    el.append(PageBreak())
    el.append(P("3   Hardware design", st_h1))
    el.append(diagram_board())
    el.append(P("Figure 2 - Board floorplan", st_caption))
    el.append(tbl(["Block", "Part", "Notes"], [
        ["MCU / radio", "ESP32-S3-WROOM-1-N16R8", "16 MB flash, 8 MB PSRAM, WiFi/BLE, native USB; UART0 pads carry the GNSS"],
        ["Magnetometer", "LIS3MDL", "16-bit, +-4 gauss, ~40 nT after averaging; SPI"],
        ["IMU", "BMI088", "accel + gyro, drone grade; SPI, dual chip-select"],
        ["Barometer", "BMP280", "altitude input to the field model; SPI"],
        ["GNSS", "u-blox MAX-M10S + U.FL", "init and truth; PPS to GPIO16"],
        ["Storage", "microSD (Hirose DM3AT)", "SDMMC 4-bit, card detect"],
        ["Interfaces", "USB-C, JST-GH TELEM, JST-GH mast", "USBLC6 ESD; Pixhawk TELEM pinout; I2C mast for RM3100"],
        ["Power", "SS14 diode-OR, AMS1117-3.3, AP2112K-3.3", "digital 3V3 and low-noise 3.3VA sensor rail"]],
        [80, 130, USABLE - 210]))
    el.append(P("3.1  Magnetic cleanliness", st_h2))
    el.append(P("The magnetometer sits at the bottom centre, 14 mm from the regulators and away from "
                "the USB and SD connectors; the ESP32 antenna keep-out is respected in full. The "
                "dominant interference on a drone is the motors and ESC currents, which no board "
                "layout can remove: the firmware's Tolles-Lawson calibration models it, and the "
                "sensor-mast connector J5 allows an external RM3100 on a boom for survey-grade use."))

    el.append(P("4   Navigation algorithms", st_h1))
    el.append(diagram_filter())
    el.append(P("Figure 3 - MagNav particle filter dataflow", st_caption))
    el.extend(bullets([
        "<b>WMM core field:</b> degree-12 spherical-harmonic model evaluated per particle; coefficients read from the NOAA WMM.COF file on the card.",
        "<b>WDMAM map window:</b> 96 x 96 cells of the int16 nT world grid cached in PSRAM around the estimate, bilinear interpolation, seamless longitude wrap.",
        "<b>Tolles-Lawson:</b> 18 terms (permanent, induced, eddy) fitted by ridge-regularised least squares from a 3-minute calibration manoeuvre with GNSS; stored on the card.",
        "<b>Particle filter:</b> 600 particles (lat, lon, scalar bias); velocity from the flight controller or IMU; Gaussian likelihood with 40 nT sigma; systematic resampling with roughening.",
        "<b>Routing:</b> haversine distance, initial bearing, great-circle intermediate points at the chosen spacing; uploaded as NAV_TAKEOFF + NAV_WAYPOINT items."]))

    el.append(PageBreak())
    el.append(P("5   PCB implementation", st_h1))
    img = os.path.join(HW, "board-top.png")
    if os.path.exists(img):
        im = Image(img, width=USABLE * 0.72, height=USABLE * 0.72 * 0.95)
        im.hAlign = "CENTER"
        el.append(im)
        el.append(P("Figure 4 - Routed board, top side", st_caption))
    el.append(P("Four layers: signals on the outer layers, solid GND (In1) and +3V3 (In2) planes "
                "inside, both notched under the module antenna. Autorouted with Freerouting "
                "constrained to the outer layers and the keep-outs, then scripted power fanout to "
                "the planes and hand-verified routes for the GNSS UART and the I2C bus. Rules: "
                "0.2 mm track, 0.15 mm clearance, 0.45/0.2 mm vias. Power vias are dog-boned "
                "outside their pads (74 moved by tools/dogbone_vias.py); only three 0.4 mm vias "
                "remain in pads where the 0.5 mm-pitch BMI088 escapes and the microSD routing leave "
                "no room (U2 pads 2/4, J3 pad 4) and the fabrication notes require them to be filled "
                "and capped. Fab outputs: Gerbers, Excellon drill + map, pick-and-place, "
                "FABRICATION-NOTES.md, Gerber ZIP."))

    el.append(P("6   Bill of materials", st_h1))
    rows = []
    try:
        with open(os.path.join(ROOT, "docs", "BOM.csv"), encoding="utf-8-sig") as f:
            rd = csv.reader(f); next(rd)
            for r in rd:
                refs = r[0] if len(r[0]) <= 30 else r[0][:27] + "..."
                rows.append([refs, r[1], r[2], r[5]])
    except Exception:
        pass
    if rows:
        el.append(tbl(["References", "Qty", "Value", "Manufacturer P/N"], rows,
                      [140, 28, 90, USABLE - 258]))

    el.append(PageBreak())
    el.append(P("7   Firmware and phone interface", st_h1))
    el.append(P("PlatformIO / Arduino-ESP32 project (firmware/): register-level SPI drivers for the "
                "three sensors, NMEA parser for the GNSS, a minimal MAVLink v2 stack (heartbeat, "
                "GPS_INPUT, mission upload, position/velocity intake), the navigation modules above, "
                "and a WiFi access point serving the phone page from the card. Flashing is over "
                "USB-C (native USB bootloader, no programmer). The phone page draws the Natural "
                "Earth coastline offline, pans/zooms by touch, places START/DEST by tap, shows the "
                "great-circle line, distance and bearing, and uploads the mission."))
    el.append(tbl(["HTTP endpoint", "Purpose"], [
        ["GET /api/status", "mode, position, sigma, field, anomaly, heading, link states"],
        ["GET /api/route?lat1&lon1&lat2&lon2&alt&spacing", "great-circle waypoints, distance, bearing"],
        ["POST /api/upload", "send the last route to the flight controller as a mission"],
        ["GET /api/anom?lat&lon&span&n", "anomaly grid for the heat overlay"],
        ["POST /api/cal?start=1|0", "Tolles-Lawson calibration start/stop"],
        ["POST /api/init?lat&lon", "force MagNav mode from a known position"]],
        [200, USABLE - 200]))

    el.append(P("8   Verification", st_h1))
    el.append(tbl(["Check", "Tool", "Result"], [
        ["Electrical rule check (5 sheets)", "kicad-cli sch erc", "0 errors, 1 warning (BMI088 SDO1/SDO2 on MISO, per Bosch)"],
        ["Netlist connectivity, 21 critical nets", "tools/check_netlist.py", "21 / 21 pass"],
        ["PCB connectivity", "kicad-cli pcb drc", "0 unconnected pads"],
        ["PCB electrical rules", "kicad-cli pcb drc", "0 violations (22 silkscreen notes)"],
        ["WMM core-field evaluator vs NOAA WMM2025 test values", "tools/wmm_check.py",
         "100 / 100 points, worst error 0.001 nT"],
        ["WDMAM SD-card grid vs source file (7200 x 3601 cells, 51.9 MB)", "tools/wdmam_check.py",
         "225 sample cells identical, 100 % coverage"],
        ["MAX-M10S straps vs u-blox integration manual UBX-20053088 R05", "manual, table 1 / sec. 4.1",
         "VIO_SEL open = 3.3 V I/O (as built); TIMEPULSE-SAFEBOOT_N tie honoured in firmware"],
        ["Vias in pads after dog-bone pass", "tools/fab_audit.py",
         "3 in small pads (listed for fill & cap), 2 in thermal pads, 0 unconnected, 0 DRC"],
        ["Firmware", "-", "complete source; not yet compile-verified on hardware"]],
        [USABLE - 250, 110, 140]))

    el.append(P("9   Limitations and next steps", st_h1))
    el.extend(bullets([
        "WDMAM resolution and 5 km altitude limit stand-alone accuracy to kilometre class; add a local survey map for metres.",
        "LIS3MDL is adequate for the world grid; use an RM3100 on the mast connector for survey-grade work.",
        "Order the board with filled-and-capped vias (three vias-in-pad, see FABRICATION-NOTES.md in the Gerber ZIP).",
        "Build the firmware with PlatformIO, run the calibration flight, benchmark MagNav against GNSS before relying on it."]))
    el.append(Spacer(1, 10))
    el.append(P("Appendix A - Schematic sheets", st_h1))
    el.append(P("Root, power, MCU, sensors, GNSS + storage, interfaces - as plotted from KiCad. "
                "Every pin carries a drawn wire stub with its net label; the netlist is the "
                "authoritative artifact validated in Section 8."))
    doc.build(el)


def merge():
    w = PdfWriter()
    for p in PdfReader(BODY_PDF).pages:
        w.add_page(p)
    for p in PdfReader(SCH_PDF).pages:
        w.add_page(p)
    w.add_metadata({"/Title": DOC_TITLE, "/Author": "DroneMagNav Project"})
    out = OUT_PDF
    try:
        f = open(out, "wb")
    except PermissionError:
        out = OUT_PDF.replace(".pdf", "-revA.pdf")
        f = open(out, "wb")
    with f:
        w.write(f)
    print("wrote", out)


if __name__ == "__main__":
    build_body()
    merge()
