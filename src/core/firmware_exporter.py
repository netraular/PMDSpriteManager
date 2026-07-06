"""
Firmware sprite exporter.

Converts a PMD Collab character (8-direction isometric `Walk` animation) into the
simple "overworld" spritesheet format used by the lv_port_pc_vscode firmware
(`graphics/species/pokemon`):

  * One PNG per creature, 2 columns x 4 rows, fixed cell size (64x64 by default
    -> a 128x256 sheet), creature centered in each cell.
  * Cell layout (matches firmware `PetSpriteLayout::make_pokemon_layout`):

        row0: [ UP   f0 ][ LEFT  f0 ]
        row1: [ UP   f1 ][ LEFT  f1 ]
        row2: [ DOWN f0 ][ RIGHT f0 ]
        row3: [ DOWN f1 ][ RIGHT f1 ]

    where f0 = first walk frame, f1 = middle walk frame.

The module is GUI-agnostic (only depends on Pillow + the std library) so it can be
reused from a CLI script and from the Tkinter app.
"""

import os
import shutil
import xml.etree.ElementTree as ET

from PIL import Image

# --- PMD sprite-sheet direction rows -----------------------------------------
# PMD `-Anim.png` sheets store one direction per row, counter-clockwise starting
# from South (Down). Edit these if a future asset set uses a different order.
PMD_ROW_DOWN = 0   # South
PMD_ROW_RIGHT = 2  # East
PMD_ROW_UP = 4     # North
PMD_ROW_LEFT = 6   # West

DEFAULT_CELL = 64
WALK_ANIM_FILE = "Walk-Anim.png"
ANIM_DATA_FILE = "AnimData.xml"

# The data-driven layout descriptor shipped next to the sheets. This is the
# single source of truth and is byte-identical to the `_layout.json` that both
# the hibitomo web content-editor and the lv_port_pc_vscode firmware ship in
# their `graphics/species/pokemon/` folders (style: "explicit").
EXPLICIT_LAYOUT_JSON = """{
  "style": "explicit",
  "cols": 2,
  "rows": 4,
  "walk_style": "stride",
  "walk": {
    "up":    [{ "col": 0, "row": 0 }, { "col": 0, "row": 1 }],
    "down":  [{ "col": 0, "row": 2 }, { "col": 0, "row": 3 }],
    "left":  [{ "col": 1, "row": 0 }, { "col": 1, "row": 1 }],
    "right": [{ "col": 1, "row": 2 }, { "col": 1, "row": 3 }]
  },
  "idle": {
    "up":    [{ "col": 0, "row": 0 }],
    "down":  [{ "col": 0, "row": 2 }],
    "left":  [{ "col": 1, "row": 0 }],
    "right": [{ "col": 1, "row": 2 }]
  },
  "description": "HeartGold overworld, fully data-driven: 2 walk frames per direction stacked vertically in a 2x2 sub-block. col0 = UP (rows 0-1) / DOWN (rows 2-3); col1 = LEFT (rows 0-1) / RIGHT (rows 2-3). Cell size derived from the sheet (64x64 in the shipped 128x256 sheets)."
}
"""

# Repo-relative destination for each generation target. The exporter mirrors this
# path under `<output>/<target>/` so the resulting tree can be copied straight
# into the corresponding repository root. Both targets receive identical assets
# (the web and firmware pokemon sheets are byte-identical); only the folder the
# sheets live in differs between the two projects.
TARGET_RELPATHS = {
    "firmware": "shared/services/pet/assets/graphics/species/pokemon",
    "web": "local-content/projects/default/shared/services/pet/assets/graphics/species/pokemon",
}


def _parse_anim_frame_size(animdata_path, anim_name="Walk"):
    """Return (frame_width, frame_height) for an animation, resolving <CopyOf>."""
    tree = ET.parse(animdata_path)
    root = tree.getroot()

    anims = {}
    for anim in root.iter("Anim"):
        name_el = anim.find("Name")
        if name_el is None:
            continue
        anims[name_el.text] = anim

    seen = set()
    name = anim_name
    while name and name not in seen:
        seen.add(name)
        anim = anims.get(name)
        if anim is None:
            return None
        copy_of = anim.find("CopyOf")
        if copy_of is not None and copy_of.text:
            name = copy_of.text
            continue
        fw = anim.find("FrameWidth")
        fh = anim.find("FrameHeight")
        if fw is None or fh is None:
            return None
        return int(fw.text), int(fh.text)
    return None


