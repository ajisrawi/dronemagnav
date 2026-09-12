"""Prepare the microSD card contents for DroneMagNav.

Creates an `sdcard/` staging folder (copy it to the card root):
  /maps/wdmam.bin   world magnetic anomaly grid (from the WDMAM file)
  /maps/WMM.COF     World Magnetic Model coefficients (NOAA, public)
  /maps/coast.json  offline world coastline (Natural Earth 1:110m, public domain)
  /www/index.html   phone UI
  /cal/             (empty; Tolles-Lawson coefficients are written by the board)

Usage:
  python tools/prepare_sd.py --wdmam data/<wdmam file> [--wmm WMM.COF]
                             [--coast ne_110m_coastline.geojson]

The WDMAM converter accepts: whitespace text "lon lat value" (.xyz / .dat /
.txt, any comment lines), NetCDF (.nc/.grd, needs `netCDF4` or `xarray`), or
GeoTIFF (needs `rasterio`). Output grid is int16 nT, INT16_MIN = no data.
"""
import argparse
import os
import shutil
import struct
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "firmware", "sdcard")
NODATA = -32768


def load_wdmam(path):
    """Return (grid[lat, lon], lon0, lat0, dlon, dlat) with lat increasing."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".nc", ".grd", ".cdf"):
        try:
            import xarray as xr
            ds = xr.open_dataset(path)
            var = [v for v in ds.data_vars if ds[v].ndim == 2][0]
            da = ds[var]
            lat = da[da.dims[0]].values
            lon = da[da.dims[1]].values
            g = da.values.astype(np.float32)
        except ImportError:
            from netCDF4 import Dataset
            ds = Dataset(path)
            var = [v for v in ds.variables if ds.variables[v].ndim == 2][0]
            g = np.array(ds.variables[var][:], dtype=np.float32)
            dims = ds.variables[var].dimensions
            lat = np.array(ds.variables[dims[0]][:])
            lon = np.array(ds.variables[dims[1]][:])
        if lat[0] > lat[-1]:
            lat = lat[::-1]
            g = g[::-1]
        return g, float(lon[0]), float(lat[0]), float(lon[1] - lon[0]), float(lat[1] - lat[0])
    if ext in (".tif", ".tiff"):
        import rasterio
        with rasterio.open(path) as src:
            g = src.read(1).astype(np.float32)
            t = src.transform
            lon0, dlon, lat_top, dlat = t.c, t.a, t.f, t.e
        if dlat < 0:
            g = g[::-1]
            lat0 = lat_top + dlat * g.shape[0]
            dlat = -dlat
        else:
            lat0 = lat_top
        return g, lon0, lat0, dlon, dlat
    # text xyz
    data = np.loadtxt(path, comments=("#", "%", ">"), usecols=(0, 1, 2), dtype=np.float64)
    lon, lat, val = data[:, 0], data[:, 1], data[:, 2]
    lons = np.unique(np.round(lon, 6))
    lats = np.unique(np.round(lat, 6))
    dlon = float(np.median(np.diff(lons)))
    dlat = float(np.median(np.diff(lats)))
    lon0, lat0 = float(lons[0]), float(lats[0])
    nlon = int(round((lons[-1] - lon0) / dlon)) + 1
    nlat = int(round((lats[-1] - lat0) / dlat)) + 1
    g = np.full((nlat, nlon), np.nan, dtype=np.float32)
    ci = np.round((lon - lon0) / dlon).astype(int)
    cj = np.round((lat - lat0) / dlat).astype(int)
    g[cj, ci] = val
    return g, lon0, lat0, dlon, dlat


def write_bin(g, lon0, lat0, dlon, dlat, out):
    # normalise longitude origin to -180 so the firmware's wrap-around works
    if lon0 >= 0 and lon0 + dlon * g.shape[1] > 180.5:
        shift = int(round(180.0 / dlon))
        g = np.roll(g, shift, axis=1)
        lon0 = lon0 - 180.0
    q = np.where(np.isfinite(g), np.clip(np.round(g), -32767, 32767), NODATA).astype("<i2")
    with open(out, "wb") as f:
        f.write(b"WDM1")
        f.write(struct.pack("<iiffffi", q.shape[1], q.shape[0], lon0, lat0, dlon, dlat, 0))
        f.write(q.tobytes(order="C"))
    print(f"wrote {out}: {q.shape[1]} x {q.shape[0]} cells, {dlon:.4f} deg, "
          f"{os.path.getsize(out) / 1e6:.1f} MB, "
          f"valid {np.isfinite(g).mean() * 100:.1f}%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wdmam", required=True)
    ap.add_argument("--wmm", help="WMM.COF from NOAA/NCEI")
    ap.add_argument("--coast", help="Natural Earth 110m coastline GeoJSON")
    a = ap.parse_args()
    for d in ("maps", "www", "cal"):
        os.makedirs(os.path.join(OUT, d), exist_ok=True)
    g, lon0, lat0, dlon, dlat = load_wdmam(a.wdmam)
    write_bin(g, lon0, lat0, dlon, dlat, os.path.join(OUT, "maps", "wdmam.bin"))
    if a.wmm:
        shutil.copy(a.wmm, os.path.join(OUT, "maps", "WMM.COF"))
        print("copied WMM.COF")
    else:
        print("NOTE: --wmm not given; download WMM.COF from "
              "https://www.ncei.noaa.gov/products/world-magnetic-model and rerun")
    if a.coast:
        shutil.copy(a.coast, os.path.join(OUT, "maps", "coast.json"))
        print("copied coastline")
    else:
        print("NOTE: --coast not given; the phone map will show graticule only")
    print("staging folder:", OUT, "-> copy its contents to the microSD root")


if __name__ == "__main__":
    main()
