# DroneMagNav — magnetic-anomaly navigation board for drones

GNSS-denied positioning from the Earth's crustal magnetic field, plus a
phone-operated great-circle route planner.

```
  LIS3MDL magnetometer ─┐                          ┌─ WDMAM anomaly map (SD)
  BMI088 IMU ───────────┼─ ESP32-S3 ─ particle ────┤  WMM core field model
  BMP280 baro ──────────┘   filter    matching     └─ Tolles-Lawson compensation
        │                        │
   u-blox GNSS (init/truth)      ├─ MAVLink GPS_INPUT → flight controller
                                 └─ WiFi AP → phone: offline map, route, upload
```

## Deliverables

| Item | Where | Status |
|---|---|---|
| Schematics (5 sheets) | `hardware/dronemagnav/*.kicad_sch`, `dronemagnav-schematic.pdf` | ERC 0 errors (1 intended warning) |
| PCB 64 × 60 mm, 4-layer, 30.5 mm Pixhawk hole pattern | `hardware/dronemagnav/dronemagnav.kicad_pcb` | routed, 0 unconnected, 0 electrical DRC |
| Fab package | `hardware/dronemagnav/fab/` (Gerber ZIP, drill, pick-and-place) | ready to upload |
| BOM | `docs/BOM.csv` | 28 line items, 56 parts, MPNs |
| Firmware (ESP32-S3, PlatformIO) | `firmware/` | complete source; WMM core-field model validated 100/100 against NOAA test vectors (0.001 nT) |
| Phone UI | `firmware/sdcard/www/index.html` | offline map, tap-to-route, upload |
| SD-card preparation | `tools/prepare_sd.py` | WDMAM → binary grid, WMM, coastline |
| Design document | `DroneMagNav-Design-Document.pdf` | study, diagrams, PCB, BOM, verification |

## Hardware
| Block | Part | Why |
|---|---|---|
| MCU / radio | ESP32-S3-WROOM-1-N16R8 | WiFi AP for the phone page, BLE, native USB, 8 MB PSRAM for map tiles + particle filter |
| Magnetometer | LIS3MDL (SPI) | 16-bit, ~40 nT after averaging; RM3100 upgrade via mast connector J5 |
| IMU | BMI088 (SPI) | drone-grade accel + gyro, vibration-robust |
| Barometer | BMP280 (SPI) | altitude for the field model |
| GNSS | u-blox MAX-M10S + U.FL | initialisation and truth reference |
| Storage | microSD (SDMMC 4-bit) | world anomaly map, WMM, coastline, web page |
| Interfaces | USB-C, JST-GH TELEM (MAVLink, 5 V in), JST-GH sensor mast (I2C) | Pixhawk-standard |
| Power | USB/FC 5 V → AMS1117-3.3 (digital) + AP2112K-3.3 (sensors) | separate clean sensor rail |

## How it navigates
1. **Compensate** the scalar field for the drone's own magnetism (18-term
   Tolles-Lawson, fitted once in flight with GNSS).
2. **Predict** position with the flight controller's velocity (or IMU dead
   reckoning) in a 600-particle filter.
3. **Update** each particle against *WMM core field + WDMAM anomaly* at the
   particle's location; resample; output mean and 1-σ.
4. **Feed** the estimate to the autopilot as `GPS_INPUT` when GNSS is lost.

**Expectations, honestly:** the WDMAM world grid is 3 arc-min (~5 km) and
upward-continued to 5 km, so with it alone you get drift-free
*kilometre-class* positioning — right for oceanic/jammed cruise, not landing.
Load a local aeromagnetic survey (`/maps/local.bin`, same format) for tens of
metres at drone altitude.

## Routing
The phone page shows an offline world coastline, you tap START and DEST, the
board computes the **great-circle** (shortest) path as evenly spaced waypoints
and uploads them to the flight controller as a MAVLink mission.

## Build / flash / prepare
See `firmware/README.md`. Short version: `pio run -t upload` over USB-C, then
`python tools/prepare_sd.py --wdmam <file> --wmm WMM.COF --coast <geojson>`
and copy `firmware/sdcard/*` to the card.

## Status / caveats
- Prototype; not certified for any regulated use.
- Firmware is complete but not yet compile-verified on hardware.
- Two BMI088 ground pads use 0.4 mm vias-in-pad (tell your assembler; fill or
  tent them). Verify MAX-M10S `VIO_SEL` strap against the integration manual.
- Map data: WDMAM from the link you supplied; WMM.COF (NOAA) and Natural Earth
  coastline are free downloads you run through `prepare_sd.py`.
