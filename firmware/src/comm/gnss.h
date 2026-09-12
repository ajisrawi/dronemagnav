// u-blox MAX-M10S over UART, NMEA parser (GGA + RMC)
#pragma once
#include <Arduino.h>

class GNSS {
public:
    struct Fix {
        bool valid = false;
        double lat = 0, lon = 0;
        float altMsl = 0;       // metres
        float speedMps = 0;     // ground speed
        float courseDeg = 0;    // track over ground
        float hdop = 99;
        uint8_t sats = 0;
        uint8_t quality = 0;    // GGA fix quality
        uint32_t lastMs = 0;
    };

    GNSS(HardwareSerial& ser) : _ser(ser) {}

    void begin(int rxPin, int txPin, uint32_t baud = 38400) {
        _ser.begin(baud, SERIAL_8N1, rxPin, txPin);
    }

    void poll() {
        while (_ser.available()) {
            char c = (char)_ser.read();
            if (c == '$') { _len = 0; _buf[_len++] = c; }
            else if (_len > 0 && _len < sizeof(_buf) - 1) {
                if (c == '\n') { _buf[_len] = 0; parse(_buf); _len = 0; }
                else if (c != '\r') _buf[_len++] = c;
            }
        }
    }

    const Fix& fix() const { return _fix; }
    bool fresh(uint32_t maxAgeMs = 2000) const {
        return _fix.valid && (millis() - _fix.lastMs) < maxAgeMs;
    }

private:
    HardwareSerial& _ser;
    char _buf[120];
    size_t _len = 0;
    Fix _fix;

    static bool checksumOk(char* s) {
        char* star = strchr(s, '*');
        if (!star) return false;
        uint8_t cs = 0;
        for (char* p = s + 1; p < star; p++) cs ^= (uint8_t)*p;
        return strtol(star + 1, nullptr, 16) == cs;
    }

    static double dm2deg(const char* f, const char* hemi) {
        if (!f || !*f) return 0;
        double v = atof(f);
        int deg = (int)(v / 100);
        double d = deg + (v - deg * 100) / 60.0;
        if (hemi && (*hemi == 'S' || *hemi == 'W')) d = -d;
        return d;
    }

    void parse(char* s) {
        if (!checksumOk(s)) return;
        char* star = strchr(s, '*'); if (star) *star = 0;
        char* f[20] = {0};
        int n = 0;
        char* p = s;
        while (p && n < 20) {
            f[n++] = p;
            p = strchr(p, ',');
            if (p) *p++ = 0;
        }
        if (n < 7) return;
        const char* id = f[0] + 3;               // skip $GP / $GN
        if (!strncmp(id, "GGA", 3) && n >= 10) {
            _fix.quality = atoi(f[6]);
            _fix.sats = atoi(f[7]);
            _fix.hdop = atof(f[8]);
            if (_fix.quality > 0) {
                _fix.lat = dm2deg(f[2], f[3]);
                _fix.lon = dm2deg(f[4], f[5]);
                _fix.altMsl = atof(f[9]);
                _fix.valid = true;
                _fix.lastMs = millis();
            } else {
                _fix.valid = false;
            }
        } else if (!strncmp(id, "RMC", 3) && n >= 9) {
            if (f[2][0] == 'A') {
                _fix.speedMps = atof(f[7]) * 0.514444f;
                _fix.courseDeg = atof(f[8]);
            }
        }
    }
};
