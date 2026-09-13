"""Convert KiCad fab outputs to JLCPCB's assembly formats.

  python tools/make_jlc.py --pos <kicad pos csv> --bom <docs/BOM.csv> --out <dir/prefix>

Writes <prefix>-cpl-jlcpcb.csv (component placement list) and
<prefix>-bom-jlcpcb.csv (bill of materials) in the column layout JLCPCB's
uploader expects:

  CPL: Designator, Mid X, Mid Y, Layer, Rotation
       (KiCad placement values passed through: mm, board origin as exported,
        Y positive upwards - the same values JLCPCB's own KiCad plugin sends)
  BOM: Comment, Designator, Footprint, LCSC Part #, Manufacturer, MPN
       LCSC Part # is left blank on purpose: JLCPCB's uploader matches parts
       from the MPN column and shows each match for confirmation, which is
       safer than a guessed catalogue number silently ordering the wrong part.
"""
import argparse
import csv
import io
import os


def read_csv(path):
    with io.open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, header, rows):
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"wrote {path} ({len(rows)} rows)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pos", required=True)
    ap.add_argument("--bom", required=True)
    ap.add_argument("--out", required=True, help="output path prefix")
    ap.add_argument("--lcsc", help="optional CSV with columns MPN,LCSC[,Status,Note] to "
                                   "fill the LCSC Part # column")
    a = ap.parse_args()
    lcsc = {}
    if a.lcsc and os.path.exists(a.lcsc):
        lcsc = {r["MPN"].strip(): r["LCSC"].strip() for r in read_csv(a.lcsc) if r["LCSC"].strip()}

    # ---------------------------------------------------------------- CPL
    cpl = []
    for r in read_csv(a.pos):
        side = r["Side"].strip().lower()
        cpl.append([r["Ref"], f"{float(r['PosX']):.4f}mm", f"{float(r['PosY']):.4f}mm",
                    "Top" if side == "top" else "Bottom", f"{float(r['Rot']):.0f}"])
    cpl.sort(key=lambda x: (x[0].rstrip("0123456789"), int("".join(c for c in x[0] if c.isdigit()) or 0)))
    write_csv(a.out + "-cpl-jlcpcb.csv", ["Designator", "Mid X", "Mid Y", "Layer", "Rotation"], cpl)

    # ---------------------------------------------------------------- BOM
    placed = {row[0] for row in cpl}
    bom, missing = [], []
    for r in read_csv(a.bom):
        refs = [x.strip() for x in r["References"].split(",") if x.strip()]
        refs_on_board = [x for x in refs if x in placed]
        missing += [x for x in refs if x not in placed]
        if not refs_on_board:
            continue          # mechanical / not-placed items (e.g. mounting hardware)
        # JLCPCB matches on the Comment: give it the description (e.g. "LED
        # green 0603", "Resistor 10K 1% 0603") rather than a net-name value
        # like "PWR", and the MPN when it is a real part number
        mpn = r.get("MPN", "").strip()
        desc = r.get("Description", "").strip()
        comment = desc or r["Value"]
        if mpn and "series" not in mpn.lower():
            comment = f"{mpn} {desc}".strip() if desc and mpn not in desc else (mpn or desc)
        # map key "MPN|Value" wins over bare "MPN" (generic MPNs such as
        # "CL10 series" cover several values)
        part = lcsc.get(f"{mpn}|{r['Value']}", lcsc.get(mpn, ""))
        bom.append([comment, ",".join(refs_on_board), r["Footprint"], part,
                    r.get("Manufacturer", ""), mpn])
    write_csv(a.out + "-bom-jlcpcb.csv",
              ["Comment", "Designator", "Footprint", "LCSC Part #", "Manufacturer", "MPN"], bom)
    in_bom = {x for row in bom for x in row[1].split(",")}
    unlisted = sorted(placed - in_bom)
    if missing:
        print("BOM references not in placement file (not assembled):", ", ".join(missing))
    if unlisted:
        print("WARNING placed parts missing from BOM:", ", ".join(unlisted))


if __name__ == "__main__":
    main()
