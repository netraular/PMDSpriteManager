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
# the firmware bottom-anchors the cell to the tile floor. The 2x magnification is
# baked into the exported PNGs on purpose: web and firmware then render them 1:1
# (no software zoom), so both display the sprites at the exact same size.
DEFAULT_SCALE = 2
# Walk frames per direction in the output sheet. 8 == firmware PET_MAX_WALK_FRAMES,
# which captures the full native cycle of all but a handful of creatures losslessly
# (the few with >8 native frames are evenly resampled down to 8).
DEFAULT_FRAMES = 8
WALK_ANIM_FILE = "Walk-Anim.png"
IDLE_ANIM_FILE = "Idle-Anim.png"
ANIM_DATA_FILE = "AnimData.xml"

# --- Animated idle -----------------------------------------------------------
# The PMD `Idle` animation (a subtle breathing/blink loop) is baked into extra
# sheet rows below the walk rows so the pet visibly "breathes" while standing
# still instead of freezing on a single frame. Because every creature shares one
# `_layout.json`, the idle is standardized to a fixed column count (resampled from
# each creature's native idle cycle) laid out at rows 4..7 (one per direction):
#
#     row0..3: DOWN/LEFT/RIGHT/UP  walk  (cols 0..DEFAULT_FRAMES-1)
#     row4..7: DOWN/LEFT/RIGHT/UP  idle  (cols 0..DEFAULT_IDLE_FRAMES-1)
#
# 8 == firmware PET_MAX_IDLE_FRAMES. Creatures with no `Idle-Anim.png` fall back
# to a static idle (walk frame 0 replicated) so the grid stays uniform.
DEFAULT_IDLE_FRAMES = 4
# First sheet row of the idle block (idle rows = IDLE_ROW_BASE .. IDLE_ROW_BASE+3).
IDLE_ROW_BASE = 4
# Per-frame idle duration (ms) written to the layout; the device cycles the idle
# cells at this rate. ~1.2s for a 4-frame loop reads as a calm breathing.
DEFAULT_IDLE_FRAME_MS = 300

# PMD `AnimData.xml` stores per-frame durations in game *ticks*. The sprites are
# authored/played at a fixed ~30 FPS by convention (SkyTemple/PMD), so one tick
# is ~33 ms. Nothing in the XML asserts this; it is the well-known default. Used
# only for the `_timings.json` companion (see below) that lets the web editor
# preview the *real* per-frame cadence next to the uniform device playback.
PMD_TICK_MS = 33

# --- Data-driven layout descriptor -------------------------------------------
# The `_layout.json` shipped next to the sheets is generated from the actual grid
# so it always matches the packing. It is the single source of truth read by both
# the hibitomo web content-editor and the lv_port_pc_vscode firmware
# (style: "explicit", one row per direction, `frames` walk cells per row).
DIR_ROWS = [("down", 0), ("left", 1), ("right", 2), ("up", 3)]


