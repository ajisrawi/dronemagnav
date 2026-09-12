"""Apply the WMM-validation notes to README, design-spec and the PDF generator
(UTF-8 safe; idempotent)."""
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def patch(rel, old, new):
    path = os.path.join(ROOT, rel)
    s = io.open(path, encoding="utf-8").read()
    if new in s:
        print(rel, "already patched")
        return
    assert old in s, ("missing anchor in", rel)
    io.open(path, "w", encoding="utf-8", newline="\n").write(s.replace(old, new))
    print(rel, "patched")


patch("README.md",
      "| Firmware (ESP32-S3, PlatformIO) | `firmware/` | complete source, build + flash instructions |",
      "| Firmware (ESP32-S3, PlatformIO) | `firmware/` | complete source; WMM core-field model "
      "validated 100/100 against NOAA test vectors (0.001 nT) |")

patch("docs/design-spec.md",
      "| PCB electrical DRC | 0 violations (22 silkscreen notes) |",
      "| PCB electrical DRC | 0 violations (22 silkscreen notes) |\n"
      "| WMM evaluator vs NOAA WMM2025 test values | 100/100 points, worst error 0.001 nT "
      "(tools/wmm_check.py) |")

patch("tools/make_design_doc.py",
      '        ["Firmware", "-", "complete source; not yet compile-verified on hardware"]],',
      '        ["WMM core-field evaluator vs NOAA WMM2025 test values", "tools/wmm_check.py",\n'
      '         "100 / 100 points, worst error 0.001 nT"],\n'
      '        ["Firmware", "-", "complete source; not yet compile-verified on hardware"]],')

patch("tools/make_design_doc.py",
      '    with open(OUT_PDF, "wb") as f:\n        w.write(f)\n    print("wrote", OUT_PDF)',
      '    out = OUT_PDF\n'
      '    try:\n'
      '        f = open(out, "wb")\n'
      '    except PermissionError:\n'
      '        out = OUT_PDF.replace(".pdf", "-revA.pdf")\n'
      '        f = open(out, "wb")\n'
      '    with f:\n'
      '        w.write(f)\n'
      '    print("wrote", out)')

for rel in ("README.md", "docs/design-spec.md", "tools/make_design_doc.py"):
    t = io.open(os.path.join(ROOT, rel), encoding="utf-8").read()
    print(rel, "mojibake!" if ("Ã" in t or "â€" in t or "Â·" in t) else "clean")
