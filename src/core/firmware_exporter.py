"""
Firmware / web sprite exporter.

Converts a PMD Collab character (8-direction isometric `Walk` + `Idle` +
`Sleep` animations) into the single-sheet "overworld" spritesheet format shared
by the hibitomo web content editor and the lv_port_pc_vscode firmware
(`graphics/species/pokemon`):

  * One PNG per creature, N columns x 17 rows (N = max(walk_n, idle_n, sleep_n)).
    This is the PRINCIPAL (unified) export: it bakes all 8 PMD directions so ONE
    sheet serves both views -- the 4 cardinals for the top-down apps and the 4
    diagonals for the iso apps. The cell size is PER-SPECIES: it is the creature's
    content bounding box (union over all walk + idle + sleep frames) magnified by
    DEFAULT_SCALE, so every creature fills its cell with no dead margin and is
    never clipped. Sheets are therefore variable-sized (and may be non-square) from
    one creature to the next; both consumers derive the cell pixel size from the
    sheet dimensions and grid. (Pass `n_dirs=4` for a legacy top-down-only sheet.)
  * Rows 0-7 = walk cycle (one direction per row), rows 8-15 = the matching idle
    loop, row 16 = the non-directional sleep (lying) loop. Each creature keeps its
    OWN native walk/idle/sleep frame counts -- there is NO fixed grid and NO
    resampling:

        row0: DOWN   walk f0 f1 f2 ... (this creature's native walk frames)
        row1: LEFT   walk ...
        row2: RIGHT  walk ...
        row3: UP     walk ...
        row4: SE (down_right)  walk ...  (iso diagonals)
        row5: NE (up_right)    walk ...
        row6: NW (up_left)     walk ...
        row7: SW (down_left)   walk ...
        row8:  DOWN  idle f0 f1 ...    (this creature's native idle frames)
        row9..15: LEFT/RIGHT/UP + SE/NE/NW/SW idle
        row16: SLEEP f0 f1 ...         (non-directional; one row for all facings)

    Direction rows match the firmware/schema convention (cardinals 0=DOWN, 1=LEFT,
    2=RIGHT, 3=UP; iso diagonals 4=SE, 5=NE, 6=NW, 7=SW).
    Because frame counts differ per creature, each creature carries its OWN
    self-contained data file, `<id>.json`, written next to its sheet: an explicit
    layout (native walk/idle cells + a flat sleep cell list) plus the REAL PMD
    per-frame cadence (`walk_durations` / `idle_durations` / `sleep_durations`,
    taken 1:1 from `AnimData.xml` in game ticks), so both consumers reproduce the
    exact Pokémon Mystery Dungeon timing.

Because the layout is fully data-driven, both consumers read each creature's
`<id>.json` and use the per-direction walk/idle cells + durations straight from
the JSON -- no packing knowledge is hard-coded in the web editor or the firmware.

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
# from South (Down): even rows are the 4 cardinals, odd rows the 4 diagonals.
# Edit these if a future asset set uses a different order.
PMD_ROW_DOWN = 0        # South
PMD_ROW_DOWN_RIGHT = 1  # South-East
PMD_ROW_RIGHT = 2       # East
PMD_ROW_UP_RIGHT = 3    # North-East
PMD_ROW_UP = 4          # North
PMD_ROW_UP_LEFT = 5     # North-West
PMD_ROW_LEFT = 6        # West
PMD_ROW_DOWN_LEFT = 7   # South-West

# Output rows follow the firmware/schema direction convention: the 4 top-down
# cardinals first (0=DOWN, 1=LEFT, 2=RIGHT, 3=UP, consumed by the room/ldtk apps)
# then the 4 isometric diagonals (4=SE, 5=NE, 6=NW, 7=SW, consumed by the iso
# apps). Each output row maps to the PMD source row it is cropped from. This is a
# single UNIFIED sheet: top-down consumers read the cardinal rows exactly as
# before, iso consumers read the diagonals.
OUT_ROW_SOURCE = [
    PMD_ROW_DOWN, PMD_ROW_LEFT, PMD_ROW_RIGHT, PMD_ROW_UP,
    PMD_ROW_DOWN_RIGHT, PMD_ROW_UP_RIGHT, PMD_ROW_UP_LEFT, PMD_ROW_DOWN_LEFT,
]

# Direction names in output-row order. Mirrors @hibitomo/schema SPRITE_DIRS_ALL and
# the firmware `DIR_KEYS`, so the emitted `<id>.json` keys line up across all repos.
DIR_NAMES = ["down", "left", "right", "up",
             "down_right", "up_right", "up_left", "down_left"]

# Number of facing directions baked into the unified sheet (cardinals + diagonals).
NUM_DIRS = len(OUT_ROW_SOURCE)

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
# Upper bound on walk columns. Each creature now keeps its OWN native walk frame
# count (NO resampling to a shared grid); this only caps the very few creatures
# whose native cycle would exceed it. 16 >= firmware PET_MAX_WALK_FRAMES and
# covers every creature in the set (native walk max is 12), so nothing is ever
# dropped and the real per-frame cadence is preserved.
DEFAULT_FRAMES = 16
WALK_ANIM_FILE = "Walk-Anim.png"
IDLE_ANIM_FILE = "Idle-Anim.png"
ANIM_DATA_FILE = "AnimData.xml"

# --- Animated idle -----------------------------------------------------------
# The PMD `Idle` animation (a subtle breathing/blink loop) is baked into extra
# sheet rows below the walk rows so the pet visibly "breathes" while standing
# still instead of freezing on a single frame. Each creature keeps its OWN native
# idle frame count (NO resampling to a shared grid) so the real breathing cadence
# is preserved; the exact per-direction cells are described in the creature's
# `<id>.json`. Idle is laid out at rows 4..7 (one per direction):
#
#     row0..3: DOWN/LEFT/RIGHT/UP  walk  (cols 0..walk_n-1)
#     row4..7: DOWN/LEFT/RIGHT/UP  idle  (cols 0..idle_n-1)
#
# 16 >= firmware PET_MAX_IDLE_FRAMES and covers every creature (native idle max is
# 15), so no idle frame is ever dropped. Creatures with no `Idle-Anim.png` fall
# back to a single static idle cell (walk frame 0).
DEFAULT_IDLE_FRAMES = 16
# First sheet row of the idle block (idle rows = IDLE_ROW_BASE .. IDLE_ROW_BASE+7,
# one per direction, below the 8 walk rows).
IDLE_ROW_BASE = NUM_DIRS  # = 8
# Per-frame idle duration (ms) written to the layout; the device cycles the idle
# cells at this rate. ~1.2s for a 4-frame loop reads as a calm breathing.
DEFAULT_IDLE_FRAME_MS = 300

# --- Sleep -------------------------------------------------------------------
# The PMD `Sleep` animation (the creature lying down asleep) is authored as a
# single NON-directional row (one pose regardless of facing), so it is baked into
# ONE extra sheet row below the idle block and described in the creature's
# `<id>.json` as a flat, direction-agnostic `sleep` cell list. The device/editor
# play it while the pet sleeps and fall back to the idle frame when a creature
# ships no `Sleep-Anim.png`.
#
#     row0..3: DOWN/LEFT/RIGHT/UP  walk
#     row4..7: DOWN/LEFT/RIGHT/UP  idle
#     row8   : SLEEP  (cols 0..sleep_n-1)
#
SLEEP_ANIM_FILE = "Sleep-Anim.png"
# Cap on sleep columns. PMD sleep loops are very short (typically 2 frames), so a
# small cap keeps the row compact; each creature keeps its own native count.
DEFAULT_SLEEP_FRAMES = 8
# Single sheet row holding the sleep loop (below the eight idle rows 8..15).
SLEEP_ROW = IDLE_ROW_BASE + NUM_DIRS  # = 16
# Per-frame sleep duration (ms) fallback when the layout omits `sleep_durations`.
DEFAULT_SLEEP_FRAME_MS = 400

# PMD `AnimData.xml` stores per-frame durations in game *ticks*. The sprites are
# authored/played at a fixed ~30 FPS by convention (SkyTemple/PMD), so one tick
# is ~33 ms. Nothing in the XML asserts this; it is the well-known default. It is
# written as `tick_ms` into each `<id>.json` (alongside the raw tick durations) so
# the web renders the *real* per-frame cadence and the 30 FPS device holds each
# frame for exactly that many ticks.
PMD_TICK_MS = 33

# --- Data-driven layout descriptor -------------------------------------------
# Each creature's `<id>.json` (written next to its sheet) is generated from the
# actual grid so it always matches the packing. It is the single source of truth
# read by both the hibitomo web content-editor and the lv_port_pc_vscode firmware
# (style: "explicit", one row per direction, `frames` walk cells per row, plus the
# real PMD walk/idle tick durations). One entry per output row, in DIR_NAMES order
# (4 cardinals then 4 diagonals); walk rows 0..7, matching idle rows 8..15.
DIR_ROWS = [(name, i) for i, name in enumerate(DIR_NAMES)]


def build_layout_dict(cols, rows=SLEEP_ROW + 1, frames=DEFAULT_FRAMES,
                      idle_frames=DEFAULT_IDLE_FRAMES,
                      idle_frame_ms=DEFAULT_IDLE_FRAME_MS,
                      walk_durations=None, idle_durations=None,
                      sleep_frames=0, sleep_row=SLEEP_ROW,
                      sleep_durations=None, sleep_frame_ms=DEFAULT_SLEEP_FRAME_MS,
                      tick_ms=PMD_TICK_MS, dir_rows=None, idle_row_base=None):
    """
    Build the explicit, data-driven per-creature layout descriptor for a
    `cols` x `rows` sheet whose top rows (0..3) are the DOWN/LEFT/RIGHT/UP walk
    cycles, whose idle rows (IDLE_ROW_BASE..IDLE_ROW_BASE+3) are the matching
    animated idle loops, and whose single `sleep_row` holds the non-directional
    sleep (lying) loop. `idle_frames` >= 2 makes the device play an animated idle
    (breathing) instead of a static standing pose; `sleep_frames` >= 1 adds a
    `sleep` clip (flat, direction-agnostic).

    `walk_durations` / `idle_durations` / `sleep_durations` are the REAL PMD
    per-frame cadences in game **ticks** (one entry per walk / idle / sleep frame),
    taken 1:1 from `AnimData.xml`. Both consumers preserve Pokémon Mystery Dungeon
    timing from these: the 30 FPS device holds each frame for that many ticks; the
    web renders each tick as `tick_ms`. Written straight into the per-creature
    `<id>.json`.
    """
    # `dir_rows` / `idle_row_base` default to the unified 8-direction layout; the
    # legacy 4-direction export passes a 4-entry slice + idle_row_base=4.
    if dir_rows is None:
        dir_rows = DIR_ROWS
    if idle_row_base is None:
        idle_row_base = IDLE_ROW_BASE
    walk = {name: [{"col": c, "row": row} for c in range(frames)]
            for name, row in dir_rows}
    idle = {name: [{"col": c, "row": idle_row_base + row}
                   for c in range(idle_frames)]
            for name, row in dir_rows}
    sleep = ([{"col": c, "row": sleep_row} for c in range(sleep_frames)]
             if sleep_frames > 0 else None)
    return {
        "style": "explicit",
        "cols": cols,
        "rows": rows,
        "walk_style": "stride",
        "tick_ms": tick_ms,
        "idle_frame_ms": idle_frame_ms,
        "sleep_frame_ms": sleep_frame_ms if sleep else None,
        "walk": walk,
        "idle": idle,
        "sleep": sleep,
        "walk_durations": list(walk_durations) if walk_durations else None,
        "idle_durations": list(idle_durations) if idle_durations else None,
        "sleep_durations": list(sleep_durations) if sleep_durations else None,
        "description": (
            "PMD Collab unified overworld+iso, fully data-driven: rows 0.."
            f"{NUM_DIRS - 1} are the walk cycle (0=DOWN, 1=LEFT, 2=RIGHT, 3=UP "
            "cardinals for the top-down apps; 4=SE, 5=NE, 6=NW, 7=SW diagonals for "
            f"the iso apps), columns 0..{frames - 1} (this creature's native walk "
            f"frames, continuous stride); rows {IDLE_ROW_BASE}.."
            f"{IDLE_ROW_BASE + NUM_DIRS - 1} are the matching native idle "
            f"(breathing) loop, columns 0..{idle_frames - 1}; row {sleep_row} is "
            f"the non-directional sleep (lying) loop, columns 0.."
            f"{max(sleep_frames - 1, 0)}. walk/idle/sleep_durations are the real "
            f"PMD per-frame cadence in {tick_ms}ms ticks. Cell size derived from "
            "the sheet (per-species: the creature's content bbox times the export "
            "scale)."
        ),
    }


def dumps_layout(layout):
    """
    Serialize a per-creature layout dict to JSON, keeping each {col,row} cell (and
    each duration array) on a single line (compact, human-readable) while still
    emitting standard JSON that both the web (zod) and firmware (rapidjson) parsers
    accept. Optional keys (durations) are omitted when absent.
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

    lines = [
        "{",
        f'  "style": {json.dumps(layout["style"])},',
        f'  "cols": {layout["cols"]},',
        f'  "rows": {layout["rows"]},',
        f'  "walk_style": {json.dumps(layout["walk_style"])},',
        f'  "tick_ms": {layout["tick_ms"]},',
        f'  "idle_frame_ms": {layout["idle_frame_ms"]},',
    ]
    if layout.get("sleep_frame_ms"):
        lines.append(f'  "sleep_frame_ms": {layout["sleep_frame_ms"]},')
    lines.append(f'  "walk": {dir_map(layout["walk"], 2)},')
    lines.append(f'  "idle": {dir_map(layout["idle"], 2)},')
    if layout.get("sleep"):
        arr = ", ".join(cell(c) for c in layout["sleep"])
        lines.append(f'  "sleep": [{arr}],')
    if layout.get("walk_durations"):
        lines.append(f'  "walk_durations": {json.dumps(layout["walk_durations"])},')
    if layout.get("idle_durations"):
        lines.append(f'  "idle_durations": {json.dumps(layout["idle_durations"])},')
    if layout.get("sleep_durations"):
        lines.append(f'  "sleep_durations": {json.dumps(layout["sleep_durations"])},')
    lines.append(f'  "description": {json.dumps(layout["description"])}')
    lines.append("}")
    return "\n".join(lines) + "\n"

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


