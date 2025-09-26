# ui_components/preview_generator.py

import os
from PIL import Image, ImageDraw, ImageOps
import math

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
        offset_texts = [f"Offset: {off}" for off in final_offsets]
        
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
                offset_texts.append(f"Offset: ({cust_center[0] - orig_center[0]}, {cust_center[1] - orig_center[1]})")
            else:
                offset_texts.append("Offset: (N/A)")
        
        return {"frames": overlay_frames, "text_data": offset_texts, "durations": self.anim_data["durations"]}

    def generate_shadow_combined_preview(self):
        if not self.group_shadow_frames or not self.group_metadata or not self.base_sprite_img:
            return {"frames": [], "text_data": [], "durations": self.anim_data["durations"]}

        # Calculate the static offset between the character's center and shadow's center on the first frame
        shadow_offset = None
        shadow_anchor_0 = self._find_white_pixel_anchor(self.group_shadow_frames[0])
        offset_anchor_0 = self.group_metadata[0]['anchors'].get('green')

        if shadow_anchor_0 and offset_anchor_0:
            shadow_offset = (offset_anchor_0[0] - shadow_anchor_0[0], offset_anchor_0[1] - shadow_anchor_0[1])
            offset_text = f"Shadow Offset: {shadow_offset}"
        else:
            offset_text = "Shadow Offset: (N/A)"

        consts = {'WIDTH': 32, 'HEIGHT': 16, 'WIDTH_HALF': 16, 'HEIGHT_HALF': 8}
        canvas_w, canvas_h = consts['WIDTH'] * 5, consts['HEIGHT'] * 5
        
        # Get all anchor positions for all frames
        shadow_positions = [self._find_white_pixel_anchor(f) for f in self.group_shadow_frames]
        green_anchor_positions = [md['anchors'].get('green') for md in self.group_metadata]
        
        ref_shadow_pos = shadow_positions[0] if shadow_positions and shadow_positions[0] else None
        ref_green_pos = green_anchor_positions[0] if green_anchor_positions and green_anchor_positions[0] else None

        if not ref_shadow_pos:
            return {"frames": [], "text_data": [offset_text] * len(self.group_shadow_frames), "durations": self.anim_data["durations"]}

        frames = []
        for i in range(len(self.group_shadow_frames)):
            canvas = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
            
            world_anchor = (canvas_w // 2, canvas_h // 2)
            grid_origin = (world_anchor[0] - consts['WIDTH_HALF'], world_anchor[1] - consts['HEIGHT_HALF'] * 3)
            self._draw_iso_grid(canvas, grid_origin, consts)
            
            draw = ImageDraw.Draw(canvas)

            # Calculate shadow movement relative to its first frame
            shadow_move_x, shadow_move_y = 0, 0
            current_shadow_pos = shadow_positions[i]
            if current_shadow_pos and ref_shadow_pos:
                shadow_move_x = current_shadow_pos[0] - ref_shadow_pos[0]
                shadow_move_y = current_shadow_pos[1] - ref_shadow_pos[1]
            
            shadow_center = (world_anchor[0] + shadow_move_x, world_anchor[1] + shadow_move_y)
            
            # Paste the shadow sprite based on its movement
            paste_pos = (shadow_center[0] - self.base_sprite_img.width // 2, 
                         shadow_center[1] - self.base_sprite_img.height // 2)
            canvas.paste(self.base_sprite_img, paste_pos, self.base_sprite_img)

            # Calculate character anchor movement relative to its first frame
            char_move_x, char_move_y = 0, 0
            current_green_pos = green_anchor_positions[i]
            if current_green_pos and ref_green_pos:
                char_move_x = current_green_pos[0] - ref_green_pos[0]
                char_move_y = current_green_pos[1] - ref_green_pos[1]

            if shadow_offset and current_green_pos:
                # Calculate where the character's anchor point should be on the canvas
                crosshair_x = shadow_center[0] + shadow_offset[0] + char_move_x
                crosshair_y = shadow_center[1] + shadow_offset[1] + char_move_y

                # Get the character sprite for this frame
                char_sprite = self.group_frames[i]
                if char_sprite and char_sprite.getbbox():
                    # Calculate the top-left position to paste the character frame
                    # so its anchor aligns with the crosshair position.
                    paste_x = crosshair_x - current_green_pos[0]
                    paste_y = crosshair_y - current_green_pos[1]
                    
                    # Paste the character
                    canvas.paste(char_sprite, (paste_x, paste_y), char_sprite)

                # Draw the green crosshair on top
                s = 3
                draw.line((crosshair_x-s, crosshair_y, crosshair_x+s, crosshair_y), fill="green", width=1)
                draw.line((crosshair_x, crosshair_y-s, crosshair_x, crosshair_y+s), fill="green", width=1)

            # Draw the static world anchor
            s = 3
            draw.line((world_anchor[0]-s, world_anchor[1], world_anchor[0]+s, world_anchor[1]), fill="red")
            draw.line((world_anchor[0], world_anchor[1]-s, world_anchor[0], world_anchor[1]+s), fill="red")
            
            canvas = canvas.resize((canvas.width * 2, canvas.height * 2), Image.NEAREST)
            frames.append(canvas)
        
        final_texts = [offset_text] * len(frames)
        return {"frames": frames, "text_data": final_texts, "thumbnail_size": (400, 400), "durations": self.anim_data["durations"]}

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


    def _grid_to_screen(self, gx, gy, origin, w_half, h_half):
        return (int(origin[0] + (gx - gy) * w_half), int(origin[1] + (gx + gy) * h_half))

    def _draw_iso_grid(self, image, origin, consts):
        draw = ImageDraw.Draw(image)
        for y in range(3):
            for x in range(3):
                pos = self._grid_to_screen(x, y, origin, consts['WIDTH_HALF'], consts['HEIGHT_HALF'])
                points = [
                    (pos[0] + consts['WIDTH_HALF'], pos[1]),
                    (pos[0] + consts['WIDTH'], pos[1] + consts['HEIGHT_HALF']),
                    (pos[0] + consts['WIDTH_HALF'], pos[1] + consts['HEIGHT']),
                    (pos[0], pos[1] + consts['HEIGHT_HALF'])
                ]
                draw.polygon(points, fill=(200, 200, 200), outline=(150, 150, 150))