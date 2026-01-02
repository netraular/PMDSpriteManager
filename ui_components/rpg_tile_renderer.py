# ui_components/rpg_tile_renderer.py

import os
from PIL import Image, ImageDraw

# Constants for RPG tile grid
TILE_SIZE = 32
GRID_SIZE = 3  # 3x3 tiles
CANVAS_SIZE = TILE_SIZE * GRID_SIZE  # 96x96 pixels


def draw_tile_grid(image, tile_size=TILE_SIZE, grid_color=(180, 180, 180), background_color=(220, 220, 220)):
    """
    Draws a 3x3 grid of tiles on the given image.
    The grid is flat (non-isometric), representing a top-down RPG view.
    """
    draw = ImageDraw.Draw(image)
    
    # Fill background for each tile
    for row in range(GRID_SIZE):
        for col in range(GRID_SIZE):
            x0 = col * tile_size
            y0 = row * tile_size
            x1 = x0 + tile_size
            y1 = y0 + tile_size
            
            # Alternate colors for checkerboard pattern
            if (row + col) % 2 == 0:
                fill_color = background_color
            else:
                fill_color = (200, 200, 200)
            
            draw.rectangle([x0, y0, x1-1, y1-1], fill=fill_color, outline=grid_color)


def draw_pivot_point(image, pivot_x, pivot_y, color=(255, 0, 0), size=3):
    """
    Draws a cross marker at the pivot point location.
    """
    draw = ImageDraw.Draw(image)
    
    # Draw cross
    draw.line((pivot_x - size, pivot_y, pivot_x + size, pivot_y), fill=color, width=2)
    draw.line((pivot_x, pivot_y - size, pivot_x, pivot_y + size), fill=color, width=2)
    
    # Draw small circle around pivot
    draw.ellipse(
        [pivot_x - size - 1, pivot_y - size - 1, pivot_x + size + 1, pivot_y + size + 1],
        outline=color,
        width=1
    )


def draw_sprite_bounds(image, x0, y0, width, height, color=(0, 128, 255)):
    """
    Draws a rectangle showing the sprite boundaries.
    """
    draw = ImageDraw.Draw(image)
    draw.rectangle([x0, y0, x0 + width - 1, y0 + height - 1], outline=color, width=1)


def draw_tile_anchor(image, anchor_x, anchor_y, color=(0, 200, 0), size=4):
    """
    Draws the tile anchor point (bottom center of middle tile).
    """
    draw = ImageDraw.Draw(image)
    
    # Draw a small triangle pointing up at the anchor
    points = [
        (anchor_x, anchor_y),
        (anchor_x - size, anchor_y + size),
        (anchor_x + size, anchor_y + size)
    ]
    draw.polygon(points, fill=color, outline=(0, 128, 0))


def load_sprites_from_json(anim_data, sprite_folder):
    """
    Loads all unique sprites referenced in an animation's JSON data into a map.
    Returns a dict mapping sprite_id -> PIL Image
    """
    loaded_sprites = {}
    
    for group in anim_data.get('sprites', {}).values():
        for frame in group.get('frames', []):
            sprite_id = frame.get('id', '0')
            if sprite_id != '0' and sprite_id not in loaded_sprites:
                sprite_path = os.path.join(sprite_folder, f"sprite_{sprite_id}.png")
                try:
                    loaded_sprites[sprite_id] = Image.open(sprite_path).convert('RGBA')
                except FileNotFoundError:
                    print(f"Warning: Sprite not found at {sprite_path}")
                    loaded_sprites[sprite_id] = None
    
    return loaded_sprites


