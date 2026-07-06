"""
CLI: export PMD characters to the firmware/web overworld spritesheet format.

Runs core.firmware_exporter over a `downloads/` folder (as produced by
download_pmd_sprites.py or the in-app Batch tool) and writes one N x 4 sheet per
creature (columns = full walk cycle, rows = DOWN/LEFT/RIGHT/UP) into an output
folder, plus copy-ready `firmware/` and `web/` subtrees.

Usage:
    python Scripts/export_firmware_sheets.py
    python Scripts/export_firmware_sheets.py --downloads pmd_projects/downloads --out firmware_output
    python Scripts/export_firmware_sheets.py --frames 8 --scale 2
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

from core.firmware_exporter import export_all, DEFAULT_FRAMES, DEFAULT_SCALE  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Export PMD sprites to firmware/web NxN format.")
    ap.add_argument("--downloads", default="pmd_projects/downloads",
                    help="Folder with project subfolders (default pmd_projects/downloads)")
    ap.add_argument("--out", default="firmware_output",
                    help="Output folder for converted sheets (default firmware_output)")
    ap.add_argument("--frames", type=int, default=DEFAULT_FRAMES,
                    help=f"Walk frames per direction / sheet columns (default {DEFAULT_FRAMES}; "
                         "8 == firmware PET_MAX_WALK_FRAMES)")
    ap.add_argument("--scale", type=int, default=DEFAULT_SCALE,
                    help=f"Integer magnification of each sprite (default {DEFAULT_SCALE}; "
                         "nearest-neighbour). The per-species cell size is the creature's "
                         "content bbox times this scale.")
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
          f"            to {out} (per-species cell, frames={args.frames}, "
          f"scale={args.scale}x, target={args.target})\n")
    ok, fail = export_all(downloads, out, targets=targets,
                          frames=args.frames, scale=args.scale)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
