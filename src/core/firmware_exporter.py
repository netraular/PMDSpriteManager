"""
Firmware / web sprite exporter.

Converts a PMD Collab character (8-direction isometric `Walk` animation) into the
single-sheet "overworld" spritesheet format shared by the hibitomo web content
editor and the lv_port_pc_vscode firmware (`graphics/species/pokemon`):

  * One PNG per creature, N columns x 4 rows. The cell size is PER-SPECIES: it is
    the creature's content bounding box (union over all walk frames) magnified by
    DEFAULT_SCALE, so every creature fills its cell with no dead margin and is never
    clipped (N = DEFAULT_FRAMES = 8 columns). Sheets are therefore variable-sized
    (and may be non-square) from one creature to the next; both consumers derive the
    cell pixel size from the sheet dimensions and grid.
  * Row = direction, column = walk frame (the FULL walk cycle, resampled to the
    fixed column count so every creature shares one grid):

        row0: DOWN   f0 f1 f2 f3 f4 f5 f6 f7
        row1: LEFT   f0 f1 f2 f3 f4 f5 f6 f7
        row2: RIGHT  f0 f1 f2 f3 f4 f5 f6 f7
        row3: UP     f0 f1 f2 f3 f4 f5 f6 f7

    Direction rows match the firmware convention (0=DOWN, 1=LEFT, 2=RIGHT, 3=UP).
    The walk cycle is resampled from the creature's native frame count (3..12) to
    the fixed column count, so the full movement is preserved for every creature
    while keeping a single shared, data-driven `_layout.json` (style: explicit).

Because the layout is fully data-driven, both consumers read the per-direction
walk cells straight from the JSON -- no packing knowledge is hard-coded in the
web editor or the firmware.

The module is GUI-agnostic (only depends on Pillow + the std library) so it can be
reused from a CLI script and from the Tkinter app.
"""

import json
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

# Output rows follow the firmware direction convention (0=DOWN, 1=LEFT, 2=RIGHT,
# 3=UP); this maps each output row to the PMD source row it is cropped from.
OUT_ROW_SOURCE = [PMD_ROW_DOWN, PMD_ROW_LEFT, PMD_ROW_RIGHT, PMD_ROW_UP]

# Integer magnification applied to each creature's cropped walk frame (nearest-
# neighbour, pixel-perfect). The output CELL SIZE IS PER-SPECIES: it is the
# creature's content bounding box (union over all of its walk frames) times `scale`,
# so no creature is ever clipped and small/large creatures keep their natural
# relative size. Both consumers (web + firmware) derive the cell pixel size from the
# sheet dimensions / grid, so a per-creature (and non-square) cell size just works;
# the firmware bottom-anchors the cell to the tile floor.
DEFAULT_SCALE = 2
# Walk frames per direction in the output sheet. 8 == firmware PET_MAX_WALK_FRAMES,
# which captures the full native cycle of all but a handful of creatures losslessly
# (the few with >8 native frames are evenly resampled down to 8).
DEFAULT_FRAMES = 8
WALK_ANIM_FILE = "Walk-Anim.png"
ANIM_DATA_FILE = "AnimData.xml"

# --- Data-driven layout descriptor -------------------------------------------
# The `_layout.json` shipped next to the sheets is generated from the actual grid
# so it always matches the packing. It is the single source of truth read by both
# the hibitomo web content-editor and the lv_port_pc_vscode firmware
# (style: "explicit", one row per direction, `frames` walk cells per row).
DIR_ROWS = [("down", 0), ("left", 1), ("right", 2), ("up", 3)]


