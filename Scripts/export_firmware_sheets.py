"""
CLI: export PMD characters to the firmware overworld spritesheet format.

Runs core.firmware_exporter over a `downloads/` folder (as produced by
download_pmd_sprites.py or the in-app Batch tool) and writes one 2x4 sheet per
creature into an output folder.

Usage:
    python Scripts/export_firmware_sheets.py
    python Scripts/export_firmware_sheets.py --downloads pmd_projects/downloads --out firmware_output
    python Scripts/export_firmware_sheets.py --cell 64
    python Scripts/export_firmware_sheets.py --target firmware
    python Scripts/export_firmware_sheets.py --target web
    python Scripts/export_firmware_sheets.py --target none
"""

import argparse
import os
import sys

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from core.firmware_exporter import export_all  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Export PMD sprites to firmware/web 2x4 format.")
    ap.add_argument("--downloads", default="pmd_projects/downloads",
                    help="Folder with project subfolders (default pmd_projects/downloads)")
    ap.add_argument("--out", default="firmware_output",
                    help="Output folder for converted sheets (default firmware_output)")
    ap.add_argument("--cell", type=int, default=64, help="Cell size in px (default 64)")
    ap.add_argument("--target", choices=["firmware", "web", "both", "none"], default="both",
                    help="Stage copy-ready trees for the hibitomo web, the firmware, "
                         "both (default), or none (flat output only).")
    args = ap.parse_args()

    downloads = os.path.abspath(args.downloads)
    out = os.path.abspath(args.out)
    if not os.path.isdir(downloads):
        print(f"ERROR: downloads folder not found: {downloads}")
        return 1

    targets = {
        "firmware": ("firmware",),
        "web": ("web",),
        "both": ("firmware", "web"),
        "none": (),
    }[args.target]

    print(f"Exporting from {downloads}\n"
          f"            to {out} (cell={args.cell}, target={args.target})\n")
    ok, fail = export_all(downloads, out, cell=args.cell, targets=targets)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
