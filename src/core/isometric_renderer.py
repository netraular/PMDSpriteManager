# ui_components/isometric_renderer.py

import os
from PIL import Image, ImageDraw

def grid_to_screen(gx, gy, origin, w_half, h_half):
    """Converts grid coordinates to screen coordinates for an isometric view."""
    return (int(origin[0] + (gx - gy) * w_half), int(origin[1] + (gx + gy) * h_half))

def draw_iso_grid(image, origin, consts):
    """Draws a 3x3 isometric grid on the given image."""
    draw = ImageDraw.Draw(image)
    for y in range(3):
        for x in range(3):
            pos = grid_to_screen(x, y, origin, consts['WIDTH_HALF'], consts['HEIGHT_HALF'])
            points = [
                (pos[0] + consts['WIDTH_HALF'], pos[1]),
                (pos[0] + consts['WIDTH'], pos[1] + consts['HEIGHT_HALF']),
                (pos[0] + consts['WIDTH_HALF'], pos[1] + consts['HEIGHT']),
                (pos[0], pos[1] + consts['HEIGHT_HALF'])
            ]
            draw.polygon(points, fill=(200, 200, 200), outline=(150, 150, 150))

def load_sprites_from_json(anim_data, sprite_folder):
    """Loads all unique sprites referenced in an animation's JSON data into a map."""
    loaded_sprites = {}
    for group in anim_data.get('sprites', {}).values():
        for frame in group.get('frames', []):
            sprite_id = frame.get('id', '0')
            if sprite_id != '0' and sprite_id not in loaded_sprites:
                sprite_path = os.path.join(sprite_folder, f"sprite_{sprite_id}.png")
                try:
                    loaded_sprites[sprite_id] = Image.open(sprite_path).convert('RGBA')
                except FileNotFoundError:
                    print(f"Warning: Sprite not found at {sprite_path}, creating placeholder.")
                    placeholder = Image.new('RGBA', (40, 40), (0, 0, 0, 0))
                    draw = ImageDraw.Draw(placeholder)
                    draw.text((5, 10), f"?{sprite_id}?", fill="red")
                    loaded_sprites[sprite_id] = placeholder
    return loaded_sprites

def generate_isometric_preview_data(anim_data, sprite_map, shadow_sprite, is_2x):
    """
    Generates all data needed by AnimationPlayer to display a final isometric preview.
    """
    if is_2x:
        consts = {'WIDTH': 64, 'HEIGHT': 32, 'WIDTH_HALF': 32, 'HEIGHT_HALF': 16}
    else:
        consts = {'WIDTH': 32, 'HEIGHT': 16, 'WIDTH_HALF': 16, 'HEIGHT_HALF': 8}

    canvas_w, canvas_h = consts['WIDTH'] * 5, consts['HEIGHT'] * 5

    all_frames_data = []
    all_group_ids = []
    for group_id in sorted(anim_data["sprites"].keys(), key=int):
        group_data = anim_data["sprites"][group_id]
        frames_in_group = group_data.get("frames", [])
        all_frames_data.extend(frames_in_group)
        all_group_ids.extend([group_id] * len(frames_in_group))

    if not all_frames_data:
        return {"frames": [], "text_data": [], "durations": []}
    
    total_frames = len(all_frames_data)
    base_durations = anim_data.get("durations", [1])
    durations = (base_durations * (total_frames // len(base_durations) + 1))[:total_frames]
    
    final_frames = []
    text_data = []

    for i, frame_info in enumerate(all_frames_data):
        group_id = all_group_ids[i]
        group_data = anim_data["sprites"][group_id]

        canvas = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
        world_anchor = (canvas_w // 2, canvas_h // 2)
        grid_origin = (world_anchor[0] - consts['WIDTH_HALF'], world_anchor[1] - consts['HEIGHT_HALF'] * 3)
        draw_iso_grid(canvas, grid_origin, consts)
        
        overlay = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        draw_overlay = ImageDraw.Draw(overlay)

        if shadow_sprite:
            shadow_pos = (world_anchor[0] - shadow_sprite.width // 2, world_anchor[1] - shadow_sprite.height // 2)
            canvas.paste(shadow_sprite, shadow_pos, shadow_sprite)

        frame_w = group_data.get("framewidth")
        frame_h = group_data.get("frameheight")
        bbox_anchor = group_data.get("bounding_box_anchor")
        
        if frame_w is not None and frame_h is not None and bbox_anchor:
            min_rx, min_ry = bbox_anchor
            box_x0 = world_anchor[0] + min_rx
            box_y0 = world_anchor[1] + min_ry
            box_x1 = box_x0 + frame_w
            box_y1 = box_y0 + frame_h
            yellow_with_alpha = (255, 255, 0, 128)
            draw_overlay.rectangle([box_x0, box_y0, box_x1-1, box_y1-1], outline=yellow_with_alpha, width=1)

        render_offset = frame_info.get("render_offset")
        sprite_id = frame_info.get("id", "0")
        sprite_img = sprite_map.get(sprite_id)

        current_offset_text = "Render Offset: (N/A)"

        if sprite_img and render_offset and len(render_offset) == 2:
            render_x, render_y = render_offset
            paste_pos = (world_anchor[0] + render_x, world_anchor[1] + render_y)
            canvas.paste(sprite_img, paste_pos, sprite_img)

            s = 3
            draw_overlay.line((paste_pos[0]-s, paste_pos[1], paste_pos[0]+s, paste_pos[1]), fill="purple", width=1)
            draw_overlay.line((paste_pos[0], paste_pos[1]-s, paste_pos[0], paste_pos[1]+s), fill="purple", width=1)
            current_offset_text = f"Render Offset: ({render_x}, {render_y})"

        canvas = Image.alpha_composite(canvas, overlay)
        draw = ImageDraw.Draw(canvas)

        frame_duration = durations[i] if i < len(durations) else "N/A"
        fw_text = f"Frame W/H: ({frame_w}, {frame_h})" if frame_w is not None and frame_h is not None else "Frame W/H: (N/A)"
        final_text_for_frame = f"{current_offset_text}\n{fw_text}\nDuration: {frame_duration}"

        s = 3
        draw.line((world_anchor[0]-s, world_anchor[1], world_anchor[0]+s, world_anchor[1]), fill="red", width=1)
        draw.line((world_anchor[0], world_anchor[1]-s, world_anchor[0], world_anchor[1]+s), fill="red", width=1)
        
        final_canvas = canvas.resize((canvas.width * 2, canvas.height * 2), Image.NEAREST)
        final_frames.append(final_canvas)
        text_data.append(final_text_for_frame)
    
    return {
        "frames": final_frames, 
        "text_data": text_data, 
        "durations": durations,
        "thumbnail_size": (400, 400)
    }