// Tolles-Lawson aircraft magnetic compensation (18-term model).
//
// The drone's own field (permanent magnets, induced soft-iron, eddy currents
// from motors/frame) corrupts the scalar measurement. Tolles-Lawson models
// this as a function of the direction cosines of the Earth field in the body
// frame and their derivatives. Coefficients are fitted during a calibration
// flight (pitch/roll/yaw manoeuvres on four headings, GNSS available) and
// stored in /cal/tl.bin on the SD card.
#pragma once
#include <Arduino.h>
#include <FS.h>
#include <math.h>

class TollesLawson {
public:
    static constexpr int NTERMS = 18;

    void reset() { memset(coef, 0, sizeof(coef)); valid = false; }

    // Direction cosines from the (already hard/soft-iron-free) body vector.
    static void terms(float bx, float by, float bz, float bxd, float byd, float bzd,
                      float Bt, float out[NTERMS]) {
        float cx = bx / Bt, cy = by / Bt, cz = bz / Bt;
        // permanent (3)
        out[0] = cx; out[1] = cy; out[2] = cz;
        // induced (6): Bt * cos_i * cos_j
        out[3] = Bt * cx * cx; out[4] = Bt * cx * cy; out[5] = Bt * cx * cz;
        out[6] = Bt * cy * cy; out[7] = Bt * cy * cz; out[8] = Bt * cz * cz;
        // eddy current (9): Bt * cos_i * d(cos_j)/dt
        float cxd = bxd / Bt, cyd = byd / Bt, czd = bzd / Bt;
        out[9] = Bt * cx * cxd;  out[10] = Bt * cx * cyd; out[11] = Bt * cx * czd;
        out[12] = Bt * cy * cxd; out[13] = Bt * cy * cyd; out[14] = Bt * cy * czd;
        out[15] = Bt * cz * cxd; out[16] = Bt * cz * cyd; out[17] = Bt * cz * czd;
    }

    // Correction to subtract from the measured scalar field (nT)
    float correction(float bx, float by, float bz, float bxd, float byd, float bzd) const {
        if (!valid) return 0.0f;
        float Bt = sqrtf(bx * bx + by * by + bz * bz);
        if (Bt < 1.0f) return 0.0f;
        float t[NTERMS];
        terms(bx, by, bz, bxd, byd, bzd, Bt, t);
        float c = 0;
        for (int i = 0; i < NTERMS; i++) c += coef[i] * t[i];
        return c;
    }

    // ---- calibration: accumulate normal equations, then solve ----------
    void beginFit() { memset(AtA, 0, sizeof(AtA)); memset(Atb, 0, sizeof(Atb)); nsamp = 0; }

    // residual = measured scalar - reference (WMM core + map anomaly at GNSS pos)
    void addSample(float bx, float by, float bz, float bxd, float byd, float bzd,
                   float residual) {
        float Bt = sqrtf(bx * bx + by * by + bz * bz);
        if (Bt < 1.0f) return;
        float t[NTERMS];
        terms(bx, by, bz, bxd, byd, bzd, Bt, t);
        for (int i = 0; i < NTERMS; i++) {
            Atb[i] += t[i] * residual;
            for (int j = 0; j < NTERMS; j++) AtA[i][j] += t[i] * t[j];
        }
        nsamp++;
    }

    // ridge-regularised least squares (lambda keeps eddy terms from blowing up)
    bool solve(double lambda = 1e-3) {
        if (nsamp < 200) return false;
        double A[NTERMS][NTERMS + 1];
        for (int i = 0; i < NTERMS; i++) {
            for (int j = 0; j < NTERMS; j++) A[i][j] = AtA[i][j] + (i == j ? lambda : 0.0);
            A[i][NTERMS] = Atb[i];
        }
        for (int col = 0; col < NTERMS; col++) {          // Gaussian elimination
            int piv = col;
            for (int r = col + 1; r < NTERMS; r++)
                if (fabs(A[r][col]) > fabs(A[piv][col])) piv = r;
            if (fabs(A[piv][col]) < 1e-12) return false;
            if (piv != col) for (int k = 0; k <= NTERMS; k++) { double t = A[col][k]; A[col][k] = A[piv][k]; A[piv][k] = t; }
            for (int r = 0; r < NTERMS; r++) {
                if (r == col) continue;
                double f = A[r][col] / A[col][col];
                for (int k = col; k <= NTERMS; k++) A[r][k] -= f * A[col][k];
            }
        }
        for (int i = 0; i < NTERMS; i++) coef[i] = (float)(A[i][NTERMS] / A[i][i]);
        valid = true;
        return true;
    }

    bool save(fs::FS& fs, const char* path = "/cal/tl.bin") const {
        File f = fs.open(path, "w");
        if (!f) return false;
        f.write((const uint8_t*)coef, sizeof(coef));
        f.close();
        return true;
    }
    bool load(fs::FS& fs, const char* path = "/cal/tl.bin") {
        File f = fs.open(path, "r");
        if (!f) return false;
        bool ok = f.read((uint8_t*)coef, sizeof(coef)) == sizeof(coef);
        f.close();
        valid = ok;
        return ok;
    }

    bool valid = false;
    float coef[NTERMS] = {0};

private:
    double AtA[NTERMS][NTERMS], Atb[NTERMS];
    int nsamp = 0;
};