def build_layout_dict(cols, rows=4, frames=DEFAULT_FRAMES):
    """
    Build the explicit, data-driven layout descriptor for an
    `cols` x `rows` sheet whose rows are DOWN/LEFT/RIGHT/UP and whose columns
    are the `frames` walk frames of that direction (idle = column 0).
    """
    walk = {name: [{"col": c, "row": row} for c in range(frames)]
            for name, row in DIR_ROWS}
    idle = {name: [{"col": 0, "row": row}] for name, row in DIR_ROWS}
    return {
        "style": "explicit",
        "cols": cols,
        "rows": rows,
        "walk_style": "stride",
        "walk": walk,
        "idle": idle,
        "description": (
            "PMD Collab overworld, fully data-driven: one row per direction "
            "(0=DOWN, 1=LEFT, 2=RIGHT, 3=UP), columns 0.."
            f"{frames - 1} are the full walk cycle (resampled to {frames} frames); "
            "idle = column 0. Continuous stride. Cell size derived from the sheet "
            "(per-species: the creature's content bbox times the export scale)."
        ),
    }


def dumps_layout(layout):
    """
    Serialize a layout dict to JSON, keeping each {col,row} cell on a single line
    (compact, human-readable) while still emitting standard JSON that both the web
    (zod) and firmware (rapidjson) parsers accept.
    """
    def cell(c):
        return f'{{ "col": {c["col"]}, "row": {c["row"]} }}'

    def dir_map(m, indent):
        pad = " " * indent
        inner = " " * (indent + 2)
        lines = []
        for i, (name, cells) in enumerate(m.items()):
            arr = ", ".join(cell(c) for c in cells)
            comma = "," if i < len(m) - 1 else ""
            lines.append(f'{inner}"{name}": [{arr}]{comma}')
        return "{\n" + "\n".join(lines) + "\n" + pad + "}"

    return (
        "{\n"
        f'  "style": {json.dumps(layout["style"])},\n'
        f'  "cols": {layout["cols"]},\n'
        f'  "rows": {layout["rows"]},\n'
        f'  "walk_style": {json.dumps(layout["walk_style"])},\n'
        f'  "walk": {dir_map(layout["walk"], 2)},\n'
        f'  "idle": {dir_map(layout["idle"], 2)},\n'
        f'  "description": {json.dumps(layout["description"])}\n'
        "}\n"
    )

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


def _prepare_frame(frame, crop_box, scale=DEFAULT_SCALE):
    """
    Crop `frame` to `crop_box` and magnify it by `scale` (integer, nearest-neighbour
    for crisp pixel-art). Returns the resulting image.

    `crop_box` is the creature's shared content bounding box (union over all of its
    frames, in native frame coordinates), so every frame is cropped to the SAME box
    and therefore comes out the SAME pixel size -- which is exactly the per-species
    cell size used to tile the output sheet. Because the crop is a single fixed box
    per creature, frames keep their positions relative to each other, preserving the
    walk bounce / jumps. Nothing is centered or padded: the cell IS the content box,
    so no creature is clipped and there is no dead margin around it. `crop_box` may
    be None (fully transparent creature), in which case the native frame is used
    as-is.
    """
    if crop_box is not None:
        frame = frame.crop(crop_box)
    if scale != 1:
        fw, fh = frame.size
        frame = frame.resize((max(1, fw * scale), max(1, fh * scale)), Image.NEAREST)
    return frame


def _union_bbox(frames):
    """Union of the non-transparent bounding boxes of `frames` (or None if empty)."""
    union = None
    for fr in frames:
        bb = fr.getbbox()
        if bb is None:
            continue
        if union is None:
            union = bb
        else:
            union = (min(union[0], bb[0]), min(union[1], bb[1]),
                     max(union[2], bb[2]), max(union[3], bb[3]))
    return union