def _centered(frame, cell):
    """Scale a frame to fit inside `cell`x`cell` (only if larger) and center it."""
    fw, fh = frame.size
    scale = min(1.0, cell / max(fw, fh))
    if scale < 1.0:
        frame = frame.resize((max(1, int(fw * scale)), max(1, int(fh * scale))),
                             Image.NEAREST)
        fw, fh = frame.size
    canvas = Image.new("RGBA", (cell, cell), (0, 0, 0, 0))
    canvas.paste(frame, ((cell - fw) // 2, (cell - fh) // 2), frame)
    return canvas


def export_project(project_path, output_png, cell=DEFAULT_CELL):
    """
    Convert one PMD character folder into a firmware overworld spritesheet.

    `project_path` must contain an `Animations/` subfolder with `AnimData.xml`
    and `Walk-Anim.png`. Returns the output path on success or raises ValueError.
    """
    animations = os.path.join(project_path, "Animations")
    animdata = os.path.join(animations, ANIM_DATA_FILE)
    walk_sheet = os.path.join(animations, WALK_ANIM_FILE)

    if not os.path.exists(walk_sheet):
        raise ValueError(f"{WALK_ANIM_FILE} not found")
    if not os.path.exists(animdata):
        raise ValueError(f"{ANIM_DATA_FILE} not found")

    size = _parse_anim_frame_size(animdata, "Walk")
    if not size:
        raise ValueError("Walk frame size not found in AnimData.xml")
    fw, fh = size

    sheet = Image.open(walk_sheet).convert("RGBA")
    sw, sh = sheet.size
    cols = max(1, sw // fw)
    rows = max(1, sh // fh)

    def crop(dir_row, frame_col):
        r = min(dir_row, rows - 1)
        c = min(frame_col, cols - 1)
        box = (c * fw, r * fh, (c + 1) * fw, (r + 1) * fh)
        return sheet.crop(box)

    f0 = 0
    f1 = cols // 2 if cols > 1 else 0

    # Build the 8 cells we need.
    up_f0 = _centered(crop(PMD_ROW_UP, f0), cell)
    up_f1 = _centered(crop(PMD_ROW_UP, f1), cell)
    left_f0 = _centered(crop(PMD_ROW_LEFT, f0), cell)
    left_f1 = _centered(crop(PMD_ROW_LEFT, f1), cell)
    down_f0 = _centered(crop(PMD_ROW_DOWN, f0), cell)
    down_f1 = _centered(crop(PMD_ROW_DOWN, f1), cell)
    right_f0 = _centered(crop(PMD_ROW_RIGHT, f0), cell)
    right_f1 = _centered(crop(PMD_ROW_RIGHT, f1), cell)

    out = Image.new("RGBA", (cell * 2, cell * 4), (0, 0, 0, 0))
    # col0 (x=0) = UP/DOWN, col1 (x=cell) = LEFT/RIGHT
    out.paste(up_f0, (0, 0), up_f0)
    out.paste(left_f0, (cell, 0), left_f0)
    out.paste(up_f1, (0, cell), up_f1)
    out.paste(left_f1, (cell, cell), left_f1)
    out.paste(down_f0, (0, cell * 2), down_f0)
    out.paste(right_f0, (cell, cell * 2), right_f0)
    out.paste(down_f1, (0, cell * 3), down_f1)
    out.paste(right_f1, (cell, cell * 3), right_f1)

    os.makedirs(os.path.dirname(output_png), exist_ok=True)
    out.save(output_png)
    return output_png


def _output_name(folder_name):
    """'0001 Bulbasaur' -> '001'. Falls back to a sanitized folder name."""
    token = folder_name.split(" ", 1)[0]
    try:
        return f"{int(token):03d}"
    except ValueError:
        return folder_name.replace(" ", "_")


def _write_layout(folder):
    """Write the explicit `_layout.json` descriptor into `folder`."""
    with open(os.path.join(folder, "_layout.json"), "w", encoding="utf-8") as f:
        f.write(EXPLICIT_LAYOUT_JSON)


def _stage_target(base_dir, sheets, target, log):
    """
    Mirror the generated sheets + `_layout.json` under `<base_dir>/<target>/<relpath>`
    so the tree can be copied straight into the matching repository root.
    """
    relpath = TARGET_RELPATHS.get(target)
    if not relpath:
        log(f"  WARN unknown target '{target}', skipped")
        return
    dest = os.path.join(base_dir, target, *relpath.split("/"))
    os.makedirs(dest, exist_ok=True)
    for png in sheets:
        shutil.copy2(png, os.path.join(dest, os.path.basename(png)))
    _write_layout(dest)
    log(f"  target '{target}' -> {os.path.join(base_dir, target)}"
        f"  (copy its contents into the repo root: {relpath}/)")


def export_all(downloads_dir, output_dir, cell=DEFAULT_CELL, log=print,
               targets=("firmware", "web")):
    """
    Convert every project subfolder of `downloads_dir` into `output_dir`.

    The raw sheets + explicit `_layout.json` are written flat into `output_dir`.
    For every name in `targets` (a subset of TARGET_RELPATHS, e.g. "firmware",
    "web"), a copy-ready tree is additionally staged under
    `<output_dir>/<target>/<repo-relative-path>/` so it can be dropped straight
    into the corresponding repository. Pass `targets=()` for the flat output only.

    Returns (success_count, fail_count). `log` is called with progress strings.
    """
    os.makedirs(output_dir, exist_ok=True)
    ok = fail = 0
    folders = sorted(d for d in os.listdir(downloads_dir)
                     if os.path.isdir(os.path.join(downloads_dir, d)))
    generated = []
    for folder in folders:
        project = os.path.join(downloads_dir, folder)
        out_png = os.path.join(output_dir, _output_name(folder) + ".png")
        try:
            export_project(project, out_png, cell)
            ok += 1
            generated.append(out_png)
            log(f"  OK  {folder} -> {os.path.basename(out_png)}")
        except Exception as e:
            fail += 1
            log(f"  SKIP {folder}: {e}")

    # Write the data-driven layout descriptor alongside the flat sheets.
    _write_layout(output_dir)

    # Stage copy-ready trees for each requested target (web / firmware).
    if generated and targets:
        log("")
        for target in targets:
            _stage_target(output_dir, generated, target, log)

    log(f"\nDone. Success: {ok}, Failed: {fail}")
    return ok, fail
