"""Verify firmware/sdcard/maps/wdmam.bin against the original WDMAM xyz file.

Reads the binary header, then samples lines from the source text (start,
middle, end and a few random offsets) and checks that the cell the firmware
would address (same math as AnomalyMap::ensureWindow/lookup) holds the same
rounded value.

usage: python tools/wdmam_check.py data/wdmam_download.bin firmware/sdcard/maps/wdmam.bin
"""
import os
import random
import struct
import sys

import numpy as np

NODATA = -32768


def main():
    src, binf = sys.argv[1], sys.argv[2]
    with open(binf, "rb") as f:
        magic = f.read(4)
        nlon, nlat, lon0, lat0, dlon, dlat, _ = struct.unpack("<iiffffi", f.read(28))
    assert magic == b"WDM1", magic
    size = os.path.getsize(binf)
    assert size == 32 + nlon * nlat * 2, (size, nlon, nlat)
    print(f"header ok: {nlon} x {nlat}, lon0={lon0} lat0={lat0} d={dlon}x{dlat}, "
          f"{size / 1e6:.1f} MB")
    g = np.memmap(binf, dtype="<i2", mode="r", offset=32, shape=(nlat, nlon))
    valid = (g != NODATA).mean()
    print(f"valid cells {valid * 100:.2f}%, min {g.min()} max {g.max()} "
          f"mean {g[g != NODATA].mean():.1f} nT")

    fsize = os.path.getsize(src)
    offsets = [0, fsize // 3, fsize // 2, 2 * fsize // 3, fsize - 4000]
    random.seed(1)
    offsets += [random.randrange(0, fsize - 4000) for _ in range(40)]
    n = bad = 0
    with open(src, "rb") as f:
        for off in offsets:
            f.seek(off)
            if off:
                f.readline()                       # skip partial line
            for _ in range(5):
                line = f.readline().decode("ascii", "ignore").split()
                if len(line) < 3:
                    continue
                lon, lat, val = float(line[0]), float(line[1]), float(line[2])
                ci = int(round((lon - lon0) / dlon)) % nlon     # firmware wrap
                cj = int(round((lat - lat0) / dlat))
                if not (0 <= cj < nlat):
                    continue
                got = int(g[cj, ci])
                exp = int(np.clip(round(val), -32767, 32767))
                n += 1
                if got != exp:
                    bad += 1
                    print(f"MISMATCH lon={lon} lat={lat} val={val}: bin={got}")
    print(f"checked {n} sample points, {bad} mismatches ->", "PASS" if bad == 0 else "FAIL")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
