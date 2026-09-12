// MagNav particle filter.
//
// State per particle: latitude, longitude (deg), scalar magnetometer bias (nT).
// Propagation: dead-reckoning from the velocity vector (from the flight
// controller's estimate when available, else IMU-integrated) plus process
// noise. Update: Gaussian likelihood of the compensated scalar measurement
// against  WMM core field + map anomaly + bias  at each particle.
// Output: weighted mean and covariance; effective sample size drives
// systematic resampling.
#pragma once
#include <Arduino.h>
#include <math.h>
#include "wmm.h"
#include "wdmam_map.h"

class MagNavPF {
public:
    static constexpr int N = 600;

    struct Particle { double lat, lon; float bias; float w; };

    void init(double lat, double lon, float sigmaPosM, float sigmaBias) {
        for (int i = 0; i < N; i++) {
            p[i].lat = lat + gauss() * sigmaPosM / 111320.0;
            p[i].lon = lon + gauss() * sigmaPosM / (111320.0 * cos(lat * DEG));
            p[i].bias = gauss() * sigmaBias;
            p[i].w = 1.0f / N;
        }
        initialised = true;
    }

    // vn, ve in m/s (north, east); dt in s; sigmaV in m/s process noise
    void predict(float vn, float ve, float dt, float sigmaV, float sigmaBiasWalk) {
        if (!initialised) return;
        for (int i = 0; i < N; i++) {
            float dn = (vn + gauss() * sigmaV) * dt, de = (ve + gauss() * sigmaV) * dt;
            p[i].lat += dn / 111320.0;
            p[i].lon += de / (111320.0 * cos(p[i].lat * DEG));
            p[i].bias += gauss() * sigmaBiasWalk * dt;
        }
    }

    // measScalar: compensated total field (nT); returns false if no map data
    bool update(float measScalar, const WMM& wmm, const AnomalyMap& map,
                double altKm, double year, float sigmaMeas) {
        if (!initialised || !wmm.isLoaded()) return false;
        float maxLogW = -1e30f;
        static float logw[N];
        int valid = 0;
        for (int i = 0; i < N; i++) {
            float anom = map.lookup(p[i].lat, p[i].lon);
            if (isnan(anom)) { logw[i] = -1e30f; continue; }
            float core = (float)wmm.totalField(p[i].lat, p[i].lon, altKm, year);
            float pred = core + anom + p[i].bias;
            float r = (measScalar - pred) / sigmaMeas;
            logw[i] = logf(p[i].w + 1e-30f) - 0.5f * r * r;
            if (logw[i] > maxLogW) maxLogW = logw[i];
            valid++;
        }
        if (valid < N / 4) return false;
        float sum = 0;
        for (int i = 0; i < N; i++) {
            p[i].w = logw[i] <= -1e29f ? 0.0f : expf(logw[i] - maxLogW);
            sum += p[i].w;
        }
        if (sum <= 0) return false;
        float ess = 0;
        for (int i = 0; i < N; i++) { p[i].w /= sum; ess += p[i].w * p[i].w; }
        ess = 1.0f / ess;
        if (ess < N * 0.5f) resample();
        return true;
    }

    void estimate(double& lat, double& lon, float& bias, float& sigmaM) const {
        double slat = 0, slon = 0; float sb = 0;
        for (int i = 0; i < N; i++) { slat += p[i].w * p[i].lat; slon += p[i].w * p[i].lon; sb += p[i].w * p[i].bias; }
        lat = slat; lon = slon; bias = sb;
        double var = 0;
        for (int i = 0; i < N; i++) {
            double dn = (p[i].lat - lat) * 111320.0, de = (p[i].lon - lon) * 111320.0 * cos(lat * DEG);
            var += p[i].w * (dn * dn + de * de);
        }
        sigmaM = (float)sqrt(var);
    }

    bool initialised = false;

private:
    static constexpr double DEG = M_PI / 180.0;
    Particle p[N];

    void resample() {
        static Particle q[N];
        float step = 1.0f / N, u = frand() * step, c = p[0].w;
        int i = 0;
        for (int j = 0; j < N; j++) {
            while (u > c && i < N - 1) { i++; c += p[i].w; }
            q[j] = p[i];
            q[j].w = step;
            u += step;
        }
        memcpy(p, q, sizeof(p));
        // roughening keeps particle diversity after resampling
        for (int k = 0; k < N; k++) {
            p[k].lat += gauss() * 3.0 / 111320.0;
            p[k].lon += gauss() * 3.0 / (111320.0 * cos(p[k].lat * DEG));
        }
    }

    static float frand() { return (float)esp_random() / 4294967295.0f; }
    static float gauss() {
        float u1 = frand() + 1e-7f, u2 = frand();
        return sqrtf(-2.0f * logf(u1)) * cosf(2.0f * (float)M_PI * u2);
    }
};
