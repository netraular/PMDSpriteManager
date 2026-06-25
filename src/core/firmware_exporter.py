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


def export_all(downloads_dir, output_dir, cell=DEFAULT_CELL, log=print):
    """
    Convert every project subfolder of `downloads_dir` into `output_dir`.

    Returns (success_count, fail_count). `log` is called with progress strings.
    """
    os.makedirs(output_dir, exist_ok=True)
    ok = fail = 0
    folders = sorted(d for d in os.listdir(downloads_dir)
                     if os.path.isdir(os.path.join(downloads_dir, d)))
    for folder in folders:
        project = os.path.join(downloads_dir, folder)
        out_png = os.path.join(output_dir, _output_name(folder) + ".png")
        try:
            export_project(project, out_png, cell)
            ok += 1
            log(f"  OK  {folder} -> {os.path.basename(out_png)}")
        except Exception as e:
            fail += 1
            log(f"  SKIP {folder}: {e}")

    # Write the firmware layout descriptor alongside the sheets.
    layout_path = os.path.join(output_dir, "_layout.json")
    if not os.path.exists(layout_path):
        with open(layout_path, "w", encoding="utf-8") as f:
            f.write(
                '{\n'
                '  "style": "pokemon",\n'
                '  "cols": 2,\n'
                '  "rows": 4,\n'
                '  "description": "HeartGold overworld layout: 2 frames per direction '
                'in a 2x2 sub-block. col0=UP/DOWN, col1=LEFT/RIGHT; rows 0-1 top pair, '
                'rows 2-3 bottom pair."\n'
                '}\n'
            )
    log(f"\nDone. Success: {ok}, Failed: {fail}")
    return ok, fail
