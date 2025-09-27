# ui_components/preview_generator.py

import os
from PIL import Image, ImageDraw
import math
from ui_components import isometric_renderer, image_utils
from animation_data_handler import calculate_isometric_render_data

class PreviewGenerator:
    def __init__(self, anim_data, group_frames, group_metadata, group_shadow_frames, sprite_folder, anim_folder):
        self.anim_data = anim_data
        self.group_frames = group_frames
        self.group_metadata = group_metadata
        self.group_shadow_frames = group_shadow_frames
        self.sprite_folder = sprite_folder
        self.anim_folder = anim_folder
        self.base_sprite_img = image_utils.load_base_shadow_sprite(self.anim_folder)

    def get_generated_frame_data(self, sprite_ids, mirror_flags, apply_correction):
        result_data = []
        frame_width, frame_height = self.anim_data["frame_width"], self.anim_data["frame_height"]

        for i, num in enumerate(sprite_ids):
            sprite_to_paste = image_utils.load_sprite(self.sprite_folder, num, mirror_flags[i])
            
            if sprite_to_paste:
                all_anchors = self.group_metadata[i]['anchors']
                target = all_anchors.get("green") or all_anchors.get("black")
                anchor_x, anchor_y = target
                
                sprite_w, sprite_h = sprite_to_paste.size
                initial_x = anchor_x - sprite_w // 2
                initial_y = anchor_y - sprite_h // 2
                
                final_x, final_y = initial_x, initial_y
                
                if apply_correction:
                    temp = Image.new('RGBA', (frame_width, frame_height))
                    temp.paste(sprite_to_paste, (initial_x, initial_y), sprite_to_paste)

                    orig_center = image_utils.get_image_bottom_center(self.group_frames[i])
                    temp_center = image_utils.get_image_bottom_center(temp)
                    
                    if orig_center and temp_center:
                        final_x += int(round(orig_center[0] - temp_center[0]))
                        final_y += int(round(orig_center[1] - temp_center[1]))
                
                result_data.append({"image": sprite_to_paste, "pos": (final_x, final_y)})
            else:
                result_data.append({"image": None, "pos": (0, 0)})
        return result_data

    def get_group_bounds(self, corrected_frame_data):
        min_x, min_y, max_x, max_y = float('inf'), float('inf'), float('-inf'), float('-inf')
        has_sprites = any(data["image"] for data in corrected_frame_data)

        if not has_sprites:
            w, h = self.anim_data["frame_width"], self.anim_data["frame_height"]
            return 0, 0, w, h

        for data in corrected_frame_data:
            if data["image"]:
                px, py = data["pos"]
                pw, ph = data["image"].size
                min_x = min(min_x, px)
                min_y = min(min_y, py)
                max_x = max(max_x, px + pw)
                max_y = max(max_y, py + ph)
        
        return int(min_x), int(min_y), int(max_x), int(max_y)

    def generate_corrected_preview(self, corrected_frame_data):
        min_x, min_y, max_x, max_y = self.get_group_bounds(corrected_frame_data)
        fw, fh = math.ceil(max_x - min_x), math.ceil(max_y - min_y)
        
        final_offsets = [[round(d["pos"][0] - min_x), round(d["pos"][1] - min_y)] if d["image"] else [0,0] for d in corrected_frame_data]
        offset_texts = [f"Final Offset: {off}" for off in final_offsets]
        
        canvas_w, canvas_h = fw + 20, fh + 20
        final_frames = []

        for i, data in enumerate(corrected_frame_data):
            frame = Image.new('RGBA', (canvas_w, canvas_h), (211, 211, 211, 255))
            draw = ImageDraw.Draw(frame)
            
            box_x0, box_y0 = (canvas_w - fw) // 2, (canvas_h - fh) // 2
            draw.rectangle([box_x0, box_y0, box_x0 + fw, box_y0 + fh], outline="grey")
            
            if data["image"]:
                paste_pos = (box_x0 + final_offsets[i][0], box_y0 + final_offsets[i][1])
                frame.paste(data["image"], paste_pos, data["image"])
            final_frames.append(frame)

        return {"frames": final_frames, "text_data": offset_texts, "durations": self.anim_data["durations"]}

    def generate_overlay_preview(self, uncorrected_frame_data):
        w, h = self.anim_data["frame_width"], self.anim_data["frame_height"]
        custom_frames = []
        for data in uncorrected_frame_data:
            comp = Image.new('RGBA', (w, h))
            if data["image"]:
                pos = (int(round(data["pos"][0])), int(round(data["pos"][1])))
                comp.paste(data["image"], pos, data["image"])
            custom_frames.append(comp)
        
        canvas_w, canvas_h = w * 2, h * 2
        overlay_frames, offset_texts = [], []

        for i, custom_frame in enumerate(custom_frames):
            comp = Image.new('RGBA', (canvas_w, canvas_h))
            orig_tint = image_utils.tint_image(self.group_frames[i], (255, 0, 0, 128))
            cust_tint = image_utils.tint_image(custom_frame, (0, 0, 255, 128))
            
            paste_pos = (w // 2, h // 2)
            comp.paste(orig_tint, paste_pos, orig_tint)
            comp.paste(cust_tint, paste_pos, cust_tint)
            overlay_frames.append(comp)

            orig_center = image_utils.get_image_bottom_center(self.group_frames[i])
            cust_center = image_utils.get_image_bottom_center(custom_frame)
            
            if orig_center and cust_center:
                offset_texts.append(f"Displacement: ({cust_center[0] - orig_center[0]}, {cust_center[1] - orig_center[1]})")
            else:
                offset_texts.append("Displacement: (N/A)")
        
        return {"frames": overlay_frames, "text_data": offset_texts, "durations": self.anim_data["durations"]}

    def generate_shadow_combined_preview(self, corrected_frame_data):
        if not self.group_shadow_frames or not self.group_metadata or not self.base_sprite_img:
            return {"frames": [], "text_data": [], "durations": self.anim_data["durations"], "static_shadow_offset": None, "render_offsets": []}

        sprite_anchor_offset, render_offsets = calculate_isometric_render_data(
            corrected_frame_data, self.group_frames, self.group_shadow_frames, self.group_metadata
        )

        consts = {'WIDTH': 32, 'HEIGHT': 16, 'WIDTH_HALF': 16, 'HEIGHT_HALF': 8}
        canvas_w, canvas_h = consts['WIDTH'] * 5, consts['HEIGHT'] * 5

        ref_pos_corrected = None
        if corrected_frame_data and corrected_frame_data[0] and corrected_frame_data[0]["image"]:
            ref_pos_corrected = corrected_frame_data[0]["pos"]

        if not ref_pos_corrected:
             return {"frames": [], "text_data": ["World Displacement: (N/A)"] * len(self.group_frames), "durations": self.anim_data["durations"], "static_shadow_offset": sprite_anchor_offset, "render_offsets": render_offsets}

        frames, frame_texts = [], []
        for i, frame_data in enumerate(corrected_frame_data):
            canvas = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
            world_anchor = (canvas_w // 2, canvas_h // 2)
            grid_origin = (world_anchor[0] - consts['WIDTH_HALF'], world_anchor[1] - consts['HEIGHT_HALF'] * 3)
            isometric_renderer.draw_iso_grid(canvas, grid_origin, consts)
            
            total_move_x, total_move_y = 0, 0
            current_pos_corrected = frame_data["pos"]
            if current_pos_corrected and frame_data["image"]:
                total_move_x = current_pos_corrected[0] - ref_pos_corrected[0]
                total_move_y = current_pos_corrected[1] - ref_pos_corrected[1]

            shadow_center = world_anchor
            paste_pos = (shadow_center[0] - self.base_sprite_img.width // 2, 
                         shadow_center[1] - self.base_sprite_img.height // 2)
            canvas.paste(self.base_sprite_img, paste_pos, self.base_sprite_img)
            
            world_disp_text = f"World Displacement: ({round(total_move_x)}, {round(total_move_y)})"
            
            current_render_offset = render_offsets[i]
            if current_render_offset:
                render_offset_text = f"Render Offset: ({current_render_offset[0]}, {current_render_offset[1]})"
                
                char_sprite_to_render = frame_data["image"]
                if char_sprite_to_render:
                    paste_x = world_anchor[0] + current_render_offset[0]
                    paste_y = world_anchor[1] + current_render_offset[1]
                    canvas.paste(char_sprite_to_render, (paste_x, paste_y), char_sprite_to_render)

                    # To draw with opacity, create a separate overlay, draw on it, and then composite it.
                    overlay = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
                    draw_overlay = ImageDraw.Draw(overlay)

                    # Draw the semi-transparent yellow bounding box on the overlay
                    w, h = char_sprite_to_render.size
                    box_coords = [paste_x, paste_y, paste_x + w - 1, paste_y + h - 1]
                    yellow_with_alpha = (255, 255, 0, 128)  # Yellow with ~50% opacity
                    draw_overlay.rectangle(box_coords, outline=yellow_with_alpha, width=1)
                    
                    # Composite the overlay onto the main canvas
                    canvas = Image.alpha_composite(canvas, overlay)
            else:
                render_offset_text = "Render Offset: (N/A)"
            
            # Re-initialize the draw object on the new composited canvas to add crosshairs
            draw = ImageDraw.Draw(canvas)

            if sprite_anchor_offset:
                crosshair_x = world_anchor[0] + sprite_anchor_offset[0] + total_move_x
                crosshair_y = world_anchor[1] + sprite_anchor_offset[1] + total_move_y
                s = 3
                draw.line((crosshair_x-s, crosshair_y, crosshair_x+s, crosshair_y), fill="green", width=1)
                draw.line((crosshair_x, crosshair_y-s, crosshair_x, crosshair_y+s), fill="green", width=1)
            
            if current_render_offset and frame_data["image"]:
                 paste_x = world_anchor[0] + current_render_offset[0]
                 paste_y = world_anchor[1] + current_render_offset[1]
                 s = 3
                 draw.line((paste_x-s, paste_y, paste_x+s, paste_y), fill="purple", width=1)
                 draw.line((paste_x, paste_y-s, paste_x, paste_y+s), fill="purple", width=1)

            frame_texts.append(f"{world_disp_text}\n{render_offset_text}")

            s = 3
            draw.line((world_anchor[0]-s, world_anchor[1], world_anchor[0]+s, world_anchor[1]), fill="red")
            draw.line((world_anchor[0], world_anchor[1]-s, world_anchor[0], world_anchor[1]+s), fill="red")
            
            canvas = canvas.resize((canvas.width * 2, canvas.height * 2), Image.NEAREST)
            frames.append(canvas)
        
        return {"frames": frames, "text_data": frame_texts, "thumbnail_size": (400, 400), "durations": self.anim_data["durations"], "static_shadow_offset": sprite_anchor_offset, "render_offsets": render_offsets}