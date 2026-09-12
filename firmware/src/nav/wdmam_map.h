// WDMAM magnetic anomaly map access.
//
// The SD card holds /maps/wdmam.bin produced by tools/prepare_sd.py:
//   header (32 bytes): magic "WDM1", int32 nlon, int32 nlat, float lon0,
//                      float lat0, float dlon, float dlat, int32 reserved
//   then int16 anomaly values in nT, row-major, first row = lat0 (south),
//   columns from lon0 (-180) eastward. Missing data = INT16_MIN.
//
// A small window around the current estimate is cached in PSRAM so the
// particle filter can do thousands of lookups per second without touching
// the card. The same format can hold a local high-resolution aeromagnetic
// survey (/maps/local.bin) which takes priority when it covers the position.
#pragma once
#include <Arduino.h>
#include <FS.h>
#include <math.h>

class AnomalyMap {
public:
    static constexpr int WIN = 96;                // cells per side (~4.8 deg @ 3')
    static constexpr int16_t NODATA = INT16_MIN;

    bool open(fs::FS& fs, const char* path) {
        _fs = &fs;
        _path = path;
        File f = fs.open(path, "r");
        if (!f) return false;
        uint8_t h[32];
        if (f.read(h, 32) != 32 || memcmp(h, "WDM1", 4) != 0) { f.close(); return false; }
        memcpy(&nlon, h + 4, 4); memcpy(&nlat, h + 8, 4);
        memcpy(&lon0, h + 12, 4); memcpy(&lat0, h + 16, 4);
        memcpy(&dlon, h + 20, 4); memcpy(&dlat, h + 24, 4);
        f.close();
        if (!win) win = (int16_t*)ps_malloc(WIN * WIN * sizeof(int16_t));
        winValid = false;
        return win != nullptr;
    }

    bool covers(double lat, double lon) const {
        return lat >= lat0 && lat < lat0 + nlat * dlat &&
               lon >= lon0 && lon < lon0 + nlon * dlon;
    }

    // Ensure the cached window is centred near (lat, lon). Called from the
    // main loop (does SD I/O); lookups themselves never touch the card.
    bool ensureWindow(double lat, double lon) {
        int ci = (int)floor((lon - lon0) / dlon), cj = (int)floor((lat - lat0) / dlat);
        int i0 = ci - WIN / 2, j0 = cj - WIN / 2;
        if (winValid && abs(i0 - wi0) < WIN / 4 && abs(j0 - wj0) < WIN / 4) return true;
        File f = _fs->open(_path, "r");
        if (!f) return false;
        for (int j = 0; j < WIN; j++) {
            int row = j0 + j;
            if (row < 0 || row >= nlat) {
                for (int i = 0; i < WIN; i++) win[j * WIN + i] = NODATA;
                continue;
            }
            for (int i = 0; i < WIN; i++) {
                int col = ((i0 + i) % nlon + nlon) % nlon;     // wrap longitude
                size_t off = 32 + ((size_t)row * nlon + col) * 2;
                if (i == 0 || col == 0) f.seek(off);
                int16_t v;
                if (f.read((uint8_t*)&v, 2) != 2) v = NODATA;
                win[j * WIN + i] = v;
            }
        }
        f.close();
        wi0 = i0; wj0 = j0; winValid = true;
        return true;
    }

    // bilinear interpolated anomaly in nT; NAN when outside the window / no data
    float lookup(double lat, double lon) const {
        if (!winValid) return NAN;
        double fi = (lon - lon0) / dlon - wi0, fj = (lat - lat0) / dlat - wj0;
        int i = (int)floor(fi), j = (int)floor(fj);
        if (i < 0 || j < 0 || i >= WIN - 1 || j >= WIN - 1) return NAN;
        int16_t a = win[j * WIN + i], b = win[j * WIN + i + 1];
        int16_t c = win[(j + 1) * WIN + i], d = win[(j + 1) * WIN + i + 1];
        if (a == NODATA || b == NODATA || c == NODATA || d == NODATA) return NAN;
        double u = fi - i, v = fj - j;
        return (float)((1 - u) * (1 - v) * a + u * (1 - v) * b + (1 - u) * v * c + u * v * d);
    }

    // local anomaly gradient magnitude (nT per cell) - used to judge how
    // informative the map is around the current position
    float gradient(double lat, double lon) const {
        float g1 = lookup(lat, lon + dlon), g0 = lookup(lat, lon - dlon);
        float h1 = lookup(lat + dlat, lon), h0 = lookup(lat - dlat, lon);
        if (isnan(g1) || isnan(g0) || isnan(h1) || isnan(h0)) return NAN;
        return sqrtf((g1 - g0) * (g1 - g0) + (h1 - h0) * (h1 - h0)) * 0.5f;
    }

    int32_t nlon = 0, nlat = 0;
    float lon0 = -180, lat0 = -90, dlon = 0.05f, dlat = 0.05f;

private:
    fs::FS* _fs = nullptr;
    const char* _path = nullptr;
    int16_t* win = nullptr;
    int wi0 = 0, wj0 = 0;
    bool winValid = false;
};