def _column_durations_ticks(native_durs, n, fallback_ticks=4):
    """Per-output-column durations in PMD game *ticks* for a sheet whose `n`
    columns are the creature's native frames 0..n-1 (no resampling, so this is a
    1:1 slice of the animation's `<Durations>`). Storing the raw ticks (not ms)
    keeps the real Pokémon Mystery Dungeon cadence exact for the 30 FPS device,
    which holds each frame for that many ticks. `native_durs=None` (no timing
    data) yields a uniform `fallback_ticks` per column so the clip still plays."""
    if not native_durs:
        return [fallback_ticks] * n
    return [native_durs[i] if i < len(native_durs) else native_durs[-1]
            for i in range(n)]


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
                   scale=DEFAULT_SCALE, idle_frames=DEFAULT_IDLE_FRAMES,
                   n_dirs=NUM_DIRS):
    """
    Convert one PMD character folder into a unified overworld+iso spritesheet.

    Produces a grid of `max(walk_n, idle_n, sleep_n)` columns x (`2*n_dirs`+sleep)
    rows, where `walk_n` / `idle_n` are THIS creature's native walk / idle frame
    counts (no resampling; `frames` / `idle_frames` only cap them). With the default
    `n_dirs=8` (the principal export), rows 0..7 are the walk cycles for the 4
    cardinals (top-down) + 4 diagonals (iso) and rows 8..15 the matching native idle
    loops (or a single static walk-frame-0 cell when the creature ships no
    `Idle-Anim.png`); row 16 is the non-directional sleep loop. Pass `n_dirs=4` for
    the legacy top-down-only sheet (rows 0..3 walk, 4..7 idle, 8 sleep).
    The CELL SIZE IS PER-SPECIES: it equals the union content bounding box over
    every placed walk AND idle frame, magnified by `scale` (nearest-neighbour), so
    neither block is clipped and both share one cell size. `project_path` must
    contain an `Animations/` subfolder with `AnimData.xml` and `Walk-Anim.png`.
    Also writes the creature's self-contained data file (`<id>.json`) next to the
    sheet: its explicit layout plus the real PMD per-frame cadence
    (`walk_durations` / `idle_durations`, in ticks). Returns `(output_path, layout)`
    on success (or raises ValueError).
    """
    animations = os.path.join(project_path, "Animations")
    animdata = os.path.join(animations, ANIM_DATA_FILE)
    walk_sheet = os.path.join(animations, WALK_ANIM_FILE)

    if not os.path.exists(walk_sheet):
        raise ValueError(f"{WALK_ANIM_FILE} not found")
    if not os.path.exists(animdata):
        raise ValueError(f"{ANIM_DATA_FILE} not found")

    # Direction layout for this export. Default is the unified 8-dir sheet; the
    # legacy path (n_dirs=4) slices to the cardinals only. idle rows follow the
    # walk rows; the single sleep row sits below both blocks.
    out_source = OUT_ROW_SOURCE[:n_dirs]
    dir_rows = DIR_ROWS[:n_dirs]
    idle_base = n_dirs
    sleep_row = 2 * n_dirs

    size = _parse_anim_frame_size(animdata, "Walk")
    if not size:
        raise ValueError("Walk frame size not found in AnimData.xml")
    wfw, wfh = size
    walk_img = Image.open(walk_sheet).convert("RGBA")
    walk_crop, walk_cols, _ = _crop_grid(walk_img, wfw, wfh)

    # Keep this creature's native walk cycle as-is (no resampling), capped so it
    # never exceeds the firmware's per-direction walk-frame limit.
    walk_n = min(walk_cols, frames)
    src_cols = list(range(walk_n))

    # (out_row, out_col, native_frame, crop_box) tuples for every placed cell. The
    # crop box (per animation) is applied later so the walk and idle blocks are
    # each cropped to their own union footprint, then bottom-anchored into a shared
    # per-species cell.
    walk_placed = [(out_row, out_col, walk_crop(pmd_row, src_col))
                   for out_row, pmd_row in enumerate(out_source)
                   for out_col, src_col in enumerate(src_cols)]
    walk_box = _union_bbox(fr for _, _, fr in walk_placed)

    # Idle block (rows IDLE_ROW_BASE..+3). Keep the creature's native Idle
    # animation frame-for-frame when present; otherwise a single static idle cell
    # (walk frame 0). No resampling, so the real breathing cadence is preserved.
    idle_path = os.path.join(animations, IDLE_ANIM_FILE)
    idle_size = _parse_anim_frame_size(animdata, "Idle") if os.path.exists(idle_path) else None
    if idle_size:
        ifw, ifh = idle_size
        idle_img = Image.open(idle_path).convert("RGBA")
        idle_crop, idle_cols, _ = _crop_grid(idle_img, ifw, ifh)
        idle_n = min(idle_cols, idle_frames)
        idle_src = list(range(idle_n))
        idle_placed = [(idle_base + out_row, out_col, idle_crop(pmd_row, isrc))
                       for out_row, pmd_row in enumerate(out_source)
                       for out_col, isrc in enumerate(idle_src)]
        idle_ticks = _column_durations_ticks(_parse_anim_durations(animdata, "Idle"), idle_n)
    else:
        # Static fallback: a single idle cell = walk frame 0.
        idle_n = 1
        idle_placed = [(idle_base + out_row, 0, walk_crop(pmd_row, 0))
                       for out_row, pmd_row in enumerate(out_source)]
        idle_ticks = [max(1, round(DEFAULT_IDLE_FRAME_MS / PMD_TICK_MS))]
    idle_box = _union_bbox(fr for _, _, fr in idle_placed)

    # Sleep block: a single NON-directional row (SLEEP_ROW). PMD authors `Sleep`
    # as one row (the creature lies down in one pose regardless of facing), so
    # every sleep column is cropped from source row 0. Omitted when the creature
    # ships no `Sleep-Anim.png` (both consumers then fall back to the idle frame).
    sleep_path = os.path.join(animations, SLEEP_ANIM_FILE)
    sleep_size = _parse_anim_frame_size(animdata, "Sleep") if os.path.exists(sleep_path) else None
    if sleep_size:
        sfw, sfh = sleep_size
        sleep_img = Image.open(sleep_path).convert("RGBA")
        sleep_crop, sleep_cols, _ = _crop_grid(sleep_img, sfw, sfh)
        sleep_n = min(sleep_cols, DEFAULT_SLEEP_FRAMES)
        sleep_placed = [(sleep_row, out_col, sleep_crop(0, ssrc))
                        for out_col, ssrc in enumerate(range(sleep_n))]
        sleep_ticks = _column_durations_ticks(_parse_anim_durations(animdata, "Sleep"), sleep_n)
    else:
        sleep_n = 0
        sleep_placed = []
        sleep_ticks = None
    sleep_box = _union_bbox(fr for _, _, fr in sleep_placed)

    # Real per-frame cadence in PMD ticks for the web preview / device (1:1 with
    # the native frames).
    walk_ticks = _column_durations_ticks(_parse_anim_durations(animdata, "Walk"), walk_n)

    # Per-species cell size = union of the walk, idle and sleep content boxes * scale.
    def _dims(box, fallback_w, fallback_h):
        if box is None:
            return fallback_w, fallback_h
        return box[2] - box[0], box[3] - box[1]

    ww, wh = _dims(walk_box, wfw, wfh)
    iw, ih = _dims(idle_box, 0, 0)
    sw, sh = _dims(sleep_box, 0, 0)
    cell_w = max(ww, iw, sw) * scale
    cell_h = max(wh, ih, sh) * scale

    out_cols = max(walk_n, idle_n, sleep_n)
    out_rows = (sleep_row + 1) if sleep_n > 0 else (idle_base + n_dirs)
    out = Image.new("RGBA", (cell_w * out_cols, cell_h * out_rows), (0, 0, 0, 0))

    for out_row, out_col, raw in walk_placed:
        frame = _prepare_frame(raw, walk_box, scale)
        _paste_anchored(out, frame, out_col * cell_w, out_row * cell_h, cell_w, cell_h)
    for out_row, out_col, raw in idle_placed:
        frame = _prepare_frame(raw, idle_box, scale)
        _paste_anchored(out, frame, out_col * cell_w, out_row * cell_h, cell_w, cell_h)
    for out_row, out_col, raw in sleep_placed:
        frame = _prepare_frame(raw, sleep_box, scale)
        _paste_anchored(out, frame, out_col * cell_w, out_row * cell_h, cell_w, cell_h)

    os.makedirs(os.path.dirname(output_png), exist_ok=True)
    out.save(output_png)
    layout = build_layout_dict(out_cols, rows=out_rows, frames=walk_n,
                               idle_frames=idle_n,
                               idle_frame_ms=DEFAULT_IDLE_FRAME_MS,
                               walk_durations=walk_ticks,
                               idle_durations=idle_ticks,
                               sleep_frames=sleep_n,
                               sleep_row=sleep_row,
                               sleep_durations=sleep_ticks,
                               dir_rows=dir_rows,
                               idle_row_base=idle_base)
    # Write the per-creature data file (`<id>.json`) right next to its sheet, so
    # every pokemon/creature owns a self-contained layout + real PMD timing file.
    data_path = os.path.splitext(output_png)[0] + ".json"
    with open(data_path, "w", encoding="utf-8") as f:
        f.write(dumps_layout(layout))
    return output_png, layout


