// World Magnetic Model evaluator (degree/order 12).
//
// Coefficients are loaded at runtime from the official NOAA/NCEI WMM.COF file
// on the SD card (/maps/WMM.COF) - free download from
// https://www.ncei.noaa.gov/products/world-magnetic-model . The file has the
// epoch on line 1 and "n m gnm hnm dgnm dhnm" lines after it.
//
// Algorithm follows the classic NOAA geomag reference implementation
// (Schmidt semi-normalised associated Legendre functions, geodetic->geocentric
// conversion, secular variation applied for the decimal year).
#pragma once
#include <Arduino.h>
#include <FS.h>
#include <math.h>

class WMM {
public:
    static constexpr int MAXDEG = 12;

    bool load(fs::FS& fs, const char* path = "/maps/WMM.COF") {
        File f = fs.open(path, "r");
        if (!f) return false;
        memset(c, 0, sizeof(c)); memset(cd, 0, sizeof(cd));
        String line = f.readStringUntil('\n');      // header: epoch model date
        epoch = line.toFloat();
        while (f.available()) {
            line = f.readStringUntil('\n');
            line.trim();
            if (line.length() == 0 || line.startsWith("9999")) break;
            int n, m; float gnm, hnm, dgnm, dhnm;
            if (sscanf(line.c_str(), "%d %d %f %f %f %f", &n, &m, &gnm, &hnm,
                       &dgnm, &dhnm) != 6) continue;
            if (n > MAXDEG || m > n) continue;
            c[m][n] = gnm; cd[m][n] = dgnm;
            if (m != 0) { c[n][m - 1] = hnm; cd[n][m - 1] = dhnm; }
        }
        f.close();
        prepare();
        loaded = true;
        return true;
    }

    bool isLoaded() const { return loaded; }

    // Evaluate field: inputs geodetic lat/lon (deg), altitude (km above WGS84
    // ellipsoid), decimal year. Outputs X (north), Y (east), Z (down) in nT.
    void evaluate(double glat, double glon, double altKm, double year,
                  double& X, double& Y, double& Z) const {
        const double a = 6378.137, b = 6356.7523142, re = 6371.2;
        const double a2 = a * a, b2 = b * b, c2 = a2 - b2, a4 = a2 * a2,
                     b4 = b2 * b2, c4 = a4 - b4;
        double dt = year - epoch;
        double rlon = glon * DEG2RAD, rlat = glat * DEG2RAD;
        double srlon = sin(rlon), srlat = sin(rlat), crlon = cos(rlon), crlat = cos(rlat);
        double srlat2 = srlat * srlat, crlat2 = crlat * crlat;
        double sp[13], cp[13];
        sp[0] = 0.0; cp[0] = 1.0; sp[1] = srlon; cp[1] = crlon;
        for (int m = 2; m <= MAXDEG; m++) {
            sp[m] = sp[1] * cp[m - 1] + cp[1] * sp[m - 1];
            cp[m] = cp[1] * cp[m - 1] - sp[1] * sp[m - 1];
        }
        // geodetic -> spherical
        double q = sqrt(a2 - c2 * srlat2);
        double q1 = altKm * q;
        double q2 = ((q1 + a2) / (q1 + b2)) * ((q1 + a2) / (q1 + b2));
        double ct = srlat / sqrt(q2 * crlat2 + srlat2);
        double st = sqrt(1.0 - ct * ct);
        double r2 = altKm * altKm + 2.0 * q1 + (a4 - c4 * srlat2) / (q * q);
        double r = sqrt(r2);
        double d = sqrt(a2 * crlat2 + b2 * srlat2);
        double ca = (altKm + d) / r;
        double sa = c2 * crlat * srlat / (r * d);
        double aor = re / r;
        double ar = aor * aor;      // (re/r)^(n+2) after the first n step
        double br = 0, bt = 0, bp = 0, bpp = 0;
        double p[13][13], dp[13][13], tc[13][13];
        p[0][0] = 1.0; dp[0][0] = 0.0;
        for (int n = 1; n <= MAXDEG; n++) {
            ar = ar * aor;
            for (int m = 0, D3 = 1, D4 = (n + m + D3) / D3; D4 > 0; D4--, m += D3) {
                // associated Legendre polynomials and derivatives via recursion
                if (n == m) {
                    p[m][n] = st * p[m - 1][n - 1];
                    dp[m][n] = st * dp[m - 1][n - 1] + ct * p[m - 1][n - 1];
                } else if (n == 1 && m == 0) {
                    p[m][n] = ct * p[m][n - 1];
                    dp[m][n] = ct * dp[m][n - 1] - st * p[m][n - 1];
                } else if (n > 1 && n != m) {
                    if (m > n - 2) p[m][n - 2] = 0.0;
                    if (m > n - 2) dp[m][n - 2] = 0.0;
                    p[m][n] = ct * p[m][n - 1] - k[m][n] * p[m][n - 2];
                    dp[m][n] = ct * dp[m][n - 1] - st * p[m][n - 1] - k[m][n] * dp[m][n - 2];
                }
                // time-adjusted Gauss coefficients
                tc[m][n] = c[m][n] + dt * cd[m][n];
                if (m != 0) tc[n][m - 1] = c[n][m - 1] + dt * cd[n][m - 1];
                double par = ar * p[m][n];
                double temp1, temp2;
                if (m == 0) {
                    temp1 = tc[m][n] * cp[m];
                    temp2 = tc[m][n] * sp[m];
                } else {
                    temp1 = tc[m][n] * cp[m] + tc[n][m - 1] * sp[m];
                    temp2 = tc[m][n] * sp[m] - tc[n][m - 1] * cp[m];
                }
                bt = bt - ar * temp1 * dp[m][n];
                bp += (fm[m] * temp2 * par);
                br += (fn[n] * temp1 * par);
                // special case: north/south geographic poles
                if (st == 0.0 && m == 1) {
                    if (n == 1) pp[n] = pp[n - 1];
                    else pp[n] = ct * pp[n - 1] - k[m][n] * pp[n - 2];
                    bpp += (fm[m] * temp2 * ar * pp[n]);
                }
            }
        }
        if (st == 0.0) bp = bpp; else bp /= st;
        // rotate to geodetic X (north), Y (east), Z (down)
        X = -bt * ca - br * sa;
        Y = bp;
        Z = bt * sa - br * ca;
    }

