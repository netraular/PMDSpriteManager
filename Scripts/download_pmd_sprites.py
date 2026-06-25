"""
Headless bulk downloader for PMD Collab sprites.

Replicates the logic of the in-app Batch tool ("Prepare Pokemon Data" +
"Download Sprites from PMDCollab") from a command line, so a whole ID range
(e.g. the first 151 Pokemon) can be fetched without the GUI.

Output layout (compatible with the Batch tool: pick the parent folder in
"Select Parent Folder"):

    <out>/
    +-- tracker.json
    +-- downloads/
        +-- 0001 Bulbasaur/
        |   +-- portrait.png
        |   +-- sprites.zip
        |   +-- sprite_recolor-0001-0000-0001.png
        |   +-- Animations/            (extracted: AnimData.xml + *-Anim/Offsets/Shadow.png)
        +-- 0004 Charmander/
        +-- ...

Usage:
    python Scripts/download_pmd_sprites.py                 # IDs 1..151 -> ./pmd_projects
    python Scripts/download_pmd_sprites.py --start 1 --end 151 --out pmd_projects
    python Scripts/download_pmd_sprites.py --workers 10
"""

import argparse
import concurrent.futures
import io
import json
import os
import sys
import urllib.error
import urllib.request
import zipfile

TRACKER_URL = "https://raw.githubusercontent.com/PMDCollab/SpriteCollab/master/tracker.json"
PORTRAIT_URL = "https://raw.githubusercontent.com/PMDCollab/SpriteCollab/master/portrait/{id}/Normal.png"
SPRITES_ZIP_URL = "https://spriteserver.pmdcollab.org/assets/{id}/sprites.zip"
RECOLOR_URL = "https://spriteserver.pmdcollab.org/assets/sprite_recolor-{id}-0000-0001.png"

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def _get(url, timeout):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def load_tracker(out_dir):
    """Download tracker.json (id -> {name, ...}) and cache it locally."""
    print("Downloading tracker.json ...")
    data = json.loads(_get(TRACKER_URL, 60).decode("utf-8"))
    tracker_path = os.path.join(out_dir, "tracker.json")
    with open(tracker_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  saved {tracker_path} ({len(data)} entries)")
    return data


def download_one(sprite_id, name, downloads_dir):
    """Download portrait + sprites.zip (extracted) + recolor for a single Pokemon."""
    folder_name = f"{sprite_id} {name}"
    dest = os.path.join(downloads_dir, folder_name)
    animations = os.path.join(dest, "Animations")
    os.makedirs(animations, exist_ok=True)

    # Portrait (non-critical).
    portrait_path = os.path.join(dest, "portrait.png")
    if not os.path.exists(portrait_path):
        try:
            with open(portrait_path, "wb") as f:
                f.write(_get(PORTRAIT_URL.format(id=sprite_id), 20))
        except Exception:
            pass

    # sprites.zip -> extract into Animations/ (the critical payload).
    has_animdata = os.path.exists(os.path.join(animations, "AnimData.xml"))
    if not has_animdata:
        raw = _get(SPRITES_ZIP_URL.format(id=sprite_id), 60)
        with open(os.path.join(dest, "sprites.zip"), "wb") as f:
            f.write(raw)
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            zf.extractall(animations)

    # Recolor master sheet (non-critical).
    recolor_path = os.path.join(dest, f"sprite_recolor-{sprite_id}-0000-0001.png")
    if not os.path.exists(recolor_path):
        try:
            with open(recolor_path, "wb") as f:
                f.write(_get(RECOLOR_URL.format(id=sprite_id), 20))
        except Exception:
            pass

    return folder_name


def main():
    ap = argparse.ArgumentParser(description="Bulk-download PMD Collab sprites.")
    ap.add_argument("--start", type=int, default=1, help="First Pokemon ID (default 1)")
    ap.add_argument("--end", type=int, default=151, help="Last Pokemon ID (default 151)")
    ap.add_argument("--out", default="pmd_projects",
                    help="Parent output folder (default ./pmd_projects)")
    ap.add_argument("--workers", type=int, default=8, help="Parallel downloads (default 8)")
    args = ap.parse_args()

    out_dir = os.path.abspath(args.out)
    downloads_dir = os.path.join(out_dir, "downloads")
    os.makedirs(downloads_dir, exist_ok=True)

    tracker = load_tracker(out_dir)

    targets = []
    for poke in range(args.start, args.end + 1):
        sid = f"{poke:04d}"
        entry = tracker.get(sid) or tracker.get(str(poke))
        if not entry:
            print(f"  skip {sid}: not in tracker")
            continue
        name = (entry.get("name") or "Unknown").strip()
        targets.append((sid, name))

    print(f"\nDownloading {len(targets)} Pokemon ({args.start}..{args.end}) "
          f"with {args.workers} workers -> {downloads_dir}\n")

    ok, fail = 0, 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(download_one, sid, name, downloads_dir): (sid, name)
                   for sid, name in targets}
        for fut in concurrent.futures.as_completed(futures):
            sid, name = futures[fut]
            try:
                fut.result()
                ok += 1
                print(f"  OK  {sid} {name}")
            except Exception as e:
                fail += 1
                print(f"  ERR {sid} {name}: {e}")

    print(f"\nDone. Success: {ok}, Failed: {fail}")
    print(f"Open the Batch tool and 'Select Parent Folder' = {out_dir}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