def calculate_first_frame_anchor_offset(first_frame_info, sprite_map):
    """
    Calculate the offset needed to position the first frame's pivot at the tile anchor.
    
    The tile anchor is at the bottom center of the middle tile.
    The sprite pivot is at the bottom center of the sprite.
    
    Returns:
        tuple: (offset_x, offset_y) to apply to all sprites to center the first frame
    """
    sprite_id = first_frame_info.get("id", "0")
    render_offset = first_frame_info.get("render_offset", [0, 0])
    sprite_img = sprite_map.get(sprite_id) if sprite_id != "0" else None
    
    if not sprite_img:
        return (0, 0)
    
    sprite_width, sprite_height = sprite_img.size
    render_x, render_y = render_offset
    
    # The sprite's pivot (bottom center) in the original coordinate system
    # is at (render_x + sprite_width/2, render_y + sprite_height)
    # We want this to be at (0, 0) relative to the tile anchor
    
    # So the offset to apply is the negative of the pivot position
    offset_x = -(render_x + sprite_width // 2)
    offset_y = -(render_y + sprite_height)
    
    return (offset_x, offset_y)


def generate_rpg_tile_preview_data(anim_data, sprite_map, shadow_sprite=None, scale_factor=1):
    """
    Generates all data needed by AnimationPlayer to display an RPG tile grid preview.
    
    The first sprite of each direction is positioned so its pivot (bottom center) 
    is at the bottom center of the middle tile. All other frames maintain their
    relative positions to the first frame.
    
    Args:
        anim_data: Animation data dictionary containing sprites info
        sprite_map: Dictionary mapping sprite_id to PIL Image
        shadow_sprite: Optional shadow sprite image (not used for RPG view)
        scale_factor: Scale factor for the preview (always 1 for 1x output)
    
    Returns:
        dict with frames, text_data, durations, and rpg_metadata
    """
    tile_size = TILE_SIZE * scale_factor
    canvas_size = tile_size * GRID_SIZE
    
    # Tile anchor is at the bottom center of the middle tile
    # Middle tile is at row 1, col 1 (0-indexed)
    # Its bottom center is at (1.5 * tile_size, 2 * tile_size)
    tile_anchor_x = canvas_size // 2  # Center horizontally
    tile_anchor_y = tile_size * 2     # Bottom of middle tile
    
    all_frames_data = []
    all_group_ids = []
    all_anchor_offsets = []  # Store the anchor offset for each frame's group
    
    # Pre-calculate anchor offset for each group based on its first frame
    group_anchor_offsets = {}
    for group_id in sorted(anim_data["sprites"].keys(), key=int):
        group_data = anim_data["sprites"][group_id]
        frames_in_group = group_data.get("frames", [])
        if frames_in_group:
            first_frame = frames_in_group[0]
            anchor_offset = calculate_first_frame_anchor_offset(first_frame, sprite_map)
            group_anchor_offsets[group_id] = anchor_offset
        else:
            group_anchor_offsets[group_id] = (0, 0)
    
    for group_id in sorted(anim_data["sprites"].keys(), key=int):
        group_data = anim_data["sprites"][group_id]
        frames_in_group = group_data.get("frames", [])
        anchor_offset = group_anchor_offsets[group_id]
        all_frames_data.extend(frames_in_group)
        all_group_ids.extend([group_id] * len(frames_in_group))
        all_anchor_offsets.extend([anchor_offset] * len(frames_in_group))
    
    if not all_frames_data:
        return {"frames": [], "text_data": [], "durations": [], "rpg_metadata": []}
    
    total_frames = len(all_frames_data)
    base_durations = anim_data.get("durations", [1])
    durations = (base_durations * (total_frames // len(base_durations) + 1))[:total_frames]
    
    final_frames = []
    text_data = []
    rpg_metadata = []
    
    for i, frame_info in enumerate(all_frames_data):
        group_id = all_group_ids[i]
        anchor_offset = all_anchor_offsets[i]
        group_data = anim_data["sprites"][group_id]
        
        # Create canvas with alpha channel
        canvas = Image.new('RGBA', (canvas_size, canvas_size), (0, 0, 0, 0))
        
        # Draw the tile grid
        draw_tile_grid(canvas, tile_size)
        
        # Get sprite info
        sprite_id = frame_info.get("id", "0")
        render_offset = frame_info.get("render_offset", [0, 0])
        sprite_img = sprite_map.get(sprite_id) if sprite_id != "0" else None
        
        frame_metadata = {
            "frame_index": i,
            "group_id": group_id,
            "group_name": group_data.get("name", f"group_{group_id}"),
            "sprite_id": sprite_id,
            "duration": durations[i] if i < len(durations) else 1
        }
        
        if sprite_img and render_offset is not None:
            render_x, render_y = render_offset
            sprite_width, sprite_height = sprite_img.size
            
            # Apply the anchor offset to position relative to first frame
            # Then add tile anchor position to place on canvas
            paste_x = tile_anchor_x + render_x + anchor_offset[0]
            paste_y = tile_anchor_y + render_y + anchor_offset[1]
            
            # Calculate pivot point in canvas coordinates
            pivot_canvas_x = paste_x + sprite_width // 2
            pivot_canvas_y = paste_y + sprite_height
            
            # Paste the sprite onto the canvas
            canvas.paste(sprite_img, (int(paste_x), int(paste_y)), sprite_img)
            
            # Draw sprite bounds
            draw_sprite_bounds(canvas, int(paste_x), int(paste_y), sprite_width, sprite_height)
            
            # Draw pivot point for this sprite (red cross)
            draw_pivot_point(canvas, int(pivot_canvas_x), int(pivot_canvas_y), color=(255, 0, 0), size=3)
            
            # Draw tile anchor point (green triangle at bottom center of middle tile)
            draw_tile_anchor(canvas, tile_anchor_x, tile_anchor_y, color=(0, 200, 0), size=4)
            
            # Calculate the relative offset from tile anchor (for JSON export)
            relative_offset_x = render_x + anchor_offset[0]
            relative_offset_y = render_y + anchor_offset[1]
            
            frame_metadata.update({
                "sprite_width": sprite_width,
                "sprite_height": sprite_height,
                "sprite_x": int(paste_x),
                "sprite_y": int(paste_y),
                "pivot_x": sprite_width // 2,  # Relative to sprite top-left
                "pivot_y": sprite_height,       # Relative to sprite top-left
                "relative_offset_x": relative_offset_x,
                "relative_offset_y": relative_offset_y,
                "original_render_offset": list(render_offset)
            })
            
            text_info = (
                f"Sprite: {sprite_id} ({sprite_width}x{sprite_height})\n"
                f"Canvas Pos: ({int(paste_x)}, {int(paste_y)})\n"
                f"Pivot (from sprite): ({sprite_width // 2}, {sprite_height})\n"
                f"Relative to anchor: ({relative_offset_x}, {relative_offset_y})\n"
                f"Duration: {frame_metadata['duration']}"
            )
        else:
            # Draw tile anchor even with no sprite
            draw_tile_anchor(canvas, tile_anchor_x, tile_anchor_y, color=(0, 200, 0), size=4)
            
            frame_metadata.update({
                "sprite_width": 0,
                "sprite_height": 0,
                "sprite_x": 0,
                "sprite_y": 0,
                "pivot_x": 0,
                "pivot_y": 0,
                "relative_offset_x": 0,
                "relative_offset_y": 0,
                "original_render_offset": [0, 0]
            })
            text_info = f"No sprite data\nDuration: {frame_metadata['duration']}"
        
        rpg_metadata.append(frame_metadata)
        
        # Scale up canvas for better visibility in preview
        display_scale = 3
        final_canvas = canvas.resize(
            (canvas.width * display_scale, canvas.height * display_scale),
            Image.NEAREST
        )
        final_frames.append(final_canvas)
        text_data.append(text_info)
    
    return {
        "frames": final_frames,
        "text_data": text_data,
        "durations": durations,
        "thumbnail_size": (400, 400),
        "rpg_metadata": rpg_metadata
    }


def generate_rpg_json_for_animation(anim_data, sprite_map, scale_factor=1):
    """
    Generates the RPG-compatible JSON for an entire animation.
    
    This JSON contains all the information needed to:
    1. Split the spritesheet into individual sprite assets
    2. Position each sprite correctly using the pivot point
    3. The first frame of each direction is the reference frame (offset 0,0)
    
    Args:
        anim_data: Animation data dictionary
        sprite_map: Dictionary mapping sprite_id to PIL Image
        scale_factor: Scale factor (1 or 2)
    
    Returns:
        dict: RPG-compatible JSON data
    """
    tile_size = TILE_SIZE * scale_factor
    canvas_size = tile_size * GRID_SIZE
    
    # Tile anchor is at the bottom center of the middle tile
    tile_anchor = (canvas_size // 2, tile_size * 2)
    
    rpg_json = {
        "name": anim_data.get("name", "unknown"),
        "tile_size": tile_size,
        "grid_size": GRID_SIZE,
        "canvas_size": canvas_size,
        "tile_anchor": list(tile_anchor),
        "durations": anim_data.get("durations", [1]),
        "directions": {}
    }
    
    # Track unique sprites for the sprite_assets section
    sprite_assets = {}
    
    # Pre-calculate anchor offset for each group based on its first frame
    group_anchor_offsets = {}
    for group_id in sorted(anim_data["sprites"].keys(), key=int):
        group_data = anim_data["sprites"][group_id]
        frames_in_group = group_data.get("frames", [])
        if frames_in_group:
            first_frame = frames_in_group[0]
            anchor_offset = calculate_first_frame_anchor_offset(first_frame, sprite_map)
            group_anchor_offsets[group_id] = anchor_offset
        else:
            group_anchor_offsets[group_id] = (0, 0)
    
    for group_id in sorted(anim_data["sprites"].keys(), key=int):
        group_data = anim_data["sprites"][group_id]
        direction_name = group_data.get("name", f"direction_{group_id}")
        anchor_offset = group_anchor_offsets[group_id]
        
        direction_data = {
            "group_id": int(group_id),
            "framewidth": group_data.get("framewidth", 0),
            "frameheight": group_data.get("frameheight", 0),
            "bounding_box_anchor": group_data.get("bounding_box_anchor", [0, 0]),
            "anchor_offset": list(anchor_offset),
            "frames": []
        }
        
        for frame_idx, frame_info in enumerate(group_data.get("frames", [])):
            sprite_id = frame_info.get("id", "0")
            render_offset = frame_info.get("render_offset", [0, 0])
            
            sprite_img = sprite_map.get(sprite_id) if sprite_id != "0" else None
            
            if sprite_img:
                sprite_width, sprite_height = sprite_img.size
                render_x, render_y = render_offset
                
                # Calculate position on canvas (relative to tile anchor)
                canvas_x = tile_anchor[0] + render_x + anchor_offset[0]
                canvas_y = tile_anchor[1] + render_y + anchor_offset[1]
                
                # Relative offset from the first frame (already applied via anchor_offset)
                relative_offset_x = render_x + anchor_offset[0]
                relative_offset_y = render_y + anchor_offset[1]
                
                # Pivot point is bottom center of sprite (relative to sprite top-left)
                pivot_x = sprite_width // 2
                pivot_y = sprite_height
                
                frame_data = {
                    "sprite_id": sprite_id,
                    "sprite_width": sprite_width,
                    "sprite_height": sprite_height,
                    "canvas_position": [int(canvas_x), int(canvas_y)],
                    "pivot": [pivot_x, pivot_y],
                    "relative_offset": [relative_offset_x, relative_offset_y],
                    "original_render_offset": list(render_offset)
                }
                
                # Add to sprite_assets if not already there
                if sprite_id not in sprite_assets:
                    sprite_assets[sprite_id] = {
                        "width": sprite_width,
                        "height": sprite_height,
                        "pivot": [pivot_x, pivot_y],
                        "filename": f"sprite_{sprite_id}.png"
                    }
            else:
                frame_data = {
                    "sprite_id": sprite_id,
                    "sprite_width": 0,
                    "sprite_height": 0,
                    "canvas_position": [0, 0],
                    "pivot": [0, 0],
                    "relative_offset": [0, 0],
                    "original_render_offset": list(render_offset) if render_offset else [0, 0]
                }
            
            direction_data["frames"].append(frame_data)
        
        rpg_json["directions"][direction_name] = direction_data
    
    rpg_json["sprite_assets"] = sprite_assets
    
    return rpg_json
