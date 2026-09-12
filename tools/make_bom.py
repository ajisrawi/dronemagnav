"""Generate the DroneMagNav BOM (CSV) from the exported KiCad netlist."""
import csv
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NETLIST = os.path.join(ROOT, "hardware", "dronemagnav", "netlist.net")
OUT_CSV = os.path.join(ROOT, "docs", "BOM.csv")

MPN = {
    ("ESP32-S3-WROOM-1-N16R8", "ESP32"): (
        "Espressif", "ESP32-S3-WROOM-1-N16R8",
        "WiFi/BLE module, 16 MB flash, 8 MB PSRAM, PCB antenna", ""),
    ("BMI088", "LGA-16"): (
        "Bosch", "BMI088", "6-axis IMU (accel + gyro), drone grade, LGA-16", ""),
    ("LIS3MDL", "LGA-12"): (
        "STMicroelectronics", "LIS3MDLTR",
        "3-axis magnetometer, 16-bit, LGA-12",
        "MagNav upgrade path: RM3100 on mast connector J5"),
    ("BMP280", "LGA-8"): (
        "Bosch", "BMP280", "Barometric pressure sensor, LGA-8", ""),
    ("MAX-M10S", "ublox_MAX"): (
        "u-blox", "MAX-M10S-00B", "GNSS receiver module, L1 multi-constellation",
        "Verify VIO_SEL strap per integration manual"),
    ("AMS1117-3.3", "SOT-223"): (
        "AMS / UMW", "AMS1117-3.3", "LDO 3.3 V 1 A, SOT-223", ""),
    ("AP2112K-3.3", "SOT-23-5"): (
        "Diodes Inc.", "AP2112K-3.3TRG1", "Low-noise LDO 3.3 V 600 mA, SOT-23-5", ""),
    ("USBLC6-2SC6", "SOT-23-6"): (
        "STMicroelectronics", "USBLC6-2SC6", "USB 2.0 ESD protection, SOT-23-6", ""),
    ("USB-C", "USB_C"): (
        "HRO", "TYPE-C-31-M-12", "USB-C receptacle, USB 2.0, 16-pin", ""),
    ("microSD", "microSD"): (
        "Hirose", "DM3AT-SF-PEJM5", "microSD card socket, push-push", ""),
    ("GNSS_ANT", "U.FL"): (
        "Hirose", "U.FL-R-SMT-1(10)", "U.FL RF connector for GNSS antenna", ""),
    ("FC_TELEM", "JST_GH"): (
        "JST", "SM06B-GHS-TB", "JST-GH 6-pin, Pixhawk TELEM pinout", ""),
    ("SENSOR_MAST", "JST_GH"): (
        "JST", "SM06B-GHS-TB", "JST-GH 6-pin, external sensor mast", ""),
    ("DEBUG_UART", "1x03"): (
        "generic", "PinHeader 1x03 2.54mm", "Debug UART header", ""),
    ("RESET", "PTS645"): (
        "C&K", "PTS645SM43SMTR92", "Tactile switch 6x6 SMD", ""),
    ("BOOT", "PTS645"): (
        "C&K", "PTS645SM43SMTR92", "Tactile switch 6x6 SMD", ""),
    ("SS14", "D_SMA"): (
        "Vishay / MDD", "SS14", "Schottky diode 40 V 1 A, SMA", ""),
    ("PWR", "LED_0603"): ("Everlight", "19-217/GHC-YR1S2/3T", "LED green 0603", ""),
    ("NAV", "LED_0603"): ("Everlight", "19-217/GHC-YR1S2/3T", "LED green 0603", ""),
    ("FIX", "LED_0603"): ("Everlight", "19-217/BHC-ZL1M2RY/3T", "LED blue 0603", ""),
    ("LINK", "LED_0603"): ("Everlight", "19-217/Y2C-CQ2R2L/3T", "LED yellow 0603", ""),
}
GENERIC = {
    ("R", "R_0603"): ("Yageo", "RC0603FR-07{val}L", "Resistor {val} 1% 0603", ""),
    ("C", "C_0603"): ("Samsung", "CL10 series", "Capacitor {val} X7R 0603", ""),
    ("C", "C_0805"): ("Samsung", "CL21 series", "Capacitor {val} X5R 0805", ""),
}


def parse_components(path):
    text = open(path, encoding="utf-8").read()
    return [(m.group(1), m.group(2), m.group(3) or "") for m in re.finditer(
        r'\(comp\s+\(ref "([^"]+)"\)\s+\(value "([^"]+)"\)\s+'
        r'(?:\(footprint "([^"]*)"\))?', text)]


def match_mpn(ref, value, footprint):
    for (val, fptail), info in MPN.items():
        if value == val and fptail in footprint:
            return info
    prefix = re.match(r'[A-Za-z]+', ref).group(0)
    kind = "R" if prefix == "R" else "C" if prefix == "C" else None
    if kind:
        for (k, fptail), info in GENERIC.items():
            if k == kind and fptail in footprint:
                mfr, mpn, desc, note = info
                return (mfr, mpn.replace("{val}", value),
                        desc.replace("{val}", value), note)
    return ("", "TBD", value, "no MPN assigned")


def main():
    groups = {}
    for ref, value, fp in parse_components(NETLIST):
        if ref.startswith("#"):
            continue
        info = match_mpn(ref, value, fp)
        key = (value, fp, info[1])
        groups.setdefault(key, {"refs": [], "info": info, "value": value,
                                "fp": fp})["refs"].append(ref)

    def refkey(r):
        m = re.match(r'([A-Za-z]+)(\d+)', r)
        return (m.group(1), int(m.group(2)))

    rows = []
    for g in groups.values():
        refs = sorted(g["refs"], key=refkey)
        mfr, mpn, desc, note = g["info"]
        rows.append([", ".join(refs), len(refs), g["value"], desc, mfr, mpn,
                     g["fp"].split(":")[-1], note])
    rows.sort(key=lambda r: refkey(r[0].split(",")[0]))
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["References", "Qty", "Value", "Description", "Manufacturer",
                    "MPN", "Footprint", "Notes"])
        w.writerows(rows)
    print(f"BOM: {len(rows)} line items, {sum(r[1] for r in rows)} components")
    for r in rows:
        if r[5] == "TBD":
            print("  TBD:", r[0], r[2])


if __name__ == "__main__":
    main()
