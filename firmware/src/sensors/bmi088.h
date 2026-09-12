// BMI088 accelerometer + gyroscope, SPI (two chip selects), register-level
#pragma once
#include <Arduino.h>
#include <SPI.h>

class BMI088 {
public:
    BMI088(SPIClass& spi, int csAcc, int csGyr)
        : _spi(spi), _csA(csAcc), _csG(csGyr) {}

    bool begin() {
        pinMode(_csA, OUTPUT); digitalWrite(_csA, HIGH);
        pinMode(_csG, OUTPUT); digitalWrite(_csG, HIGH);
        // accel: soft reset, dummy read to switch it into SPI mode
        writeA(0x7E, 0xB6); delay(2);
        readA(0x00);
        if (readA(0x00) != 0x1E) return false;
        writeA(0x7D, 0x04); delay(5);          // ACC_PWR_CTRL: enable
        writeA(0x7C, 0x00);                    // ACC_PWR_CONF: active
        writeA(0x40, 0xA8);                    // ACC_CONF: normal BW, 100 Hz ODR
        writeA(0x41, 0x01);                    // ACC_RANGE: +-6 g
        // gyro
        writeG(0x14, 0xB6); delay(30);
        if (readG(0x00) != 0x0F) return false;
        writeG(0x0F, 0x01);                    // GYRO_RANGE: +-1000 dps
        writeG(0x10, 0x02);                    // GYRO_BANDWIDTH: 400 Hz ODR/47 Hz
        writeG(0x11, 0x00);                    // GYRO_LPM1: normal
        return true;
    }

    // m/s^2
    void readAccel(float& ax, float& ay, float& az) {
        uint8_t b[6];
        readAN(0x12, b, 6);
        int16_t x = (int16_t)(b[1] << 8 | b[0]);
        int16_t y = (int16_t)(b[3] << 8 | b[2]);
        int16_t z = (int16_t)(b[5] << 8 | b[4]);
        const float s = 6.0f * 9.80665f / 32768.0f;   // +-6 g range
        ax = x * s; ay = y * s; az = z * s;
    }

    // rad/s
    void readGyro(float& gx, float& gy, float& gz) {
        uint8_t b[6];
        readGN(0x02, b, 6);
        int16_t x = (int16_t)(b[1] << 8 | b[0]);
        int16_t y = (int16_t)(b[3] << 8 | b[2]);
        int16_t z = (int16_t)(b[5] << 8 | b[4]);
        const float s = (1000.0f / 32768.0f) * (PI / 180.0f);
        gx = x * s; gy = y * s; gz = z * s;
    }

private:
    SPIClass& _spi;
    int _csA, _csG;
    SPISettings _set{10000000, MSBFIRST, SPI_MODE0};

    void writeA(uint8_t r, uint8_t v) { xfer(_csA, r & 0x7F, &v, 1, true, false); }
    void writeG(uint8_t r, uint8_t v) { xfer(_csG, r & 0x7F, &v, 1, true, false); }
    uint8_t readA(uint8_t r) { uint8_t v; readAN(r, &v, 1); return v; }
    uint8_t readG(uint8_t r) { uint8_t v; readGN(r, &v, 1); return v; }
    // the BMI088 accelerometer returns one dummy byte before data on SPI
    void readAN(uint8_t r, uint8_t* b, size_t n) { xfer(_csA, 0x80 | r, b, n, false, true); }
    void readGN(uint8_t r, uint8_t* b, size_t n) { xfer(_csG, 0x80 | r, b, n, false, false); }

    void xfer(int cs, uint8_t cmd, uint8_t* b, size_t n, bool write, bool dummy) {
        _spi.beginTransaction(_set);
        digitalWrite(cs, LOW);
        _spi.transfer(cmd);
        if (dummy) _spi.transfer(0x00);
        for (size_t i = 0; i < n; i++) {
            if (write) _spi.transfer(b[i]);
            else b[i] = _spi.transfer(0x00);
        }
        digitalWrite(cs, HIGH);
        _spi.endTransaction();
    }
};