def _output_name(folder_name):
    """'0001 Bulbasaur' -> '001'. Falls back to a sanitized folder name."""
    token = folder_name.split(" ", 1)[0]
    try:
        return f"{int(token):03d}"
    except ValueError:
        return folder_name.replace(" ", "_")


def _stage_target(base_dir, sheets, target, log):
    """
    Mirror the generated sheets + their per-creature `<id>.json` data files under
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
        data = os.path.splitext(png)[0] + ".json"
        if os.path.exists(data):
            shutil.copy2(data, os.path.join(dest, os.path.basename(data)))
    log(f"  target '{target}' -> {os.path.join(base_dir, target)}"
        f"  (copy its contents into the repo root: {relpath}/)")


def export_all(downloads_dir, output_dir, log=print,
               targets=("firmware", "web"), frames=DEFAULT_FRAMES,
               scale=DEFAULT_SCALE, idle_frames=DEFAULT_IDLE_FRAMES,
               n_dirs=NUM_DIRS):
    """
    Convert every project subfolder of `downloads_dir` into `output_dir`.

    Each creature becomes an `max(walk_n, idle_n)` x 8 sheet keeping its OWN native
    walk/idle frame counts (`frames`/`idle_frames` only cap them), with a
    per-species cell size (content bbox * `scale`). The raw sheets + one
    self-contained per-creature data file (`<id>.json`: explicit layout + real PMD
    `walk_durations`/`idle_durations` in ticks) are written flat into `output_dir`.
    For every name in `targets` (a subset of TARGET_RELPATHS, e.g. "firmware",
    "web"), a copy-ready tree is additionally staged under
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
        name = _output_name(folder)
        out_png = os.path.join(output_dir, name + ".png")
        try:
            export_project(project, out_png, frames, scale, idle_frames, n_dirs)
            ok += 1
            generated.append(out_png)
            log(f"  OK  {folder} -> {os.path.basename(out_png)}")
        except Exception as e:
            fail += 1
            log(f"  SKIP {folder}: {e}")

    # Stage copy-ready trees for each requested target (web / firmware).
    if generated and targets:
        log("")
        for target in targets:
            _stage_target(output_dir, generated, target, log)

    log(f"\nDone. Success: {ok}, Failed: {fail}")
    return ok, fail
