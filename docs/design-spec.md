# DroneMagNav — Design Specification (rev A)

## 1. Purpose
A drone-mountable navigation module that estimates position without GNSS by
matching the measured total magnetic field against the World Digital Magnetic
Anomaly Map (WDMAM), fused with inertial dead reckoning; and a phone interface
to plan and upload direct (great-circle) routes.

## 2. Architecture
| Function | Implementation |
|---|---|
| Compute + radio | ESP32-S3-WROOM-1-N16R8: dual-core 240 MHz, 8 MB PSRAM, WiFi/BLE, USB-CDC |
| Sensing | LIS3MDL mag, BMI088 IMU, BMP280 baro — one SPI bus at 8–10 MHz |
| Reference | u-blox MAX-M10S GNSS on UART0 pads (GPIO43/44), PPS on GPIO16 |
| Map storage | microSD, SDMMC 4-bit (GPIO38–42, 47), card detect GPIO48 |
| Flight controller | UART2 (GPIO4/5) MAVLink v2, Pixhawk TELEM pinout on JST-GH J2 |
| External sensor | I2C1 (GPIO1/2) + interrupt GPIO3 on JST-GH J5 (mast-mounted RM3100) |
| Power | USB-C VBUS ⊕ FC 5 V (SS14 diode-OR) → AMS1117-3.3 → +3V3; AP2112K-3.3 → +3.3VA |

## 3. Pin map
| ESP32-S3 | Net | | ESP32-S3 | Net |
|---|---|---|---|---|
| IO12 | SPI_SCK | | IO38/39/40/41/42/47 | SD_CLK/CMD/D0/D1/D2/D3 |
| IO11 | SPI_MOSI | | IO48 | SD_DET |
| IO13 | SPI_MISO | | TXD0 (43) / RXD0 (44) | GNSS RXD / TXD |
| IO10 / IO9 | CS_ACC / CS_GYR | | IO16 | GNSS_PPS |
| IO14 / IO21 | CS_MAG / CS_BARO | | IO4 / IO5 | FC_RXD / FC_TXD |
| IO6 / IO7 / IO8 | INT_ACC / INT_GYR / MAG_DRDY | | IO1 / IO2 / IO3 | I2C_SDA / I2C_SCL / MAST_INT |
| IO35 / IO36 / IO37 | LED_NAV / LED_FIX / LED_LINK | | EN / IO0 | RESET / BOOT buttons |

## 4. Connectors
- **J1 USB-C** — power (VBUS) + native USB (D+/D− through USBLC6-2SC6 ESD).
- **J2 FC_TELEM (JST-GH 6)** — 1 VCC 5 V in, 2 FC TX → board, 3 board TX → FC, 4/5 NC, 6 GND.
- **J3 microSD** — Hirose DM3AT push-push.
- **J4 GNSS antenna** — U.FL, passive antenna, 50 Ω trace.
- **J5 SENSOR_MAST (JST-GH 6)** — 1 +3.3VA, 2 GND, 3 SDA, 4 SCL, 5 INT, 6 +5 V.

## 5. PCB
64 × 60 mm, 4 layers (F.Cu signals / In1 GND / In2 +3V3 / B.Cu signals),
30.5 mm M3 mounting pattern. ESP32 antenna at the top edge with a full copper
keep-out (module courtyard respected). USB-C left edge, microSD right edge,
GNSS + U.FL top-right, sensors centre, magnetometer bottom-centre away from
the regulators (bottom-left). Rules: 0.2 mm track, 0.15 mm clearance,
0.45/0.2 mm vias (0.4 mm vias-in-pad on BMI088 pads 2/4).

## 6. Firmware
See `firmware/README.md` for the module map. Key algorithms:
- **WMM** degree-12 spherical-harmonic core field, coefficients from `WMM.COF`.
- **AnomalyMap** 96 × 96-cell PSRAM window over the int16 nT grid on SD; bilinear lookup.
- **TollesLawson** 18-term compensation; ridge-regularised least squares fit from a calibration flight.
- **MagNavPF** 600 particles (lat, lon, bias); systematic resampling at ESS < N/2, roughening.
- **MavlinkLite** HEARTBEAT, GPS_INPUT, MISSION_COUNT/ITEM_INT upload; parses GLOBAL_POSITION_INT / VFR_HUD.
- **WebUI** AP `DroneMagNav`, HTTP API: `/api/status`, `/api/route`, `/api/upload`, `/api/coast`, `/api/anom`, `/api/cal`, `/api/init`.

## 7. Map data pipeline
`tools/prepare_sd.py` converts the WDMAM grid (xyz/NetCDF/GeoTIFF) to
`/maps/wdmam.bin` (32-byte header + int16 nT, 3′ world grid ≈ 52 MB), and
stages `WMM.COF`, `coast.json` (Natural Earth 1:110m) and the web page.

## 8. Verification
| Check | Result |
|---|---|
| Schematic ERC | 0 errors, 1 warning (BMI088 SDO1/SDO2 both on MISO — per Bosch reference design) |
| Netlist, 21 critical nets | 21/21 |
| PCB connectivity | 0 unconnected |
| PCB electrical DRC | 0 violations (22 silkscreen notes) |

## 9. Known limitations
- WDMAM resolution/altitude → km-class accuracy without a local survey.
- LIS3MDL noise adequate for the world grid only; RM3100 recommended for local surveys.
- Magnetic interference from ESCs/motors must be handled by mounting distance and the Tolles-Lawson calibration.
- Firmware not yet compile-verified on hardware; MAX-M10S `VIO_SEL` strap to be confirmed.
