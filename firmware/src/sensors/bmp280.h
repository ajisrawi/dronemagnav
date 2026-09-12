// BMP280 barometer, SPI, with Bosch compensation
#pragma once
#include <Arduino.h>
#include <SPI.h>

class BMP280 {
public:
    BMP280(SPIClass& spi, int cs) : _spi(spi), _cs(cs) {}

    bool begin() {
        pinMode(_cs, OUTPUT); digitalWrite(_cs, HIGH);
        if (read8(0xD0) != 0x58) return false;
        write8(0xE0, 0xB6); delay(5);
        uint8_t c[24];
        readN(0x88, c, 24);
        T1 = c[1] << 8 | c[0]; T2 = (int16_t)(c[3] << 8 | c[2]); T3 = (int16_t)(c[5] << 8 | c[4]);
        P1 = c[7] << 8 | c[6]; P2 = (int16_t)(c[9] << 8 | c[8]); P3 = (int16_t)(c[11] << 8 | c[10]);
        P4 = (int16_t)(c[13] << 8 | c[12]); P5 = (int16_t)(c[15] << 8 | c[14]);
        P6 = (int16_t)(c[17] << 8 | c[16]); P7 = (int16_t)(c[19] << 8 | c[18]);
        P8 = (int16_t)(c[21] << 8 | c[20]); P9 = (int16_t)(c[23] << 8 | c[22]);
        write8(0xF5, 0x10);      // config: standby 0.5 ms, IIR x16
        write8(0xF4, 0x57);      // ctrl_meas: T x2, P x16, normal mode
        return true;
    }

    // pressure in Pa, temperature in C
    void read(float& pressure, float& temp) {
        uint8_t d[6];
        readN(0xF7, d, 6);
        int32_t adcP = ((int32_t)d[0] << 12) | ((int32_t)d[1] << 4) | (d[2] >> 4);
        int32_t adcT = ((int32_t)d[3] << 12) | ((int32_t)d[4] << 4) | (d[5] >> 4);
        int32_t var1 = ((((adcT >> 3) - ((int32_t)T1 << 1))) * ((int32_t)T2)) >> 11;
        int32_t var2 = (((((adcT >> 4) - ((int32_t)T1)) * ((adcT >> 4) - ((int32_t)T1))) >> 12) *
                        ((int32_t)T3)) >> 14;
        int32_t tfine = var1 + var2;
        temp = ((tfine * 5 + 128) >> 8) / 100.0f;
        int64_t v1 = (int64_t)tfine - 128000;
        int64_t v2 = v1 * v1 * (int64_t)P6;
        v2 = v2 + ((v1 * (int64_t)P5) << 17);
        v2 = v2 + (((int64_t)P4) << 35);
        v1 = ((v1 * v1 * (int64_t)P3) >> 8) + ((v1 * (int64_t)P2) << 12);
        v1 = (((((int64_t)1) << 47) + v1)) * ((int64_t)P1) >> 33;
        if (v1 == 0) { pressure = 0; return; }
        int64_t p = 1048576 - adcP;
        p = (((p << 31) - v2) * 3125) / v1;
        v1 = (((int64_t)P9) * (p >> 13) * (p >> 13)) >> 25;
        v2 = (((int64_t)P8) * p) >> 19;
        p = ((p + v1 + v2) >> 8) + (((int64_t)P7) << 4);
        pressure = (float)p / 256.0f;
    }

    static float altitudeFromPressure(float pa, float qnh = 101325.0f) {
        return 44330.0f * (1.0f - powf(pa / qnh, 0.1903f));
    }

private:
    SPIClass& _spi;
    int _cs;
    uint16_t T1, P1;
    int16_t T2, T3, P2, P3, P4, P5, P6, P7, P8, P9;
    void write8(uint8_t r, uint8_t v) {
        _spi.beginTransaction(SPISettings(8000000, MSBFIRST, SPI_MODE0));
        digitalWrite(_cs, LOW);
        _spi.transfer(r & 0x7F); _spi.transfer(v);
        digitalWrite(_cs, HIGH);
        _spi.endTransaction();
    }
    uint8_t read8(uint8_t r) { uint8_t v; readN(r, &v, 1); return v; }
    void readN(uint8_t r, uint8_t* b, size_t n) {
        _spi.beginTransaction(SPISettings(8000000, MSBFIRST, SPI_MODE0));
        digitalWrite(_cs, LOW);
        _spi.transfer(0x80 | r);
        for (size_t i = 0; i < n; i++) b[i] = _spi.transfer(0x00);
        digitalWrite(_cs, HIGH);
        _spi.endTransaction();
    }
};
