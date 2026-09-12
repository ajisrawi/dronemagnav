"""Validate the firmware WMM algorithm (firmware/src/nav/wmm.h) against NOAA's
official WMM2025 test values, using a line-by-line Python port of the same
code. Any error > 0.1 nT means the C++ evaluator has a bug.

usage: python tools/wmm_check.py data/WMM.COF data/wmm/WMM2025_TestValues.txt
"""
import math
import sys

MAXDEG = 12


class WMM:
    def __init__(self, path):
        self.c = [[0.0] * 13 for _ in range(13)]
        self.cd = [[0.0] * 13 for _ in range(13)]
        with open(path) as f:
            self.epoch = float(f.readline().split()[0])
            for line in f:
                s = line.split()
                if len(s) < 6 or s[0].startswith("9999"):
                    break
                n, m = int(s[0]), int(s[1])
                gnm, hnm, dgnm, dhnm = map(float, s[2:6])
                if n > MAXDEG or m > n:
                    continue
                self.c[m][n] = gnm
                self.cd[m][n] = dgnm
                if m != 0:
                    self.c[n][m - 1] = hnm
                    self.cd[n][m - 1] = dhnm
        self.prepare()

    def prepare(self):
        self.snorm = [0.0] * 169
        self.k = [[0.0] * 13 for _ in range(13)]
        self.fn = [0.0] * 13
        self.fm = [0.0] * 13
        self.pp = [0.0] * 13
        self.snorm[0] = 1.0
        for n in range(1, MAXDEG + 1):
            self.snorm[n] = self.snorm[n - 1] * (2 * n - 1) / n
            j = 2
            m = 0
            D2 = n - m + 1
            while D2 > 0:
                self.k[m][n] = ((n - 1) ** 2 - m * m) / ((2 * n - 1) * (2 * n - 3))
                if m > 0:
                    flnmj = ((n - m + 1) * j) / (n + m)
                    self.snorm[n + m * 13] = self.snorm[n + (m - 1) * 13] * math.sqrt(flnmj)
                    j = 1
                    self.c[n][m - 1] *= self.snorm[n + m * 13]
                    self.cd[n][m - 1] *= self.snorm[n + m * 13]
                self.c[m][n] *= self.snorm[n + m * 13]
                self.cd[m][n] *= self.snorm[n + m * 13]
                D2 -= 1
                m += 1
            self.fn[n] = n + 1
            self.fm[n] = n
        self.k[1][1] = 0.0
        self.fm[0] = 0.0
        self.pp[0] = 1.0

    def evaluate(self, glat, glon, alt_km, year):
        a, b, re = 6378.137, 6356.7523142, 6371.2
        a2, b2 = a * a, b * b
        c2 = a2 - b2
        a4, b4 = a2 * a2, b2 * b2
        c4 = a4 - b4
        dt = year - self.epoch
        rlon, rlat = math.radians(glon), math.radians(glat)
        srlon, srlat, crlon, crlat = math.sin(rlon), math.sin(rlat), math.cos(rlon), math.cos(rlat)
        srlat2, crlat2 = srlat * srlat, crlat * crlat
        sp = [0.0] * 13
        cp = [0.0] * 13
        sp[0], cp[0], sp[1], cp[1] = 0.0, 1.0, srlon, crlon
        for m in range(2, MAXDEG + 1):
            sp[m] = sp[1] * cp[m - 1] + cp[1] * sp[m - 1]
            cp[m] = cp[1] * cp[m - 1] - sp[1] * sp[m - 1]
        q = math.sqrt(a2 - c2 * srlat2)
        q1 = alt_km * q
        q2 = ((q1 + a2) / (q1 + b2)) ** 2
        ct = srlat / math.sqrt(q2 * crlat2 + srlat2)
        st = math.sqrt(1.0 - ct * ct)
        r2 = alt_km * alt_km + 2.0 * q1 + (a4 - c4 * srlat2) / (q * q)
        r = math.sqrt(r2)
        d = math.sqrt(a2 * crlat2 + b2 * srlat2)
        ca = (alt_km + d) / r
        sa = c2 * crlat * srlat / (r * d)
        aor = re / r
        ar = aor * aor
        br = bt = bp = bpp = 0.0
        p = [[0.0] * 13 for _ in range(13)]
        dp = [[0.0] * 13 for _ in range(13)]
        tc = [[0.0] * 13 for _ in range(13)]
        p[0][0], dp[0][0] = 1.0, 0.0
        for n in range(1, MAXDEG + 1):
            ar *= aor
            m = 0
            D4 = n + 1
            while D4 > 0:
                if n == m:
                    p[m][n] = st * p[m - 1][n - 1]
                    dp[m][n] = st * dp[m - 1][n - 1] + ct * p[m - 1][n - 1]
                elif n == 1 and m == 0:
                    p[m][n] = ct * p[m][n - 1]
                    dp[m][n] = ct * dp[m][n - 1] - st * p[m][n - 1]
                elif n > 1 and n != m:
                    if m > n - 2:
                        p[m][n - 2] = 0.0
                        dp[m][n - 2] = 0.0
                    p[m][n] = ct * p[m][n - 1] - self.k[m][n] * p[m][n - 2]
                    dp[m][n] = ct * dp[m][n - 1] - st * p[m][n - 1] - self.k[m][n] * dp[m][n - 2]
                tc[m][n] = self.c[m][n] + dt * self.cd[m][n]
                if m != 0:
                    tc[n][m - 1] = self.c[n][m - 1] + dt * self.cd[n][m - 1]
                par = ar * p[m][n]
                if m == 0:
                    temp1 = tc[m][n] * cp[m]
                    temp2 = tc[m][n] * sp[m]
                else:
                    temp1 = tc[m][n] * cp[m] + tc[n][m - 1] * sp[m]
                    temp2 = tc[m][n] * sp[m] - tc[n][m - 1] * cp[m]
                bt -= ar * temp1 * dp[m][n]
                bp += self.fm[m] * temp2 * par
                br += self.fn[n] * temp1 * par
                if st == 0.0 and m == 1:
                    if n == 1:
                        self.pp[n] = self.pp[n - 1]
                    else:
                        self.pp[n] = ct * self.pp[n - 1] - self.k[m][n] * self.pp[n - 2]
                    bpp += self.fm[m] * temp2 * ar * self.pp[n]
                D4 -= 1
                m += 1
        bp = bpp if st == 0.0 else bp / st
        X = -bt * ca - br * sa
        Y = bp
        Z = bt * sa - br * ca
        return X, Y, Z


def main():
    cof, tests = sys.argv[1], sys.argv[2]
    wmm = WMM(cof)
    worst = 0.0
    n = 0
    with open(tests) as f:
        for line in f:
            s = line.split()
            if len(s) < 8 or s[0].startswith("#"):
                continue
            try:
                year, alt, lat, lon = map(float, s[:4])
                X_ref, Y_ref, Z_ref = map(float, s[7:10])   # fields 8-10
            except ValueError:
                continue
            X, Y, Z = wmm.evaluate(lat, lon, alt, year)
            err = max(abs(X - X_ref), abs(Y - Y_ref), abs(Z - Z_ref))
            worst = max(worst, err)
            n += 1
            if err > 0.1:
                print(f"MISMATCH year={year} alt={alt} lat={lat} lon={lon}: "
                      f"got X={X:.1f} Y={Y:.1f} Z={Z:.1f} ref X={X_ref} Y={Y_ref} Z={Z_ref}")
    print(f"checked {n} test points, worst error {worst:.3f} nT ->",
          "PASS" if worst <= 0.1 else "FAIL")


if __name__ == "__main__":
    main()
