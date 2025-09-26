# ui_components/preview_generator.py

import os
from PIL import Image, ImageDraw, ImageOps
import math
from ui_components import isometric_renderer

class PreviewGenerator:
    def __init__(self, anim_data, group_frames, group_metadata, group_shadow_frames, sprite_folder, anim_folder):
        self.anim_data = anim_data
        self.group_frames = group_frames
        self.group_metadata = group_metadata
        self.group_shadow_frames = group_shadow_frames
        self.sprite_folder = sprite_folder
        self.anim_folder = anim_folder
        self.base_sprite_img = self._load_base_sprite()

    def _load_base_sprite(self):
        try:
            path = os.path.join(self.anim_folder, "sprite_base.png")
            if os.path.exists(path):
                return Image.open(path).convert('RGBA')
        except Exception as e:
            print(f"Could not load sprite_base.png: {e}")
        return None

    def get_generated_frame_data(self, sprite_ids, mirror_flags, apply_correction):
        result_data = []
        frame_width, frame_height = self.anim_data["frame_width"], self.anim_data["frame_height"]

        for i, num in enumerate(sprite_ids):
            sprite_to_paste = self._load_sprite(num, mirror_flags[i])
            
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

                    orig_center = self._get_image_bottom_center(self.group_frames[i])
                    temp_center = self._get_image_bottom_center(temp)
                    
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
            orig_tint = self._tint_image(self.group_frames[i], (255, 0, 0, 128))
            cust_tint = self._tint_image(custom_frame, (0, 0, 255, 128))
            
            paste_pos = (w // 2, h // 2)
            comp.paste(orig_tint, paste_pos, orig_tint)
            comp.paste(cust_tint, paste_pos, cust_tint)
            overlay_frames.append(comp)

            orig_center = self._get_image_bottom_center(self.group_frames[i])
            cust_center = self._get_image_bottom_center(custom_frame)
            
            if orig_center and cust_center:
                offset_texts.append(f"Displacement: ({cust_center[0] - orig_center[0]}, {cust_center[1] - orig_center[1]})")
            else:
                offset_texts.append("Displacement: (N/A)")
        
        return {"frames": overlay_frames, "text_data": offset_texts, "durations": self.anim_data["durations"]}

    def generate_shadow_combined_preview(self, corrected_frame_data):
        if not self.group_shadow_frames or not self.group_metadata or not self.base_sprite_img:
            return {"frames": [], "text_data": [], "durations": self.anim_data["durations"], "static_shadow_offset": None, "render_offsets": []}

        # Calculate the static offset between the character's anchor and shadow's anchor on the first frame
        sprite_anchor_offset = None
        shadow_anchor_0 = self._find_white_pixel_anchor(self.group_shadow_frames[0])
        offset_anchor_0 = self.group_metadata[0]['anchors'].get('green')

        if shadow_anchor_0 and offset_anchor_0:
            sprite_anchor_offset = (offset_anchor_0[0] - shadow_anchor_0[0], offset_anchor_0[1] - shadow_anchor_0[1])

        consts = {'WIDTH': 32, 'HEIGHT': 16, 'WIDTH_HALF': 16, 'HEIGHT_HALF': 8}
        canvas_w, canvas_h = consts['WIDTH'] * 5, consts['HEIGHT'] * 5

        # Get the corrected position from the first frame as the reference "zero" point
        ref_pos_corrected = None
        if corrected_frame_data and corrected_frame_data[0] and corrected_frame_data[0]["image"]:
            ref_pos_corrected = corrected_frame_data[0]["pos"]

        if not ref_pos_corrected:
            # Fallback if no sprites are defined, but we still want to show the shadow
             return {"frames": [], "text_data": ["World Displacement: (N/A)"] * len(self.group_frames), "durations": self.anim_data["durations"], "static_shadow_offset": sprite_anchor_offset, "render_offsets": [None] * len(self.group_frames)}

        frames, frame_texts, render_offsets = [], [], []
        for i, frame_data in enumerate(corrected_frame_data):
            canvas = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
            world_anchor = (canvas_w // 2, canvas_h // 2)
            grid_origin = (world_anchor[0] - consts['WIDTH_HALF'], world_anchor[1] - consts['HEIGHT_HALF'] * 3)
            isometric_renderer.draw_iso_grid(canvas, grid_origin, consts)
            draw = ImageDraw.Draw(canvas)

            # Calculate total unified movement based on the corrected final position data
            total_move_x, total_move_y = 0, 0
            current_pos_corrected = frame_data["pos"]
            if current_pos_corrected and frame_data["image"]:
                total_move_x = current_pos_corrected[0] - ref_pos_corrected[0]
                total_move_y = current_pos_corrected[1] - ref_pos_corrected[1]

            # The shadow is static at the world anchor
            shadow_center = world_anchor
            paste_pos = (shadow_center[0] - self.base_sprite_img.width // 2, 
                         shadow_center[1] - self.base_sprite_img.height // 2)
            canvas.paste(self.base_sprite_img, paste_pos, self.base_sprite_img)
            
            world_disp_text = f"World Displacement: ({round(total_move_x)}, {round(total_move_y)})"
            render_offset_text = "Render Offset: (N/A)"
            current_render_offset = None

            if sprite_anchor_offset:
                # The green crosshair position is the world anchor + static offset + world displacement
                crosshair_x = world_anchor[0] + sprite_anchor_offset[0] + total_move_x
                crosshair_y = world_anchor[1] + sprite_anchor_offset[1] + total_move_y

                char_sprite = self.group_frames[i]
                current_green_pos = self.group_metadata[i]['anchors'].get('green')
                
                bbox = char_sprite.getbbox()
                if bbox and current_green_pos:
                    # Calculate paste position for the full frame
                    paste_x = crosshair_x - current_green_pos[0]
                    paste_y = crosshair_y - current_green_pos[1]
                    
                    # Define the top-left corner of the actual asset (bounding box)
                    render_anchor_x = paste_x + bbox[0]
                    render_anchor_y = paste_y + bbox[1]

                    # Draw the bounding box itself in yellow BEFORE pasting the sprite
                    box_x1 = paste_x + bbox[2] - 1
                    box_y1 = paste_y + bbox[3] - 1
                    draw.rectangle([render_anchor_x, render_anchor_y, box_x1, box_y1], outline="yellow", width=1)

                    # Paste the character sprite on top of the bounding box
                    canvas.paste(char_sprite, (paste_x, paste_y), char_sprite)

                    s = 3
                    # Draw the green crosshair (character anchor)
                    draw.line((crosshair_x-s, crosshair_y, crosshair_x+s, crosshair_y), fill="green", width=1)
                    draw.line((crosshair_x, crosshair_y-s, crosshair_x, crosshair_y+s), fill="green", width=1)
                    
                    # Draw the new lilac render offset cross at the top-left of the bounding box
                    draw.line((render_anchor_x-s, render_anchor_y, render_anchor_x+s, render_anchor_y), fill="purple", width=1)
                    draw.line((render_anchor_x, render_anchor_y-s, render_anchor_x, render_anchor_y+s), fill="purple", width=1)
                    
                    # Calculate and format the render offset text from the correct point
                    render_offset_x = render_anchor_x - world_anchor[0]
                    render_offset_y = render_anchor_y - world_anchor[1]
                    current_render_offset = (render_offset_x, render_offset_y)
                    render_offset_text = f"Render Offset: ({render_offset_x}, {render_offset_y})"

            frame_texts.append(f"{world_disp_text}\n{render_offset_text}")
            render_offsets.append(current_render_offset)

            # Draw the static world anchor (red cross)
            s = 3
            draw.line((world_anchor[0]-s, world_anchor[1], world_anchor[0]+s, world_anchor[1]), fill="red")
            draw.line((world_anchor[0], world_anchor[1]-s, world_anchor[0], world_anchor[1]+s), fill="red")
            
            canvas = canvas.resize((canvas.width * 2, canvas.height * 2), Image.NEAREST)
            frames.append(canvas)
        
        return {"frames": frames, "text_data": frame_texts, "thumbnail_size": (400, 400), "durations": self.anim_data["durations"], "static_shadow_offset": sprite_anchor_offset, "render_offsets": render_offsets}

    # Helper Methods
    def _load_sprite(self, sprite_id, is_mirrored):
        if not sprite_id or sprite_id <= 0: return None
        try:
            path = os.path.join(self.sprite_folder, f"sprite_{sprite_id}.png")
            sprite = Image.open(path).convert('RGBA')
            return ImageOps.mirror(sprite) if is_mirrored else sprite
        except FileNotFoundError:
            return None

    def _get_image_bottom_center(self, image):
        bbox = image.getbbox()
        return ((bbox[0] + bbox[2]) // 2, bbox[3]) if bbox else None

    def _get_image_center(self, image):
        bbox = image.getbbox()
        return ((bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2) if bbox else None
    
    def _find_white_pixel_anchor(self, image):
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
        
        width, height = image.size
        pixels = image.load()
        white_pixel_color = (255, 255, 255, 255)
        
        for y in range(height):
            for x in range(width):
                if pixels[x, y] == white_pixel_color:
                    return (x, y)
        
        return self._get_image_center(image)

    def _tint_image(self, image, color):
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
        
        tint_layer = Image.new('RGBA', image.size, color)
        
        return Image.composite(tint_layer, image, image)