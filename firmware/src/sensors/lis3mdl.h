// LIS3MDL 3-axis magnetometer, SPI, register-level driver
#pragma once
#include <Arduino.h>
#include <SPI.h>

class LIS3MDL {
public:
    static constexpr uint8_t WHO_AM_I = 0x0F, CTRL1 = 0x20, CTRL2 = 0x21,
                             CTRL3 = 0x22, CTRL4 = 0x23, CTRL5 = 0x24,
                             OUT_X_L = 0x28, STATUS = 0x27;

    LIS3MDL(SPIClass& spi, int cs) : _spi(spi), _cs(cs) {}

    bool begin() {
        pinMode(_cs, OUTPUT);
        digitalWrite(_cs, HIGH);
        if (read8(WHO_AM_I) != 0x3D) return false;
        // ultra-high-performance XY, ODR 80 Hz, FAST_ODR off, temp sensor on
        write8(CTRL1, 0xF0);
        // full scale +-4 gauss (0.1461 mG/LSB at 16 bit -> 14.6 nT/LSB)
        write8(CTRL2, 0x00);
        // continuous conversion, SPI 4-wire
        write8(CTRL3, 0x00);
        // Z ultra-high-performance
        write8(CTRL4, 0x0C);
        // block data update
        write8(CTRL5, 0x40);
        return true;
    }

    // returns field in nanotesla (board frame)
    bool read(float& bx, float& by, float& bz) {
        uint8_t buf[6];
        readN(OUT_X_L, buf, 6);
        int16_t x = (int16_t)(buf[1] << 8 | buf[0]);
        int16_t y = (int16_t)(buf[3] << 8 | buf[2]);
        int16_t z = (int16_t)(buf[5] << 8 | buf[4]);
        const float nT_per_lsb = 100000.0f / 6842.0f;   // +-4 gauss: 6842 LSB/gauss
        bx = x * nT_per_lsb;
        by = y * nT_per_lsb;
        bz = z * nT_per_lsb;
        return true;
    }

private:
    SPIClass& _spi;
    int _cs;
    void write8(uint8_t reg, uint8_t v) {
        _spi.beginTransaction(SPISettings(8000000, MSBFIRST, SPI_MODE3));
        digitalWrite(_cs, LOW);
        _spi.transfer(reg & 0x3F);
        _spi.transfer(v);
        digitalWrite(_cs, HIGH);
        _spi.endTransaction();
    }
    uint8_t read8(uint8_t reg) {
        uint8_t v;
        readN(reg, &v, 1);
        return v;
    }
    void readN(uint8_t reg, uint8_t* buf, size_t n) {
        _spi.beginTransaction(SPISettings(8000000, MSBFIRST, SPI_MODE3));
        digitalWrite(_cs, LOW);
        _spi.transfer(0x80 | 0x40 | (reg & 0x3F));      // read + auto-increment
        for (size_t i = 0; i < n; i++) buf[i] = _spi.transfer(0x00);
        digitalWrite(_cs, HIGH);
        _spi.endTransaction();
    }
};
