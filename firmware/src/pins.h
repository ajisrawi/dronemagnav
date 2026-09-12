// DroneMagNav board pin map - matches schematic rev A (hardware/dronemagnav)
#pragma once

// SPI sensor bus (BMI088 accel/gyro, LIS3MDL magnetometer, BMP280 baro)
#define PIN_SPI_SCK    12
#define PIN_SPI_MOSI   11
#define PIN_SPI_MISO   13
#define PIN_CS_ACC     10
#define PIN_CS_GYR      9
#define PIN_CS_MAG     14
#define PIN_CS_BARO    21
#define PIN_INT_ACC     6
#define PIN_INT_GYR     7
#define PIN_MAG_DRDY    8

// GNSS (u-blox MAX-M10S) on the UART0 pads (GPIO43 TXD0 / GPIO44 RXD0);
// the console is the native USB-CDC port, so UART0 is free
#define PIN_GNSS_TX    43   // ESP TXD0 -> GNSS RXD
#define PIN_GNSS_RX    44   // GNSS TXD -> ESP RXD0
#define PIN_GNSS_PPS   16

// Flight controller MAVLink on UART2 (JST-GH TELEM pinout)
#define PIN_FC_TX       4   // ESP -> FC RX
#define PIN_FC_RX       5   // FC TX -> ESP

// I2C sensor-mast connector (external RM3100 etc.)
#define PIN_I2C_SDA     1
#define PIN_I2C_SCL     2
#define PIN_MAST_INT    3

// microSD, SDMMC 4-bit
#define PIN_SD_CLK     38
#define PIN_SD_CMD     39
#define PIN_SD_D0      40
#define PIN_SD_D1      41
#define PIN_SD_D2      42
#define PIN_SD_D3      47
#define PIN_SD_DET     48   // low = card present

// status LEDs
#define PIN_LED_NAV    35
#define PIN_LED_FIX    36
#define PIN_LED_LINK   37
