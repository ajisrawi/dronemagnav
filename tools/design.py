"""DroneMagNav - magnetic-anomaly navigation board for drones.

Generates the KiCad project in hardware/dronemagnav/:
  root, power, mcu, sensors, gnss_storage, interfaces sheets.

Architecture:
  ESP32-S3-WROOM-1 (WiFi/BLE, USB)  <-SPI->  BMI088 IMU + LIS3MDL mag + BMP280 baro
                                    <-SDMMC-> microSD (WDMAM tiles + world map)
                                    <-UART->  u-blox MAX-M10S GNSS (init / truth)
                                    <-UART->  flight controller (MAVLink, JST-GH)
                                    <-I2C->   sensor-mast connector (external RM3100)
  Power: USB-C VBUS or FC 5 V -> diode-OR -> AMS1117-3.3 (digital) + AP2112 (sensors)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from kicad_gen import (SymbolLibrary, Sheet, Part, render_sheet, connect_part,
                       pin_endpoint, new_uuid, fmt)

PROJECT = "dronemagnav"
OUTDIR = os.path.join(os.path.dirname(__file__), "..", "hardware", PROJECT)

R_0603 = "Resistor_SMD:R_0603_1608Metric"
C_0603 = "Capacitor_SMD:C_0603_1608Metric"
C_0805 = "Capacitor_SMD:C_0805_2012Metric"
LED_0603 = "LED_SMD:LED_0603_1608Metric"
JST6 = "Connector_JST:JST_GH_SM06B-GHS-TB_1x06-1MP_P1.25mm_Horizontal"

libdb = SymbolLibrary()
ROOT_UUID = new_uuid()


def tie_power(sheet, pname, x, y):
    sheet.power.append((pname, x, y, 0.0))


def pin_pt(part, pin_no):
    sym = libdb.get(part.lib, part.name)
    for p in sym.pins:
        if p['number'] == pin_no:
            return pin_endpoint(sym, part.x, part.y, p)
    raise KeyError(pin_no)


def build_power():
    sh = Sheet("power.kicad_sch", "Power - USB/FC 5V in, 3V3 digital + 3V3A sensor rails",
               PROJECT)
    P = []
    d1 = Part("D1", "Device", "D_Schottky", "SS14", 60, 60,
              {"2": "VBUS", "1": "#+5V"}, "Diode_SMD:D_SMA")
    d2 = Part("D2", "Device", "D_Schottky", "SS14", 60, 80,
              {"2": "5V_FC", "1": "#+5V"}, "Diode_SMD:D_SMA")
    P += [d1, d2]
    P.append(Part("C1", "Device", "C", "10uF", 90, 70, {"1": "#+5V", "2": "#GND"},
                  C_0805))
    P.append(Part("U6", "Regulator_Linear", "AMS1117-3.3", "AMS1117-3.3", 130, 60,
                  {"VI": "#+5V", "VO": "#+3V3", "GND": "#GND"},
                  "Package_TO_SOT_SMD:SOT-223-3_TabPin2"))
    P.append(Part("C2", "Device", "C", "10uF", 155, 70, {"1": "#+3V3", "2": "#GND"},
                  C_0805))
    P.append(Part("C3", "Device", "C", "100nF", 167.5, 70, {"1": "#+3V3", "2": "#GND"},
                  C_0603))
    P.append(Part("U7", "Regulator_Linear", "AP2112K-3.3", "AP2112K-3.3", 130, 110,
                  {"VIN": "#+5V", "EN": "#+5V", "GND": "#GND", "NC": "NC",
                   "VOUT": "#+3.3VA"}, "Package_TO_SOT_SMD:SOT-23-5"))
    P.append(Part("C4", "Device", "C", "1uF", 105, 125, {"1": "#+5V", "2": "#GND"},
                  C_0603))
    P.append(Part("C5", "Device", "C", "10uF", 155, 125, {"1": "#+3.3VA", "2": "#GND"},
                  C_0805))
    P.append(Part("C6", "Device", "C", "100nF", 167.5, 125,
                  {"1": "#+3.3VA", "2": "#GND"}, C_0603))
    P.append(Part("R1", "Device", "R", "1K", 200, 60, {"1": "#+3V3", "2": "PWR_LED_A"},
                  R_0603))
    P.append(Part("D3", "Device", "LED", "PWR", 215, 75, {"2": "PWR_LED_A", "1": "#GND"},
                  LED_0603))
    for p in P:
        sh.add(p)
        connect_part(sh, libdb, p, nc_rest=True)
    tie_power(sh, "PWR_FLAG", *pin_pt(d1, "2"))    # VBUS
    tie_power(sh, "PWR_FLAG", *pin_pt(d2, "2"))    # 5V_FC
    tie_power(sh, "PWR_FLAG", *pin_pt(d1, "1"))    # +5V
    tie_power(sh, "PWR_FLAG", *pin_pt(P[2], "2"))  # GND (C1 bottom)
    sh.texts.append(("Two 5 V sources diode-ORed: USB-C VBUS (bench) and the flight-"
                     "controller TELEM port (5V_FC, in flight). SS14 drop ~0.35 V.",
                     30, 160, 2.0))
    sh.texts.append(("AMS1117 (1 A) feeds ESP32/SD/GNSS; AP2112K (low-noise LDO) "
                     "feeds the IMU/magnetometer/baro on the +3V3A rail.", 30, 167, 2.0))
    return sh


def build_mcu():
    sh = Sheet("mcu.kicad_sch", "MCU - ESP32-S3-WROOM-1 (WiFi/BLE, USB, SDMMC, SPI)",
               PROJECT)
    P = []
    P.append(Part("U1", "RF_Module", "ESP32-S3-WROOM-1", "ESP32-S3-WROOM-1-N16R8",
                  200, 120, {
                      "3V3": "#+3V3", "GND": "#GND",
                      "EN": "EN", "IO0": "BOOT",
                      "USB_D-": "USB_DN", "USB_D+": "USB_DP",
                      "TXD0": "GNSS_RXD", "RXD0": "GNSS_TXD",
                      # SPI sensor bus
                      "IO12": "SPI_SCK", "IO11": "SPI_MOSI", "IO13": "SPI_MISO",
                      "IO10": "CS_ACC", "IO9": "CS_GYR", "IO14": "CS_MAG",
                      "IO21": "CS_BARO",
                      "IO6": "INT_ACC", "IO7": "INT_GYR", "IO8": "MAG_DRDY",
                      # UARTs
                      "IO17": "NC", "IO18": "NC", "IO16": "GNSS_PPS",
                      "IO4": "FC_RXD", "IO5": "FC_TXD",
                      # I2C mast bus
                      "IO1": "I2C_SDA", "IO2": "I2C_SCL", "IO3": "MAST_INT",
                      # SDMMC 4-bit
                      "IO38": "SD_CLK", "IO39": "SD_CMD", "IO40": "SD_D0",
                      "IO41": "SD_D1", "IO42": "SD_D2", "IO47": "SD_D3",
                      "IO48": "SD_DET",
                      # LEDs
                      "IO35": "LED_NAV", "IO36": "LED_FIX", "IO37": "LED_LINK",
                      "IO15": "NC", "IO45": "NC", "IO46": "NC",
                  }, "RF_Module:ESP32-S3-WROOM-1"))
    P.append(Part("R2", "Device", "R", "10K", 100, 60, {"1": "#+3V3", "2": "EN"}, R_0603))
    P.append(Part("C7", "Device", "C", "1uF", 115, 60, {"1": "EN", "2": "#GND"}, C_0603))
    P.append(Part("SW1", "Switch", "SW_Push", "RESET", 100, 85, {"1": "EN", "2": "#GND"},
                  "Button_Switch_SMD:SW_SPST_PTS645Sx43SMTR92"))
    P.append(Part("R3", "Device", "R", "10K", 100, 110, {"1": "#+3V3", "2": "BOOT"},
                  R_0603))
    P.append(Part("SW2", "Switch", "SW_Push", "BOOT", 100, 135,
                  {"1": "BOOT", "2": "#GND"},
                  "Button_Switch_SMD:SW_SPST_PTS645Sx43SMTR92"))
    P.append(Part("C8", "Device", "C", "10uF", 260, 60, {"1": "#+3V3", "2": "#GND"},
                  C_0805))
    P.append(Part("C9", "Device", "C", "100nF", 272.5, 60, {"1": "#+3V3", "2": "#GND"},
                  C_0603))
    x = 260
    for i, (net, val) in enumerate([("LED_NAV", "NAV"), ("LED_FIX", "FIX"),
                                    ("LED_LINK", "LINK")]):
        P.append(Part(f"R{4 + i}", "Device", "R", "330R", x + 15 * i, 100,
                      {"1": net, "2": f"{val}_LED_A"}, R_0603))
        P.append(Part(f"D{4 + i}", "Device", "LED", val, x + 15 * i, 120,
                      {"2": f"{val}_LED_A", "1": "#GND"}, LED_0603))
    P.append(Part("R7", "Device", "R", "4.7K", 100, 165, {"1": "#+3V3", "2": "I2C_SDA"},
                  R_0603))
    P.append(Part("R8", "Device", "R", "4.7K", 115, 165, {"1": "#+3V3", "2": "I2C_SCL"},
                  R_0603))
    for i, net in enumerate(["SD_CMD", "SD_D0", "SD_D1", "SD_D2", "SD_D3", "SD_DET"]):
        P.append(Part(f"R{9 + i}", "Device", "R", "10K", 260 + 12.5 * i, 165,
                      {"1": "#+3V3", "2": net}, R_0603))
    for p in P:
        sh.add(p)
        connect_part(sh, libdb, p, nc_rest=True)
    sh.texts.append(("ESP32-S3 N16R8: 16 MB flash, 8 MB PSRAM (map tiles + particle "
                     "filter), WiFi AP serves the phone UI, native USB for flashing.",
                     30, 230, 2.0))
    sh.texts.append(("SPI @10 MHz to IMU/mag/baro; SDMMC 4-bit to microSD; UART0 pads (GPIO43/44) GNSS; "
                     "UART2 MAVLink to flight controller; I2C to external sensor mast.",
                     30, 237, 2.0))
    return sh


def build_sensors():
    sh = Sheet("sensors.kicad_sch", "Sensors - BMI088 IMU, LIS3MDL magnetometer, BMP280 baro",
               PROJECT)
    P = []
    P.append(Part("U2", "Sensor_Motion", "BMI088", "BMI088", 90, 80, {
        "VDD": "#+3.3VA", "VDDIO": "#+3.3VA", "GNDA": "#GND", "GNDIO": "#GND",
        "PS": "#GND",
        "SCK/SCL": "SPI_SCK", "SDI/SDA": "SPI_MOSI",
        "SDO1": "SPI_MISO", "SDO2": "SPI_MISO",
        "~{CSB1}": "CS_ACC", "~{CSB2}": "CS_GYR",
        "INT1": "INT_ACC", "INT3": "INT_GYR", "INT2": "NC", "INT4": "NC",
    }, "Package_LGA:Bosch_LGA-16_4.5x3mm_P0.5mm_LayoutBorder7x1y_ClockwisePinNumbering"))
    P.append(Part("C10", "Device", "C", "100nF", 60, 120, {"1": "#+3.3VA", "2": "#GND"},
                  C_0603))
    P.append(Part("C11", "Device", "C", "100nF", 72.5, 120, {"1": "#+3.3VA", "2": "#GND"},
                  C_0603))
    P.append(Part("U3", "Sensor_Magnetic", "LIS3MDL", "LIS3MDL", 200, 80, {
        "Vdd": "#+3.3VA", "Vdd_IO": "#+3.3VA", "GND": "#GND",
        "C1": "MAG_C1",
        "SCL/SPC": "SPI_SCK", "SDA/SDI/SDO": "SPI_MOSI", "SDO/SA1": "SPI_MISO",
        "~{CS}": "CS_MAG", "DRDY": "MAG_DRDY", "INT": "NC",
    }, "Package_LGA:LGA-12_2x2mm_P0.5mm"))
    P.append(Part("C12", "Device", "C", "100nF", 230, 120, {"1": "MAG_C1", "2": "#GND"},
                  C_0603))
    P.append(Part("C13", "Device", "C", "100nF", 242.5, 120, {"1": "#+3.3VA", "2": "#GND"},
                  C_0603))
    P.append(Part("U4", "Sensor_Pressure", "BMP280", "BMP280", 300, 80, {
        "VDD": "#+3.3VA", "VDDIO": "#+3.3VA", "GND": "#GND",
        "CSB": "CS_BARO", "SDI": "SPI_MOSI", "SDO": "SPI_MISO", "SCK": "SPI_SCK",
    }, "Package_LGA:Bosch_LGA-8_2x2.5mm_P0.65mm_ClockwisePinNumbering"))
    P.append(Part("C14", "Device", "C", "100nF", 330, 120, {"1": "#+3.3VA", "2": "#GND"},
                  C_0603))
    P.append(Part("C15", "Device", "C", "10uF", 342.5, 120, {"1": "#+3.3VA", "2": "#GND"},
                  C_0805))
    for p in P:
        sh.add(p)
        connect_part(sh, libdb, p, nc_rest=True)
    sh.texts.append(("All three sensors share SPI (PS=GND on BMI088 selects SPI). "
                     "LIS3MDL: 16-bit, +-4 gauss, ~3 mG rms @80 Hz -> ~40 nT after "
                     "averaging: adequate for low-altitude anomaly matching.",
                     30, 160, 2.0))
    sh.texts.append(("Keep the magnetometer >= 10 mm from switching parts and away from "
                     "ESC/motor leads. MagNav-grade upgrade: RM3100 on the mast "
                     "connector J5 (I2C).", 30, 167, 2.0))
    return sh


def build_gnss_storage():
    sh = Sheet("gnss_storage.kicad_sch", "GNSS (u-blox MAX-M10S) and microSD map storage",
               PROJECT)
    P = []
    P.append(Part("U5", "RF_GPS", "MAX-M10S", "MAX-M10S", 100, 80, {
        "GND": "#GND", "VCC": "#+3V3", "VCC_IO": "#+3V3", "V_BCKP": "#+3V3",
        "TXD": "GNSS_TXD", "RXD": "GNSS_RXD", "TIMEPULSE": "GNSS_PPS",
        "RF_IN": "GNSS_RF", "~{RESET}": "GNSS_NRST",
        "EXTINT": "NC", "~{SAFEBOOT}": "NC", "LNA_EN": "NC", "VCC_RF": "NC",
        "VIO_SEL": "NC", "SDA": "NC", "SCL": "NC",
    }, "RF_GPS:ublox_MAX"))
    P.append(Part("R15", "Device", "R", "10K", 60, 130, {"1": "#+3V3", "2": "GNSS_NRST"},
                  R_0603))
    P.append(Part("C16", "Device", "C", "10uF", 130, 130, {"1": "#+3V3", "2": "#GND"},
                  C_0805))
    P.append(Part("C17", "Device", "C", "100nF", 142.5, 130, {"1": "#+3V3", "2": "#GND"},
                  C_0603))
    P.append(Part("J4", "Connector", "Conn_Coaxial", "GNSS_ANT", 160, 80,
                  {"1": "GNSS_RF", "2": "#GND"},
                  "Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical"))
    P.append(Part("J3", "Connector", "Micro_SD_Card_Det2", "microSD",
                  260, 80, {
                      "DAT2": "SD_D2", "DAT3/CD": "SD_D3", "CMD": "SD_CMD",
                      "VDD": "#+3V3", "CLK": "SD_CLK", "VSS": "#GND",
                      "DAT0": "SD_D0", "DAT1": "SD_D1",
                      "DET_B": "SD_DET", "DET_A": "#GND", "SHIELD": "#GND",
                  }, "Connector_Card:microSD_HC_Hirose_DM3AT-SF-PEJM5"))
    P.append(Part("C18", "Device", "C", "10uF", 300, 130, {"1": "#+3V3", "2": "#GND"},
                  C_0805))
    for p in P:
        sh.add(p)
        connect_part(sh, libdb, p, nc_rest=True)
    sh.texts.append(("MAX-M10S: passive antenna on U.FL J4 (50 ohm trace, keep short). "
                     "V_BCKP tied to 3V3 (no backup cell; hot start not retained).",
                     30, 165, 2.0))
    sh.texts.append(("VIO_SEL left open = default I/O level; verify against the "
                     "u-blox MAX-M10S integration manual before production.",
                     30, 172, 2.0))
    sh.texts.append(("microSD holds the WDMAM anomaly tiles (~500 MB world), the WMM "
                     "coefficients, the offline coastline map and the phone web UI.",
                     30, 179, 2.0))
    return sh


def build_interfaces():
    sh = Sheet("interfaces.kicad_sch", "Interfaces - USB-C, flight controller, sensor mast",
               PROJECT)
    P = []
    j1 = Part("J1", "Connector", "USB_C_Receptacle_USB2.0_16P", "USB-C", 80, 80, {
        "VBUS": "VBUS", "GND": "#GND", "SHIELD": "#GND",
        "CC1": "CC1", "CC2": "CC2",
        "D+": "USB_DP_RAW", "D-": "USB_DN_RAW",
        "SBU1": "NC", "SBU2": "NC",
    }, "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12")
    P.append(j1)
    P.append(Part("R16", "Device", "R", "5.1K", 130, 60, {"1": "CC1", "2": "#GND"},
                  R_0603))
    P.append(Part("R17", "Device", "R", "5.1K", 142.5, 60, {"1": "CC2", "2": "#GND"},
                  R_0603))
    P.append(Part("U8", "Power_Protection", "USBLC6-2P6", "USBLC6-2SC6", 160, 100, {
        "1": "USB_DP_RAW", "6": "USB_DP", "3": "USB_DN_RAW", "4": "USB_DN",
        "5": "VBUS", "2": "#GND",
    }, "Package_TO_SOT_SMD:SOT-23-6"))
    j2 = Part("J2", "Connector_Generic", "Conn_01x06", "FC_TELEM", 240, 80, {
        "1": "5V_FC", "2": "FC_TXD", "3": "FC_RXD", "4": "NC", "5": "NC",
        "6": "#GND",
    }, JST6)
    P.append(j2)
    P.append(Part("J5", "Connector_Generic", "Conn_01x06", "SENSOR_MAST", 240, 130, {
        "1": "#+3.3VA", "2": "#GND", "3": "I2C_SDA", "4": "I2C_SCL",
        "5": "MAST_INT", "6": "#+5V",
    }, JST6))
    for p in P:
        sh.add(p)
        connect_part(sh, libdb, p, nc_rest=True)
    sh.texts.append(("J2 follows the Pixhawk TELEM pinout (VCC, TX, RX, CTS, RTS, GND): "
                     "pin 2 = FC transmit -> our FC_TXD input; pin 3 = our transmit.",
                     30, 175, 2.0))
    sh.texts.append(("J5 sensor mast: powers and reads an external RM3100 / second "
                     "magnetometer mounted away from motors for MagNav-grade noise.",
                     30, 182, 2.0))
    return sh


def render_root(sheets):
    out = ['(kicad_sch (version 20231120) (generator "dronemagnav_gen")',
           f'  (uuid "{ROOT_UUID}")', '  (paper "A3")', '  (title_block',
           '    (title "DroneMagNav - magnetic anomaly navigation board for drones")',
           '    (company "DroneMagNav Project")', '    (rev "A")',
           '    (comment 1 "ESP32-S3 + BMI088 + LIS3MDL + BMP280 + MAX-M10S + microSD")',
           '  )', '  (lib_symbols)']
    x = 40
    for i, sh in enumerate(sheets):
        out.append(f'''  (sheet (at {fmt(x)} 60) (size 50 30) (fields_autoplaced yes)
    (stroke (width 0.1524) (type solid)) (fill (color 0 0 0 0.0000))
    (uuid "{sh.uuid}")
    (property "Sheetname" "{sh.title.split(' - ')[0]}" (at {fmt(x)} 58 0)
      (effects (font (size 1.27 1.27)) (justify left bottom)))
    (property "Sheetfile" "{sh.filename}" (at {fmt(x)} 92 0)
      (effects (font (size 1.27 1.27)) (justify left top)))
    (instances (project "{PROJECT}" (path "/{ROOT_UUID}" (page "{i + 2}"))))
  )''')
        x += 70
    notes = [
        ("MagNav: measure Earth's crustal magnetic anomaly with the magnetometer, "
         "subtract the core field (WMM), match against the WDMAM map on the SD card", 40, 130),
        ("with a particle filter fused with IMU dead-reckoning -> GNSS-denied position. "
         "GNSS module gives initialisation and truth for testing.", 40, 137),
        ("Phone UI over WiFi AP: pick start/destination on the offline map, "
         "great-circle route + waypoints sent to the flight controller (MAVLink).",
         40, 148),
        ("Prototype hardware - not certified for any regulated use.", 40, 159),
    ]
    for t, tx, ty in notes:
        out.append(f'  (text "{t}" (exclude_from_sim no) (at {fmt(tx)} {fmt(ty)} 0)'
                   f' (effects (font (size 2 2)) (justify left bottom))'
                   f' (uuid "{new_uuid()}"))')
    out.append('  (sheet_instances (path "/" (page "1")))')
    out.append(')')
    return '\n'.join(out)


def write_pro():
    pro = {
        "board": {"design_settings": {"rules": {"min_clearance": 0.15, "min_connection": 0.0, "min_copper_edge_clearance": 0.5, "min_hole_clearance": 0.25, "min_hole_to_hole": 0.2, "min_microvia_diameter": 0.2, "min_microvia_drill": 0.1, "min_resolved_spokes": 1, "min_silk_clearance": 0.0, "min_text_height": 0.8, "min_text_thickness": 0.08, "min_through_hole_diameter": 0.2, "min_track_width": 0.2, "min_via_annular_width": 0.1, "min_via_diameter": 0.4, "solder_mask_to_copper_clearance": 0.0, "use_height_for_length_calcs": True}}, "layer_presets": [], "viewports": []},
        "boards": [], "cvpcb": {"equivalence_files": []},
        "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
        "meta": {"filename": f"{PROJECT}.kicad_pro", "version": 1},
        "net_settings": {"classes": [{
            "name": "Default", "priority": 2147483647,
            "clearance": 0.15, "track_width": 0.2,
            "via_diameter": 0.6, "via_drill": 0.3,
            "microvia_diameter": 0.3, "microvia_drill": 0.1,
            "diff_pair_width": 0.2, "diff_pair_gap": 0.25,
            "diff_pair_via_gap": 0.25, "bus_width": 12, "line_style": 0,
            "pcb_color": "rgba(0, 0, 0, 0.000)",
            "schematic_color": "rgba(0, 0, 0, 0.000)", "wire_width": 6}],
            "meta": {"version": 3}},
        "pcbnew": {"last_paths": {}, "page_layout_descr_file": ""},
        "schematic": {"annotate_start_num": 0,
                      "drawing": {"default_line_thickness": 6.0,
                                  "default_text_size": 50.0,
                                  "label_size_ratio": 0.375},
                      "legacy_lib_dir": "", "legacy_lib_list": [],
                      "meta": {"version": 1}, "net_format_name": "",
                      "page_layout_descr_file": "", "plot_directory": "",
                      "spice_current_sheet_as_root": False,
                      "spice_external_command": "spice \"%I\"",
                      "spice_model_current_sheet_as_root": True,
                      "spice_save_all_currents": False,
                      "spice_save_all_voltages": False,
                      "subpart_first_id": 65, "subpart_id_separator": 0},
        "erc": {"erc_exclusions": [], "meta": {"version": 0}, "pin_map": [[0,0,0,0,0,0,1,0,0,0,0,2],[0,1,0,1,0,0,1,0,2,2,2,2],[0,0,0,0,0,0,1,0,0,0,0,2],[0,1,0,0,0,0,1,1,2,1,1,2],[0,0,0,0,0,0,1,0,0,0,0,2],[0,0,0,0,0,0,0,0,0,0,0,2],[1,1,1,1,1,0,1,1,1,1,1,2],[0,0,0,1,0,0,1,0,0,0,0,2],[0,2,0,2,0,0,1,0,2,2,2,2],[0,2,0,1,0,0,1,0,2,0,0,2],[0,2,0,1,0,0,1,0,2,0,0,2],[2,2,2,2,2,2,2,2,2,2,2,2]], "rule_severities": {}}, "sheets": [], "text_variables": {},
    }
    with open(os.path.join(OUTDIR, f"{PROJECT}.kicad_pro"), "w", encoding="utf-8") as f:
        json.dump(pro, f, indent=2)


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    sheets = [build_power(), build_mcu(), build_sensors(), build_gnss_storage(),
              build_interfaces()]
    for i, sh in enumerate(sheets):
        with open(os.path.join(OUTDIR, sh.filename), "w", encoding="utf-8") as f:
            f.write(render_sheet(sh, libdb, ROOT_UUID, sh.uuid, i + 2))
        print("wrote", sh.filename, f"({len(sh.parts)} parts, {len(sh.labels)} labels)")
    with open(os.path.join(OUTDIR, f"{PROJECT}.kicad_sch"), "w", encoding="utf-8") as f:
        f.write(render_root(sheets))
    write_pro()
    print("wrote root +", f"{PROJECT}.kicad_pro")


if __name__ == "__main__":
    main()

