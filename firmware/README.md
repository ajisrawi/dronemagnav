# DroneMagNav firmware (ESP32-S3)

Magnetic-anomaly navigation (MagNav) + great-circle route planner for drones.

```
firmware/
├── platformio.ini          build config (PlatformIO, Arduino-ESP32, N16R8)
├── partitions.csv          16 MB flash layout (dual OTA app slots)
├── src/
│   ├── main.cpp            sensor loop, attitude, MagNav filter, FC feed
│   ├── pins.h              board pin map (schematic rev A)
│   ├── sensors/            bmi088.h  lis3mdl.h  bmp280.h  (register-level SPI)
│   ├── nav/
│   │   ├── wmm.h           World Magnetic Model core field (coeffs from SD)
│   │   ├── wdmam_map.h     anomaly-map window cache (WDMAM / local survey)
│   │   ├── tolles_lawson.h 18-term aircraft-field compensation + fit
│   │   ├── particle_filter.h  600-particle MagNav estimator
│   │   └── geo.h           great-circle distance / bearing / waypoints
│   └── comm/
│       ├── gnss.h          u-blox NMEA parser
│       ├── mavlink_lite.h  MAVLink v2: heartbeat, GPS_INPUT, mission upload
│       └── web_ui.h        WiFi AP + HTTP API for the phone page
└── sdcard/                 staging tree for the microSD (see tools/prepare_sd.py)
    ├── www/index.html      mobile map page (offline coastline, tap-to-route)
    └── maps/               wdmam.bin, WMM.COF, coast.json  (generated)
```

## 1. Install the toolchain
Install [PlatformIO Core](https://platformio.org/install/cli) (or the VS Code
extension). Everything else (ESP-IDF toolchain, Arduino-ESP32 core) is fetched
automatically on first build.

## 2. Build
```bash
cd firmware
pio run
```

## 3. Flash (USB-C, no external programmer)
```bash
pio run -t upload
```
First time only: hold **BOOT**, tap **RESET**, release BOOT — the ESP32-S3
enters its ROM bootloader on the native USB port. Afterwards the USB-CDC
auto-reset handles it. `pio device monitor -b 115200` shows the boot log.

## 4. Prepare the microSD card
```bash
python tools/prepare_sd.py --wdmam data/<WDMAM file> --wmm WMM.COF --coast ne_110m_coastline.geojson
```
then copy `firmware/sdcard/*` to the card root (FAT32, ≤ 32 GB recommended).

| File | Source |
|---|---|
| `maps/wdmam.bin` | converted from the WDMAM grid you supplied |
| `maps/WMM.COF` | NOAA/NCEI World Magnetic Model coefficients (free) |
| `maps/coast.json` | Natural Earth 1:110m coastline GeoJSON (public domain) |
| `maps/local.bin` | optional: your own high-resolution aeromagnetic survey, same format |

## 5. Use it
1. Power from USB-C or the flight controller TELEM port. Join WiFi
   **DroneMagNav** / `magnav123`, open **http://192.168.4.1/** on your phone.
2. **Calibrate once** (Tolles-Lawson): with GNSS fix, tap *Start calibration*,
   fly pitch/roll/yaw manoeuvres on four headings for ~3 min, tap *Stop*.
   Coefficients are saved to `/cal/tl.bin`.
3. **Route:** tap *Set START = here* (or tap the map), tap the destination,
   *Compute route* → great-circle waypoints → *Upload to flight controller*.
4. **MagNav:** when GNSS is lost the filter takes over automatically (or tap
   *Init* to force it) and streams its fix to the FC as `GPS_INPUT`
   (ArduPilot: set `GPS_TYPE=14`, or `GPS_TYPE2=14` for blended use).

## Honest performance expectations
The WDMAM world grid is 3 arc-minutes (~5 km) and is upward-continued to
5 km altitude — it only contains long-wavelength anomalies. With it alone the
filter gives **kilometre-class** positioning, drift-free: good for oceanic /
GNSS-jammed cruise, not for precision landing. For tens-of-metres accuracy at
drone altitude load a local aeromagnetic survey as `/maps/local.bin`. The
LIS3MDL is adequate for the world grid; an RM3100 on the mast connector (J5)
is the upgrade for local-survey navigation.

Not compile-verified on hardware yet — see the project README for status.
