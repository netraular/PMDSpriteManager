# animation_group_ui.py

import os
from tkinter import Frame, Label, Button, Entry, BooleanVar, Checkbutton, StringVar, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageOps
import math

class AnimationGroupUI:
    def __init__(self, parent, viewer, group_idx, anim_data, group_frames, group_offsets_frames, group_shadow_frames, group_metadata, sprite_folder, json_group_data, ai_callback):
        self.parent = parent
        self.viewer = viewer
        self.group_idx = group_idx
        self.anim_data = anim_data
        self.group_frames = group_frames
        self.group_offsets_frames = group_offsets_frames
        self.group_shadow_frames = group_shadow_frames
        self.group_metadata = group_metadata
        self.sprite_folder = sprite_folder
        self.json_group_data = json_group_data or {}
        self.ai_callback = ai_callback

        self.after_ids = []
        self.result_after_ids = []
        self.overlay_after_ids = []
        self.iso_after_ids = []
        
        self.string_vars = []
        self.mirror_vars = []
        self.custom_sprite_labels = []

        self._setup_ui()
        self._populate_initial_data()
        self.refresh_all_custom_previews()
        self.refresh_all_previews()

    def _setup_ui(self):
        row_container = Frame(self.parent); row_container.pack(fill='x', padx=5, pady=5)
        
        group_frame = Frame(row_container, bd=2, relief="groove"); group_frame.pack(side='left', fill='both', expand=True, padx=(0, 5))
        header_frame = Frame(group_frame); header_frame.pack(fill='x', pady=5, padx=5)
        header_left = Frame(header_frame); header_left.pack(side='left', fill='x', expand=True)
        
        Label(header_left, text=f"Group {self.group_idx + 1}", font=('Arial', 12, 'bold')).pack(side='left')
        self.name_entry = Entry(header_left, width=20); self.name_entry.pack(side='left', padx=10)
        
        self.ai_button = Button(header_left, text="AI Identify Sprites", command=lambda: self.ai_callback(self)); self.ai_button.pack(side='left', padx=10)
        
        content_frame = Frame(group_frame); content_frame.pack(fill="both", expand=True)
        animation_previews_container = Frame(content_frame); animation_previews_container.pack(side="left", padx=10)
        anim_panel = Frame(animation_previews_container); anim_panel.pack(side="left", padx=5)
        anim_panel_copy = Frame(animation_previews_container); anim_panel_copy.pack(side="left", padx=5)
        shadow_panel = Frame(animation_previews_container); shadow_panel.pack(side="left", padx=5)
        frames_panel = Frame(content_frame); frames_panel.pack(side="left", fill="x", expand=True)
        
        # --- Previews Container ---
        previews_container = Frame(row_container)
        previews_container.pack(side='left', fill='y')
        
        Button(previews_container, text="Refresh Previews", command=self.refresh_all_previews).pack(pady=2, padx=2, fill='x')

        # --- Uncorrected Overlay Preview (Left) ---
        overlay_preview_frame = Frame(previews_container, bd=1, relief="sunken")
        overlay_preview_frame.pack(side='left', fill='y', padx=(5, 0))
        Label(overlay_preview_frame, text="Uncorrected Overlay", font=('Arial', 8, 'bold')).pack(pady=(5,0))
        self.overlay_label = Label(overlay_preview_frame); self.overlay_label.pack(pady=5, padx=5, expand=True)
        self.offset_label = Label(overlay_preview_frame, text="Offset: (N/A)", font=('Arial', 8)); self.offset_label.pack(pady=(0, 5))

        # --- Corrected Result Preview (Middle) ---
        result_preview_frame = Frame(previews_container, bd=1, relief="sunken")
        result_preview_frame.pack(side='left', fill='y', padx=(5, 0))
        Label(result_preview_frame, text="Corrected Preview", font=('Arial', 8, 'bold')).pack(pady=(5,0))
        self.result_label = Label(result_preview_frame); self.result_label.pack(pady=5, padx=5, expand=True)
        self.corrected_offset_label = Label(result_preview_frame, text="Offset: (N/A)", font=('Arial', 8))
        self.corrected_offset_label.pack(pady=(0, 5))
        
        # --- Isometric Preview (Right) ---
        iso_preview_frame = Frame(previews_container, bd=1, relief="sunken")
        iso_preview_frame.pack(side='left', fill='y', padx=(5, 0))
        Label(iso_preview_frame, text="Isometric Preview", font=('Arial', 8, 'bold')).pack(pady=(5,0))
        self.iso_label = Label(iso_preview_frame)
        self.iso_label.pack(pady=5, padx=5, expand=True)
        
        durations = self.anim_data["durations"] * (len(self.group_frames) // len(self.anim_data["durations"]) + 1)
        
        anim_label = Label(anim_panel); anim_label.pack()
        self._start_animation_loop(anim_label, [f.copy() for f in self.group_frames], durations[:len(self.group_frames)], self.after_ids)
        
        if self.group_offsets_frames:
            anim_label_copy = Label(anim_panel_copy, bg="lightgrey"); anim_label_copy.pack()
            self._start_animation_loop(anim_label_copy, [f.copy() for f in self.group_offsets_frames], durations[:len(self.group_offsets_frames)], self.after_ids)

        if self.group_shadow_frames:
            shadow_label = Label(shadow_panel, bg="lightgrey"); shadow_label.pack()
            self._start_animation_loop(shadow_label, [f.copy() for f in self.group_shadow_frames], durations[:len(self.group_shadow_frames)], self.after_ids)

        for idx, frame in enumerate(self.group_frames):
            frame_container = Frame(frames_panel); frame_container.grid(row=0, column=idx, padx=2, pady=2)
            
            display_frame = self._draw_anchors_on_frame(frame.copy(), idx)
            display_frame.thumbnail((80, 80))
            img = ImageTk.PhotoImage(display_frame)
            lbl = Label(frame_container, image=img, relief="sunken", bd=1); lbl.image = img; lbl.pack()
            
            custom_sprite_lbl = Label(frame_container, relief="sunken", bd=1); custom_sprite_lbl.pack()
            self.custom_sprite_labels.append(custom_sprite_lbl)

            input_frame = Frame(frame_container); input_frame.pack()
            sv = StringVar(); entry = Entry(input_frame, width=5, textvariable=sv); entry.insert(0, "0"); entry.pack(side='left')
            mirror_var = BooleanVar(); cb = Checkbutton(input_frame, variable=mirror_var); cb.pack(side='left')

            self.string_vars.append(sv)
            self.mirror_vars.append(mirror_var)
            
            callback = lambda *args, f_idx=idx: self.update_custom_sprite_preview(f_idx)
            sv.trace_add("write", callback)
            mirror_var.trace_add("write", callback)

            Label(frame_container, text=f"Dur: {durations[idx]}", font=('Arial', 7)).pack()

    def _populate_initial_data(self):
        default_name = self._get_default_group_name()
        self.name_entry.insert(0, self.json_group_data.get("name", default_name))
        
        sprite_values = self.json_group_data.get("values", [])
        for idx, sv in enumerate(self.string_vars):
            if idx < len(sprite_values):
                frame_val = sprite_values[idx]
                sprite_id = frame_val if isinstance(frame_val, int) else frame_val.get("id", 0)
                per_sprite_mirror = False if isinstance(frame_val, int) else frame_val.get("mirrored", False)
                sv.set(str(sprite_id))
                self.mirror_vars[idx].set(per_sprite_mirror)

    def _draw_anchors_on_frame(self, frame, frame_idx):
        if frame_idx < len(self.group_metadata):
            metadata = self.group_metadata[frame_idx]
            all_anchors = metadata.get('anchors', {})
            draw = ImageDraw.Draw(frame)
            cross_size = 2
            for color_name, coords in all_anchors.items():
                if coords:
                    x, y = coords
                    draw.line((x - cross_size, y, x + cross_size, y), fill=color_name, width=1)
                    draw.line((x, y - cross_size, x, y + cross_size), fill=color_name, width=1)
        return frame

    def refresh_all_custom_previews(self):
        for i in range(len(self.string_vars)):
            self.update_custom_sprite_preview(i)

    def update_custom_sprite_preview(self, frame_idx):
        sv = self.string_vars[frame_idx]
        mirror_var = self.mirror_vars[frame_idx]
        label_to_update = self.custom_sprite_labels[frame_idx]
        
        frame_width, frame_height = self.anim_data["frame_width"], self.anim_data["frame_height"]
        composite_frame = Image.new('RGBA', (frame_width, frame_height), (0, 0, 0, 0))
        
        sprite_num_str = sv.get()
        sprite_img = None

        try:
            if sprite_num_str.isdigit() and int(sprite_num_str) > 0:
                sprite_path = os.path.join(self.sprite_folder, f"sprite_{int(sprite_num_str)}.png")
                try:
                    sprite_img = Image.open(sprite_path).convert('RGBA')
                except FileNotFoundError:
                    draw_err = ImageDraw.Draw(composite_frame)
                    draw_err.text((frame_width / 2, frame_height / 2), f"?{sprite_num_str}?", fill="red", anchor="mm")
            
            if frame_idx < len(self.group_metadata):
                metadata = self.group_metadata[frame_idx]
                all_anchors = metadata.get('anchors', {})
                green_anchor = all_anchors.get("green")
                black_anchor = all_anchors.get("black")
                sprite_center_target = green_anchor or black_anchor
                
                if sprite_img and sprite_center_target:
                    if mirror_var.get():
                        sprite_img = ImageOps.mirror(sprite_img)
                    sprite_w, sprite_h = sprite_img.size
                    paste_x = sprite_center_target[0] - sprite_w // 2
                    paste_y = sprite_center_target[1] - sprite_h // 2
                    composite_frame.paste(sprite_img, (paste_x, paste_y), sprite_img)
                
                composite_frame = self._draw_anchors_on_frame(composite_frame, frame_idx)
            
            elif sprite_img:
                sprite_w, sprite_h = sprite_img.size
                paste_x = (frame_width - sprite_w) // 2
                paste_y = (frame_height - sprite_h) // 2
                composite_frame.paste(sprite_img, (paste_x, paste_y), sprite_img)

        finally:
            composite_frame.thumbnail((80, 80))
            img_tk = ImageTk.PhotoImage(composite_frame)
            label_to_update.config(image=img_tk)
            label_to_update.image = img_tk

    def _get_image_bottom_center(self, image):
        """Calculates the bottom-center of the visible pixels in an image."""
        bbox = image.getbbox()
        if not bbox:
            return None
        center_x = (bbox[0] + bbox[2]) / 2
        bottom_y = bbox[3]
        return (center_x, bottom_y)

    def _get_generated_frame_data(self, apply_correction):
        sprite_numbers = [int(sv.get()) if sv.get().isdigit() else 0 for sv in self.string_vars]
        result_data = []
        frame_width, frame_height = self.anim_data["frame_width"], self.anim_data["frame_height"]

        for i, num in enumerate(sprite_numbers):
            sprite_to_paste = None
            if num > 0:
                sprite_path = os.path.join(self.sprite_folder, f"sprite_{num}.png")
                try:
                    sprite_to_paste = Image.open(sprite_path).convert('RGBA')
                except FileNotFoundError:
                    pass
            
            if sprite_to_paste:
                if self.mirror_vars[i].get():
                    sprite_to_paste = ImageOps.mirror(sprite_to_paste)

                all_anchors = self.group_metadata[i]['anchors']
                sprite_center_target = all_anchors.get("green") or all_anchors.get("black")
                anchor_x, anchor_y = sprite_center_target
                
                sprite_w, sprite_h = sprite_to_paste.size
                initial_paste_x = anchor_x - sprite_w // 2
                initial_paste_y = anchor_y - sprite_h // 2
                
                final_paste_x, final_paste_y = initial_paste_x, initial_paste_y
                
                if apply_correction:
                    original_frame = self.group_frames[i]
                    temp_frame = Image.new('RGBA', (frame_width, frame_height), (0, 0, 0, 0))
                    temp_frame.paste(sprite_to_paste, (initial_paste_x, initial_paste_y), sprite_to_paste)

                    center_orig = self._get_image_bottom_center(original_frame)
                    center_temp = self._get_image_bottom_center(temp_frame)
                    
                    correction_x, correction_y = 0, 0
                    if center_orig and center_temp:
                        correction_x = center_orig[0] - center_temp[0]
                        correction_y = center_orig[1] - center_temp[1]

                    final_paste_x += int(round(correction_x))
                    final_paste_y += int(round(correction_y))
                
                result_data.append({"image": sprite_to_paste, "pos": (final_paste_x, final_paste_y)})
            else:
                result_data.append({"image": None, "pos": (0, 0)})
        return result_data

    def refresh_all_previews(self):
        self.load_corrected_result_animation()
        self.load_uncorrected_overlay_animation()
        self.load_isometric_preview_animation()

    def _get_group_bounds(self):
        min_x, min_y, max_x, max_y = float('inf'), float('inf'), float('-inf'), float('-inf')
        has_visible_sprites = False

        frame_data_list = self._get_generated_frame_data(apply_correction=True)

        for frame_data in frame_data_list:
            sprite_img = frame_data["image"]
            if sprite_img:
                has_visible_sprites = True
                paste_x, paste_y = frame_data["pos"]
                sprite_w, sprite_h = sprite_img.size
                
                min_x = min(min_x, paste_x)
                min_y = min(min_y, paste_y)
                max_x = max(max_x, paste_x + sprite_w)
                max_y = max(max_y, paste_y + sprite_h)
        
        if not has_visible_sprites:
            w, h = self.anim_data["frame_width"], self.anim_data["frame_height"]
            return (0, 0, w, h)

        return (min_x, min_y, max_x, max_y)

    def load_corrected_result_animation(self):
        for aid in self.result_after_ids: self.parent.after_cancel(aid)
        self.result_after_ids.clear()

        min_x, min_y, max_x, max_y = self._get_group_bounds()
        
        new_framewidth = math.ceil(max_x - min_x)
        new_frameheight = math.ceil(max_y - min_y)

        custom_frames_data = self._get_generated_frame_data(apply_correction=True)
        if not custom_frames_data: return

        final_offsets = []
        for frame_data in custom_frames_data:
            if frame_data["image"]:
                abs_paste_x, abs_paste_y = frame_data["pos"]
                final_offsets.append( (round(abs_paste_x - min_x), round(abs_paste_y - min_y)) )
            else:
                final_offsets.append( (0,0) )
        
        offset_texts = [f"Offset: {offset}" for offset in final_offsets]

        preview_canvas_width = new_framewidth + 20
        preview_canvas_height = new_frameheight + 20

        final_frames = []
        for frame_data in custom_frames_data:
            final_frame = Image.new('RGBA', (preview_canvas_width, preview_canvas_height), (211, 211, 211, 255))
            draw = ImageDraw.Draw(final_frame)

            box_x0 = (preview_canvas_width - new_framewidth) // 2
            box_y0 = (preview_canvas_height - new_frameheight) // 2
            box_x1 = box_x0 + new_framewidth
            box_y1 = box_y0 + new_frameheight
            draw.rectangle([box_x0, box_y0, box_x1, box_y1], fill=None, outline="grey")
            
            sprite_img = frame_data["image"]
            if sprite_img:
                abs_paste_x, abs_paste_y = frame_data["pos"]
                
                relative_paste_x = abs_paste_x - min_x
                relative_paste_y = abs_paste_y - min_y
                
                final_paste_x_in_box = box_x0 + int(round(relative_paste_x))
                final_paste_y_in_box = box_y0 + int(round(relative_paste_y))
                
                final_paste_pos = (final_paste_x_in_box, final_paste_y_in_box)
                final_frame.paste(sprite_img, final_paste_pos, sprite_img)

            final_frames.append(final_frame)

        durations = self.anim_data["durations"] * (len(final_frames) // len(self.anim_data["durations"]) + 1)
        self._start_animation_loop(
            image_label=self.result_label, 
            frames=final_frames, 
            durations=durations[:len(final_frames)], 
            id_storage_list=self.result_after_ids,
            text_label=self.corrected_offset_label,
            text_data=offset_texts
        )

    def _tint_image(self, image, color):
        image = image.convert('RGBA')
        color_img = Image.new('RGBA', image.size, color)
        alpha_mask = image.getchannel('A')
        tinted_sprite = Image.new('RGBA', image.size, (0, 0, 0, 0))
        tinted_sprite.paste(color_img, (0, 0), alpha_mask)
        return tinted_sprite

    def load_uncorrected_overlay_animation(self):
        for aid in self.overlay_after_ids: self.parent.after_cancel(aid)
        self.overlay_after_ids.clear()

        uncorrected_frames_data = self._get_generated_frame_data(apply_correction=False)
        if not uncorrected_frames_data: return

        uncorrected_frames = []
        frame_width, frame_height = self.anim_data["frame_width"], self.anim_data["frame_height"]
        for frame_data in uncorrected_frames_data:
            composite = Image.new('RGBA', (frame_width, frame_height), (0,0,0,0))
            if frame_data["image"]:
                paste_pos = (int(round(frame_data["pos"][0])), int(round(frame_data["pos"][1])))
                composite.paste(frame_data["image"], paste_pos, frame_data["image"])
            uncorrected_frames.append(composite)

        if len(self.group_frames) != len(uncorrected_frames): return
            
        canvas_width, canvas_height = self.anim_data["frame_width"] * 2, self.anim_data["frame_height"] * 2
        overlay_frames = []
        offset_texts = []
        
        for i in range(len(uncorrected_frames)):
            composite = Image.new('RGBA', (canvas_width, canvas_height), (0,0,0,0))
            tinted_original = self._tint_image(self.group_frames[i], (255, 0, 0, 128))
            tinted_custom = self._tint_image(uncorrected_frames[i], (0, 0, 255, 128))
            paste_pos = (self.anim_data["frame_width"] // 2, self.anim_data["frame_height"] // 2)
            composite.paste(tinted_original, paste_pos, tinted_original)
            composite.paste(tinted_custom, paste_pos, tinted_custom)
            overlay_frames.append(composite)

            center_orig = self._get_image_bottom_center(self.group_frames[i])
            center_custom = self._get_image_bottom_center(uncorrected_frames[i])

            if center_orig and center_custom:
                dx = center_custom[0] - center_orig[0]
                dy = center_custom[1] - center_orig[1]
                offset_texts.append(f"Offset: ({dx:+.1f}, {dy:+.1f})")
            else:
                offset_texts.append("Offset: (N/A)")

        durations = self.anim_data["durations"] * (len(overlay_frames) // len(self.anim_data["durations"]) + 1)
        self._start_animation_loop(
            image_label=self.overlay_label, 
            frames=overlay_frames, 
            durations=durations[:len(overlay_frames)], 
            id_storage_list=self.overlay_after_ids,
            text_label=self.offset_label,
            text_data=offset_texts
        )

    def _grid_to_screen(self, grid_x, grid_y, origin, TILE_WIDTH_HALF, TILE_HEIGHT_HALF):
        screen_x = origin[0] + (grid_x - grid_y) * TILE_WIDTH_HALF
        screen_y = origin[1] + (grid_x + grid_y) * TILE_HEIGHT_HALF
        return int(screen_x), int(screen_y)

    def _draw_iso_grid(self, image, origin, consts):
        draw = ImageDraw.Draw(image)
        fill_color = (200, 200, 200, 255)
        outline_color = (150, 150, 150, 255)
        
        for y in range(3):
            for x in range(3):
                pos = self._grid_to_screen(x, y, origin, consts['WIDTH_HALF'], consts['HEIGHT_HALF'])
                top = (pos[0] + consts['WIDTH_HALF'], pos[1])
                right = (pos[0] + consts['WIDTH'], pos[1] + consts['HEIGHT_HALF'])
                bottom = (pos[0] + consts['WIDTH_HALF'], pos[1] + consts['HEIGHT'])
                left = (pos[0], pos[1] + consts['HEIGHT_HALF'])
                draw.polygon([top, right, bottom, left], fill=fill_color, outline=outline_color)

    def load_isometric_preview_animation(self):
        for aid in self.iso_after_ids: self.parent.after_cancel(aid)
        self.iso_after_ids.clear()

        custom_frames_data = self._get_generated_frame_data(apply_correction=True)
        if not custom_frames_data: return

        min_x, min_y, max_x, max_y = self._get_group_bounds()
        group_fw = math.ceil(max_x - min_x)
        group_fh = math.ceil(max_y - min_y)

        base_sprite_img = None
        try:
            sprite_base_path = os.path.join(self.viewer.anim_folder, "sprite_base.png")
            if os.path.exists(sprite_base_path):
                base_sprite_img = Image.open(sprite_base_path).convert('RGBA')
        except Exception as e:
            print(f"Could not load sprite_base.png for preview: {e}")

        tile_consts = {'WIDTH': 32, 'HEIGHT': 16, 'WIDTH_HALF': 16, 'HEIGHT_HALF': 8}
        canvas_width = tile_consts['WIDTH'] * 5
        canvas_height = tile_consts['HEIGHT'] * 5

        iso_frames = []
        for frame_data in custom_frames_data:
            canvas = Image.new('RGBA', (canvas_width, canvas_height), (255, 255, 255, 0))
            draw = ImageDraw.Draw(canvas)
            
            world_anchor_x = canvas_width // 2
            world_anchor_y = canvas_height // 2

            center_tile_top_corner_x = world_anchor_x - tile_consts['WIDTH_HALF']
            center_tile_top_corner_y = world_anchor_y - tile_consts['HEIGHT_HALF']

            static_grid_origin_x = center_tile_top_corner_x
            static_grid_origin_y = center_tile_top_corner_y - 2 * tile_consts['HEIGHT_HALF']
            
            self._draw_iso_grid(canvas, (static_grid_origin_x, static_grid_origin_y), tile_consts)
            
            if base_sprite_img:
                shadow_w, shadow_h = base_sprite_img.size
                # Center the base sprite on the center of the middle tile
                shadow_paste_x = world_anchor_x - shadow_w // 2
                shadow_paste_y = (world_anchor_y + tile_consts['HEIGHT_HALF']) - shadow_h // 2
                canvas.paste(base_sprite_img, (shadow_paste_x, shadow_paste_y), base_sprite_img)

            frame_origin_x = world_anchor_x - (group_fw // 2)
            center_tile_bottom_y = world_anchor_y + tile_consts['HEIGHT_HALF']
            frame_origin_y = center_tile_bottom_y - group_fh

            box_x0 = frame_origin_x
            box_y0 = frame_origin_y
            box_x1 = box_x0 + group_fw
            box_y1 = box_y0 + group_fh
            draw.rectangle([box_x0, box_y0, box_x1, box_y1], outline="grey")

            sprite_img = frame_data["image"]
            if sprite_img:
                abs_paste_x, abs_paste_y = frame_data["pos"]
                relative_paste_x = abs_paste_x - min_x
                relative_paste_y = abs_paste_y - min_y

                paste_x = frame_origin_x + int(round(relative_paste_x))
                paste_y = frame_origin_y + int(round(relative_paste_y))
                
                canvas.paste(sprite_img, (paste_x, paste_y), sprite_img)

            # Zoom the final canvas for better visibility
            canvas = canvas.resize((canvas.width * 2, canvas.height * 2), Image.NEAREST)
            iso_frames.append(canvas)

        durations = self.anim_data["durations"] * (len(iso_frames) // len(self.anim_data["durations"]) + 1)
        self._start_animation_loop(
            image_label=self.iso_label, 
            frames=iso_frames, 
            durations=durations[:len(iso_frames)], 
            id_storage_list=self.iso_after_ids,
            thumbnail_size=(400, 400)
        )

    def set_sprite_values(self, sprite_numbers, mirror_flags):
        for idx, sprite_number in enumerate(sprite_numbers):
            if sprite_number > 0:
                self.string_vars[idx].set(str(sprite_number))
                self.mirror_vars[idx].set(mirror_flags[idx])

    def get_data(self):
        group_entry = {"name": self.name_entry.get().strip()}

        values_list = []
        for i, sv in enumerate(self.string_vars):
            sprite_id = int(sv.get()) if sv.get().isdigit() else 0
            is_mirrored = self.mirror_vars[i].get()
            values_list.append({"id": sprite_id, "mirrored": is_mirrored})

        min_x, min_y, max_x, max_y = self._get_group_bounds()
        
        group_entry["framewidth"] = math.ceil(max_x - min_x)
        group_entry["frameheight"] = math.ceil(max_y - min_y)

        frame_data_list = self._get_generated_frame_data(apply_correction=True)
        relative_offsets = []
        for frame_data in frame_data_list:
            if frame_data["image"]:
                abs_paste_x, abs_paste_y = frame_data["pos"]
                relative_paste_x = abs_paste_x - min_x
                relative_paste_y = abs_paste_y - min_y
                relative_offsets.append([round(relative_paste_x), round(relative_paste_y)])
            else:
                relative_offsets.append([0, 0])

        group_entry["values"] = values_list
        group_entry["offsets"] = relative_offsets
        return group_entry

    def _calculate_all_corrected_offsets(self):
        corrected_offsets = []
        frame_width, frame_height = self.anim_data["frame_width"], self.anim_data["frame_height"]

        for i, sv in enumerate(self.string_vars):
            sprite_id = int(sv.get()) if sv.get().isdigit() else 0
            is_mirrored = self.mirror_vars[i].get()

            original_anchor = self.group_metadata[i]['anchors'].get('black')
            if not original_anchor:
                corrected_offsets.append((0,0))
                continue

            sprite_to_paste = None
            if sprite_id > 0:
                try:
                    path = os.path.join(self.sprite_folder, f"sprite_{sprite_id}.png")
                    sprite_to_paste = Image.open(path).convert('RGBA')
                except FileNotFoundError:
                    pass
            
            if sprite_to_paste:
                if is_mirrored:
                    sprite_to_paste = ImageOps.mirror(sprite_to_paste)

                anchor_x, anchor_y = original_anchor
                sprite_w, sprite_h = sprite_to_paste.size
                initial_paste_x = anchor_x - sprite_w // 2
                initial_paste_y = anchor_y - sprite_h // 2
                
                temp_frame = Image.new('RGBA', (frame_width, frame_height), (0, 0, 0, 0))
                temp_frame.paste(sprite_to_paste, (initial_paste_x, initial_paste_y), sprite_to_paste)

                center_orig = self._get_image_bottom_center(self.group_frames[i])
                center_temp = self._get_image_bottom_center(temp_frame)

                correction_x, correction_y = 0, 0
                if center_orig and center_temp:
                    correction_x = center_orig[0] - center_temp[0]
                    correction_y = center_orig[1] - center_temp[1]

                corrected_anchor_x = anchor_x + int(round(correction_x))
                corrected_anchor_y = anchor_y + int(round(correction_y))
                corrected_offsets.append((corrected_anchor_x, corrected_anchor_y))
            else:
                corrected_offsets.append(original_anchor)
        
        return corrected_offsets

    def cleanup(self):
        for aid in self.after_ids: self.parent.after_cancel(aid)
        for aid in self.result_after_ids: self.parent.after_cancel(aid)
        for aid in self.overlay_after_ids: self.parent.after_cancel(aid)
        for aid in self.iso_after_ids: self.parent.after_cancel(aid)
        self.after_ids.clear()
        self.result_after_ids.clear()
        self.overlay_after_ids.clear()
        self.iso_after_ids.clear()

    def _start_animation_loop(self, image_label, frames, durations, id_storage_list, text_label=None, text_data=None, thumbnail_size=(200, 200)):
        current_frame = [0]
        def update():
            if not image_label.winfo_exists() or not frames: return
            idx = current_frame[0] % len(frames)
            
            frame = frames[idx]
            frame.thumbnail(thumbnail_size); img = ImageTk.PhotoImage(frame)
            image_label.config(image=img); image_label.image = img
            
            if text_label and text_data:
                text_label.config(text=text_data[idx % len(text_data)])
            
            delay = durations[idx % len(durations)] * 33; current_frame[0] += 1
            after_id = self.parent.after(delay, update)
            id_storage_list.append(after_id)
        update()

    def _get_default_group_name(self):
        anim_name = self.anim_data["name"]
        total_groups = self.anim_data["total_groups"]
        group_idx = self.group_idx
        DIRECTIONAL_NAMES_8 = ("down", "down-right", "right", "up-right", "up", "up-left", "left", "down-left")
        if total_groups == 8 and 0 <= group_idx < len(DIRECTIONAL_NAMES_8):
            return DIRECTIONAL_NAMES_8[group_idx]
        elif total_groups == 1:
            return anim_name.lower()
        return f"group{group_idx + 1}"