def _resample_indices(native_count, target_count):
    """
    Map `target_count` output frames onto `native_count` source frames, evenly.

    When native <= target the cycle is stretched (frames repeat) so no motion is
    lost; when native > target it is evenly subsampled. Always returns a list of
    length `target_count` of valid source indices in [0, native_count).
    """
    if native_count <= 0:
        return [0] * target_count
    if native_count == target_count:
        return list(range(native_count))
    return [min(native_count - 1, (i * native_count) // target_count)
            for i in range(target_count)]


def export_project(project_path, output_png, frames=DEFAULT_FRAMES,
                   scale=DEFAULT_SCALE):
    """
    Convert one PMD character folder into an overworld spritesheet.

    Produces a `frames` x 4 grid (columns = full walk cycle resampled to `frames`,
    rows = DOWN/LEFT/RIGHT/UP). The CELL SIZE IS PER-SPECIES: it equals the
    creature's content bounding box (union over all frames) magnified by `scale`
    (nearest-neighbour), so the sheet is exactly `cell_w*frames` x `cell_h*4` with no
    dead margin and no clipping. `project_path` must contain an `Animations/`
    subfolder with `AnimData.xml` and `Walk-Anim.png`. Returns the output path on
    success or raises ValueError.
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

    # Resample this creature's native walk cycle (cols frames) to `frames`.
    src_cols = _resample_indices(cols, frames)

    # Gather every frame we will actually place, then crop them all to a single
    # shared content bbox. This strips the large empty margin PMD reserves around
    # each sprite so the per-species cell is exactly the creature's real footprint.
    # Using the union over all frames keeps the walk bounce and left/right lean
    # intact (every frame is cropped to the same box, so relative motion is kept).
    placed = [(out_row, out_col, crop(pmd_row, src_col))
              for out_row, pmd_row in enumerate(OUT_ROW_SOURCE)
              for out_col, src_col in enumerate(src_cols)]
    box = _union_bbox(fr for _, _, fr in placed)

    # Per-species cell size = content bbox (or the native frame if fully blank) * scale.
    if box is not None:
        cell_w = (box[2] - box[0]) * scale
        cell_h = (box[3] - box[1]) * scale
    else:
        cell_w, cell_h = fw * scale, fh * scale

    out = Image.new("RGBA", (cell_w * frames, cell_h * 4), (0, 0, 0, 0))
    for out_row, out_col, raw in placed:
        frame = _prepare_frame(raw, box, scale)
        out.paste(frame, (out_col * cell_w, out_row * cell_h), frame)

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


def _write_layout(folder, cols, frames=DEFAULT_FRAMES):
    """Write the explicit `_layout.json` descriptor into `folder`."""
    layout = build_layout_dict(cols, rows=4, frames=frames)
    with open(os.path.join(folder, "_layout.json"), "w", encoding="utf-8") as f:
        f.write(dumps_layout(layout))


def _stage_target(base_dir, sheets, target, cols, frames, log):
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
    _write_layout(dest, cols, frames)
    log(f"  target '{target}' -> {os.path.join(base_dir, target)}"
        f"  (copy its contents into the repo root: {relpath}/)")


def export_all(downloads_dir, output_dir, log=print,
               targets=("firmware", "web"), frames=DEFAULT_FRAMES,
               scale=DEFAULT_SCALE):
    """
    Convert every project subfolder of `downloads_dir` into `output_dir`.

    Each creature becomes a `frames` x 4 sheet (full walk cycle resampled to
    `frames` columns), with a per-species cell size (content bbox * `scale`). The raw
    sheets + explicit `_layout.json` are written flat into `output_dir`. For every
    name in `targets` (a subset of TARGET_RELPATHS, e.g. "firmware", "web"), a
    copy-ready tree is additionally staged under
    `<output_dir>/<target>/<repo-relative-path>/` so it can be dropped straight into
    the corresponding repository. Pass `targets=()` for the flat output only.

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
            export_project(project, out_png, frames, scale)
            ok += 1
            generated.append(out_png)
            log(f"  OK  {folder} -> {os.path.basename(out_png)}")
        except Exception as e:
            fail += 1
            log(f"  SKIP {folder}: {e}")

    # Write the data-driven layout descriptor alongside the flat sheets.
    _write_layout(output_dir, frames, frames)

    # Stage copy-ready trees for each requested target (web / firmware).
    if generated and targets:
        log("")
        for target in targets:
            _stage_target(output_dir, generated, target, frames, frames, log)

    log(f"\nDone. Success: {ok}, Failed: {fail}")
    return ok, fail