    double totalField(double lat, double lon, double altKm, double year) const {
        double X, Y, Z;
        evaluate(lat, lon, altKm, year, X, Y, Z);
        return sqrt(X * X + Y * Y + Z * Z);
    }

    double declination(double lat, double lon, double altKm, double year) const {
        double X, Y, Z;
        evaluate(lat, lon, altKm, year, X, Y, Z);
        return atan2(Y, X) / DEG2RAD;
    }

private:
    static constexpr double DEG2RAD = M_PI / 180.0;
    bool loaded = false;
    double epoch = 2025.0;
    double c[13][13], cd[13][13];
    double snorm[169], k[13][13], fn[13], fm[13];
    mutable double pp[13];

    // Schmidt semi-normalisation of the Gauss coefficients (once per load)
    void prepare() {
        snorm[0] = 1.0;
        for (int n = 1; n <= MAXDEG; n++) {
            snorm[n] = snorm[n - 1] * (double)(2 * n - 1) / (double)n;
            int j = 2;
            for (int m = 0, D1 = 1, D2 = (n - m + D1) / D1; D2 > 0; D2--, m += D1) {
                k[m][n] = (double)(((n - 1) * (n - 1)) - (m * m)) /
                          (double)((2 * n - 1) * (2 * n - 3));
                if (m > 0) {
                    double flnmj = (double)((n - m + 1) * j) / (double)(n + m);
                    snorm[n + m * 13] = snorm[n + (m - 1) * 13] * sqrt(flnmj);
                    j = 1;
                    c[n][m - 1] = snorm[n + m * 13] * c[n][m - 1];
                    cd[n][m - 1] = snorm[n + m * 13] * cd[n][m - 1];
                }
                c[m][n] = snorm[n + m * 13] * c[m][n];
                cd[m][n] = snorm[n + m * 13] * cd[m][n];
            }
            fn[n] = (double)(n + 1);
            fm[n] = (double)n;
        }
        k[1][1] = 0.0;
        fm[0] = 0.0;
        pp[0] = 1.0;
    }
};