def build_layout_dict(cols, rows=8, frames=DEFAULT_FRAMES,
                      idle_frames=DEFAULT_IDLE_FRAMES,
                      idle_frame_ms=DEFAULT_IDLE_FRAME_MS):
    """
    Build the explicit, data-driven layout descriptor for a `cols` x `rows` sheet
    whose top rows (0..3) are the DOWN/LEFT/RIGHT/UP walk cycles and whose idle
    rows (IDLE_ROW_BASE..IDLE_ROW_BASE+3) are the matching animated idle loops.
    `idle_frames` >= 2 makes the device play an animated idle (breathing) instead
    of a static standing pose.
    """
    walk = {name: [{"col": c, "row": row} for c in range(frames)]
            for name, row in DIR_ROWS}
    idle = {name: [{"col": c, "row": IDLE_ROW_BASE + row}
                   for c in range(idle_frames)]
            for name, row in DIR_ROWS}
    return {
        "style": "explicit",
        "cols": cols,
        "rows": rows,
        "walk_style": "stride",
        "idle_frame_ms": idle_frame_ms,
        "walk": walk,
        "idle": idle,
        "description": (
            "PMD Collab overworld, fully data-driven: rows 0..3 are the walk "
            "cycle (0=DOWN, 1=LEFT, 2=RIGHT, 3=UP), columns 0.."
            f"{frames - 1} resampled to {frames} frames (continuous stride); rows "
            f"{IDLE_ROW_BASE}..{IDLE_ROW_BASE + 3} are the matching animated idle "
            f"(breathing) loop, columns 0..{idle_frames - 1} cycled every "
            f"{idle_frame_ms}ms. Cell size derived from the sheet (per-species: "
            "the creature's content bbox times the export scale)."
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
        f'  "idle_frame_ms": {layout["idle_frame_ms"]},\n'
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


def _parse_anim_durations(animdata_path, anim_name):
    """Return the per-frame duration list (game ticks) for an animation,
    resolving `<CopyOf>`. Returns None when the animation/durations are absent."""
    try:
        root = ET.parse(animdata_path).getroot()
    except Exception:
        return None
    anims = {}
    for anim in root.iter("Anim"):
        name_el = anim.find("Name")
        if name_el is not None and name_el.text:
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
        durs = anim.find("Durations")
        if durs is None:
            return None
        out = [int(d.text) for d in durs.findall("Duration") if d.text]
        return out or None
    return None


def _column_durations_ms(native_durs, src_indices, tick_ms=PMD_TICK_MS,
                         fallback_ticks=4):
    """Per-output-column durations (ms) for a sheet whose columns are the
    `src_indices` resample of an animation's native frames.

    Each native frame's tick budget is split evenly across the (contiguous)
    output columns that reuse it, so the summed output time equals the native
    animation's total — i.e. playing the sheet columns at these durations
    reproduces the real PMD cadence even though frames were duplicated/subsampled
    to a fixed column count. `native_durs=None` (no timing data) yields a uniform
    `fallback_ticks` per column."""
    n = len(src_indices)
    if not native_durs:
        return [round(fallback_ticks * tick_ms)] * n
    counts = {}
    for s in src_indices:
        counts[s] = counts.get(s, 0) + 1
    out = []
    for s in src_indices:
        idx = min(s, len(native_durs) - 1)
        out.append(round(native_durs[idx] / counts[s] * tick_ms))
    return out


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


def _paste_anchored(out, frame, cell_x, cell_y, cell_w, cell_h):
    """
    Paste `frame` into the cell at (cell_x, cell_y) of size (cell_w, cell_h),
    horizontally centered and bottom-anchored. Anchoring the feet to the cell
    bottom keeps the walk and idle blocks aligned even when their content boxes
    differ in size (the idle animation often has a slightly different footprint
    than walk), and matches how the firmware bottom-anchors the cell to the tile
    floor.
    """
    fw, fh = frame.size
    px = cell_x + (cell_w - fw) // 2
    py = cell_y + (cell_h - fh)
    out.paste(frame, (px, py), frame)


def _crop_grid(sheet, fw, fh):
    """Return a `crop(dir_row, frame_col)` closure over a PMD `-Anim.png` sheet."""
    sw, sh = sheet.size
    cols = max(1, sw // fw)
    rows = max(1, sh // fh)

    def crop(dir_row, frame_col):
        r = min(dir_row, rows - 1)
        c = min(frame_col, cols - 1)
        return sheet.crop((c * fw, r * fh, (c + 1) * fw, (r + 1) * fh))

    return crop, cols, rows


def export_project(project_path, output_png, frames=DEFAULT_FRAMES,
                   scale=DEFAULT_SCALE, idle_frames=DEFAULT_IDLE_FRAMES):
    """
    Convert one PMD character folder into an overworld spritesheet.

    Produces a grid of `max(frames, idle_frames)` columns x 8 rows: rows 0..3 are
    the DOWN/LEFT/RIGHT/UP walk cycles (resampled to `frames` columns) and rows
    4..7 are the matching animated idle loops (resampled to `idle_frames` columns
    from the creature's native `Idle` animation, or a static walk-frame-0 fallback
    when the creature ships no `Idle-Anim.png`). The CELL SIZE IS PER-SPECIES: it
    equals the union content bounding box over every placed walk AND idle frame,
    magnified by `scale` (nearest-neighbour), so neither block is clipped and both
    share one cell size. `project_path` must contain an `Animations/` subfolder
    with `AnimData.xml` and `Walk-Anim.png`. Returns `(output_path, timings)` on
    success (or raises ValueError); `timings` is
    `{"walk": [ms per walk column], "idle": [ms per idle column]}` derived from the
    native `<Durations>` (see `_column_durations_ms`) for the web preview.
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
    wfw, wfh = size
    walk_img = Image.open(walk_sheet).convert("RGBA")
    walk_crop, walk_cols, _ = _crop_grid(walk_img, wfw, wfh)

    # Resample this creature's native walk cycle (walk_cols frames) to `frames`.
    src_cols = _resample_indices(walk_cols, frames)

    # (out_row, out_col, native_frame, crop_box) tuples for every placed cell. The
    # crop box (per animation) is applied later so the walk and idle blocks are
    # each cropped to their own union footprint, then bottom-anchored into a shared
    # per-species cell.
    walk_placed = [(out_row, out_col, walk_crop(pmd_row, src_col))
                   for out_row, pmd_row in enumerate(OUT_ROW_SOURCE)
                   for out_col, src_col in enumerate(src_cols)]
    walk_box = _union_bbox(fr for _, _, fr in walk_placed)

    # Idle block (rows IDLE_ROW_BASE..+3). Use the creature's native Idle
    # animation when present; otherwise fall back to a static idle (walk frame 0)
    # so every creature keeps the same 8-row grid.
    idle_path = os.path.join(animations, IDLE_ANIM_FILE)
    idle_size = _parse_anim_frame_size(animdata, "Idle") if os.path.exists(idle_path) else None
    if idle_size:
        ifw, ifh = idle_size
        idle_img = Image.open(idle_path).convert("RGBA")
        idle_crop, idle_cols, _ = _crop_grid(idle_img, ifw, ifh)
        idle_src = _resample_indices(idle_cols, idle_frames)
        idle_placed = [(IDLE_ROW_BASE + out_row, out_col, idle_crop(pmd_row, isrc))
                       for out_row, pmd_row in enumerate(OUT_ROW_SOURCE)
                       for out_col, isrc in enumerate(idle_src)]
        idle_ms = _column_durations_ms(_parse_anim_durations(animdata, "Idle"), idle_src)
    else:
        # Static fallback: replicate walk frame 0 across the idle columns.
        idle_placed = [(IDLE_ROW_BASE + out_row, out_col, walk_crop(pmd_row, 0))
                       for out_row, pmd_row in enumerate(OUT_ROW_SOURCE)
                       for out_col in range(idle_frames)]
        idle_ms = [DEFAULT_IDLE_FRAME_MS] * idle_frames
    idle_box = _union_bbox(fr for _, _, fr in idle_placed)

    # Real per-frame cadence (ms) for the web comparison preview.
    walk_ms = _column_durations_ms(_parse_anim_durations(animdata, "Walk"), src_cols)

    # Per-species cell size = union of the walk and idle content boxes * scale.
    def _dims(box, fallback_w, fallback_h):
        if box is None:
            return fallback_w, fallback_h
        return box[2] - box[0], box[3] - box[1]

    ww, wh = _dims(walk_box, wfw, wfh)
    iw, ih = _dims(idle_box, 0, 0)
    cell_w = max(ww, iw) * scale
    cell_h = max(wh, ih) * scale

    out_cols = max(frames, idle_frames)
    out_rows = IDLE_ROW_BASE + 4
    out = Image.new("RGBA", (cell_w * out_cols, cell_h * out_rows), (0, 0, 0, 0))

    for out_row, out_col, raw in walk_placed:
        frame = _prepare_frame(raw, walk_box, scale)
        _paste_anchored(out, frame, out_col * cell_w, out_row * cell_h, cell_w, cell_h)
    for out_row, out_col, raw in idle_placed:
        frame = _prepare_frame(raw, idle_box, scale)
        _paste_anchored(out, frame, out_col * cell_w, out_row * cell_h, cell_w, cell_h)

    os.makedirs(os.path.dirname(output_png), exist_ok=True)
    out.save(output_png)
    return output_png, {"walk": walk_ms, "idle": idle_ms}


def _output_name(folder_name):
    """'0001 Bulbasaur' -> '001'. Falls back to a sanitized folder name."""
    token = folder_name.split(" ", 1)[0]
    try:
        return f"{int(token):03d}"
    except ValueError:
        return folder_name.replace(" ", "_")


def _write_layout(folder, cols, frames=DEFAULT_FRAMES,
                  idle_frames=DEFAULT_IDLE_FRAMES):
    """Write the explicit `_layout.json` descriptor into `folder`."""
    layout = build_layout_dict(cols, rows=IDLE_ROW_BASE + 4, frames=frames,
                               idle_frames=idle_frames)
    with open(os.path.join(folder, "_layout.json"), "w", encoding="utf-8") as f:
        f.write(dumps_layout(layout))


def _write_timings(folder, timings):
    """Write the `_timings.json` companion (per-creature real walk/idle cadence).

    Shape: `{ "tick_ms": 33, "creatures": { "001": {"walk": [ms...], "idle":
    [ms...] }, ... } }`, keyed by the sheet basename (zero-padded id). The device
    ignores it; the web editor uses it to preview the *real* per-frame timing next
    to the uniform playback."""
    doc = {
        "tick_ms": PMD_TICK_MS,
        "description": (
            "Real per-frame cadence (ms) per creature, derived from the PMD "
            "AnimData.xml <Durations> and aligned to the sheet's walk/idle "
            "columns. Consumed only by the web editor's comparison preview."
        ),
        "creatures": timings,
    }
    with open(os.path.join(folder, "_timings.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")


def _stage_target(base_dir, sheets, target, cols, frames, idle_frames, log):
    """
    Mirror the generated sheets + `_layout.json` + `_timings.json` under
    `<base_dir>/<target>/<relpath>` so the tree can be copied straight into the
    matching repository root.
    """
    relpath = TARGET_RELPATHS.get(target)
    if not relpath:
        log(f"  WARN unknown target '{target}', skipped")
        return
    dest = os.path.join(base_dir, target, *relpath.split("/"))
    os.makedirs(dest, exist_ok=True)
    for png in sheets:
        shutil.copy2(png, os.path.join(dest, os.path.basename(png)))
    _write_layout(dest, cols, frames, idle_frames)
    src_timings = os.path.join(base_dir, "_timings.json")
    if os.path.exists(src_timings):
        shutil.copy2(src_timings, os.path.join(dest, "_timings.json"))
    log(f"  target '{target}' -> {os.path.join(base_dir, target)}"
        f"  (copy its contents into the repo root: {relpath}/)")


def export_all(downloads_dir, output_dir, log=print,
               targets=("firmware", "web"), frames=DEFAULT_FRAMES,
               scale=DEFAULT_SCALE, idle_frames=DEFAULT_IDLE_FRAMES):
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
    creature_timings = {}
    for folder in folders:
        project = os.path.join(downloads_dir, folder)
        name = _output_name(folder)
        out_png = os.path.join(output_dir, name + ".png")
        try:
            _, timings = export_project(project, out_png, frames, scale, idle_frames)
            ok += 1
            generated.append(out_png)
            creature_timings[name] = timings
            log(f"  OK  {folder} -> {os.path.basename(out_png)}")
        except Exception as e:
            fail += 1
            log(f"  SKIP {folder}: {e}")

    # Write the data-driven layout descriptor + real-cadence timings alongside the
    # flat sheets.
    _write_layout(output_dir, frames, frames, idle_frames)
    _write_timings(output_dir, creature_timings)

    # Stage copy-ready trees for each requested target (web / firmware).
    if generated and targets:
        log("")
        for target in targets:
            _stage_target(output_dir, generated, target, frames, frames, idle_frames, log)

    log(f"\nDone. Success: {ok}, Failed: {fail}")
    return ok, fail
