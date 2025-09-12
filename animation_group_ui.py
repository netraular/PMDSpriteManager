# animation_group_ui.py

import os
from tkinter import Frame, Label, Button, Entry, BooleanVar, Checkbutton, StringVar, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageOps

class AnimationGroupUI:
    def __init__(self, parent, group_idx, anim_data, group_frames, group_offsets_frames, group_metadata, sprite_folder, json_group_data, ai_callback):
        self.parent = parent
        self.group_idx = group_idx
        self.anim_data = anim_data
        self.group_frames = group_frames
        self.group_offsets_frames = group_offsets_frames
        self.group_metadata = group_metadata
        self.sprite_folder = sprite_folder
        self.json_group_data = json_group_data or {}
        self.ai_callback = ai_callback

        self.after_ids = []
        self.preview_after_ids = []
        self.overlay_after_ids = []
        
        self.string_vars = []
        self.mirror_vars = []
        self.custom_sprite_labels = []

        self._setup_ui()
        self._populate_initial_data()
        self.refresh_all_custom_previews()
        self.load_result_animation()
        self.load_overlay_animation()

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
        frames_panel = Frame(content_frame); frames_panel.pack(side="left", fill="x", expand=True)
        
        result_preview_frame = Frame(row_container, bd=1, relief="sunken"); result_preview_frame.pack(side='left', fill='y', padx=(5, 0))
        Button(result_preview_frame, text="Load Preview", command=self.load_result_animation).pack(pady=2, padx=2)
        self.result_label = Label(result_preview_frame); self.result_label.pack(pady=5, padx=5, expand=True)
        
        overlay_preview_frame = Frame(row_container, bd=1, relief="sunken"); overlay_preview_frame.pack(side='left', fill='y', padx=(5, 0))
        Button(overlay_preview_frame, text="Load Overlay", command=self.load_overlay_animation).pack(pady=2, padx=2)
        self.overlay_label = Label(overlay_preview_frame); self.overlay_label.pack(pady=5, padx=5, expand=True)

        durations = self.anim_data["durations"] * (len(self.group_frames) // len(self.anim_data["durations"]) + 1)
        
        anim_label = Label(anim_panel); anim_label.pack()
        self._start_animation_loop(anim_label, [f.copy() for f in self.group_frames], durations[:len(self.group_frames)], self.after_ids)
        
        if self.group_offsets_frames:
            anim_label_copy = Label(anim_panel_copy, bg="lightgrey"); anim_label_copy.pack()
            self._start_animation_loop(anim_label_copy, [f.copy() for f in self.group_offsets_frames], durations[:len(self.group_offsets_frames)], self.after_ids)

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

    def _generate_custom_animation_frames(self):
        sprite_numbers = [int(sv.get()) if sv.get().isdigit() else 0 for sv in self.string_vars]
        result_frames = []
        frame_width, frame_height = self.anim_data["frame_width"], self.anim_data["frame_height"]

        for i, num in enumerate(sprite_numbers):
            composite_frame = Image.new('RGBA', (frame_width, frame_height), (0, 0, 0, 0))
            sprite_to_paste = None
            if num > 0:
                sprite_path = os.path.join(self.sprite_folder, f"sprite_{num}.png")
                try:
                    sprite_to_paste = Image.open(sprite_path).convert('RGBA')
                except FileNotFoundError:
                    pass
            
            if sprite_to_paste:
                all_anchors = self.group_metadata[i]['anchors']
                sprite_center_target = all_anchors.get("green") or all_anchors.get("black")
                anchor_x, anchor_y = sprite_center_target
                
                if self.mirror_vars[i].get():
                    sprite_to_paste = ImageOps.mirror(sprite_to_paste)

                sprite_w, sprite_h = sprite_to_paste.size
                paste_x, paste_y = anchor_x - sprite_w // 2, anchor_y - sprite_h // 2
                composite_frame.paste(sprite_to_paste, (paste_x, paste_y), sprite_to_paste)

            result_frames.append(composite_frame)
        return result_frames

    def load_result_animation(self):
        for aid in self.preview_after_ids: self.parent.after_cancel(aid)
        self.preview_after_ids.clear()

        custom_frames = self._generate_custom_animation_frames()
        if not custom_frames: return

        canvas_width, canvas_height = self.anim_data["frame_width"] * 2, self.anim_data["frame_height"] * 2
        final_frames = []
        for frame in custom_frames:
            final_frame = Image.new('RGBA', (canvas_width, canvas_height), (211, 211, 211, 255))
            draw = ImageDraw.Draw(final_frame)
            box_x0, box_y0 = self.anim_data["frame_width"] // 2, self.anim_data["frame_height"] // 2
            box_x1, box_y1 = box_x0 + self.anim_data["frame_width"], box_y0 + self.anim_data["frame_height"]
            draw.rectangle([box_x0, box_y0, box_x1, box_y1], fill=None, outline="grey")
            
            final_frame.paste(frame, (box_x0, box_y0), frame)
            final_frames.append(final_frame)

        durations = self.anim_data["durations"] * (len(final_frames) // len(self.anim_data["durations"]) + 1)
        self._start_animation_loop(self.result_label, final_frames, durations[:len(final_frames)], self.preview_after_ids)

    def _tint_image(self, image, color):
        image = image.convert('RGBA')
        color_img = Image.new('RGBA', image.size, color)
        alpha_mask = image.getchannel('A')
        tinted_sprite = Image.new('RGBA', image.size, (0, 0, 0, 0))
        tinted_sprite.paste(color_img, (0, 0), alpha_mask)
        return tinted_sprite

    def load_overlay_animation(self):
        for aid in self.overlay_after_ids: self.parent.after_cancel(aid)
        self.overlay_after_ids.clear()

        custom_frames = self._generate_custom_animation_frames()
        if not custom_frames or len(self.group_frames) != len(custom_frames): return
            
        canvas_width, canvas_height = self.anim_data["frame_width"] * 2, self.anim_data["frame_height"] * 2
        overlay_frames = []
        
        for i in range(len(custom_frames)):
            composite = Image.new('RGBA', (canvas_width, canvas_height), (0,0,0,0))

            tinted_original = self._tint_image(self.group_frames[i], (255, 0, 0, 128))
            tinted_custom = self._tint_image(custom_frames[i], (0, 0, 255, 128))

            paste_pos = (self.anim_data["frame_width"] // 2, self.anim_data["frame_height"] // 2)
            
            composite.paste(tinted_original, paste_pos, tinted_original)
            composite.paste(tinted_custom, paste_pos, tinted_custom)
            
            overlay_frames.append(composite)

        durations = self.anim_data["durations"] * (len(overlay_frames) // len(self.anim_data["durations"]) + 1)
        self._start_animation_loop(self.overlay_label, overlay_frames, durations[:len(overlay_frames)], self.overlay_after_ids)

    def set_sprite_values(self, sprite_numbers, mirror_flags):
        for idx, sprite_number in enumerate(sprite_numbers):
            if sprite_number > 0:
                self.string_vars[idx].set(str(sprite_number))
                self.mirror_vars[idx].set(mirror_flags[idx])

    def get_data(self):
        group_entry = {"name": self.name_entry.get().strip(), "mirrored": False}
        values_list = []
        for i, sv in enumerate(self.string_vars):
            sprite_id = int(sv.get()) if sv.get().isdigit() else 0
            is_mirrored = self.mirror_vars[i].get()
            values_list.append({"id": sprite_id, "mirrored": is_mirrored})
        group_entry["values"] = values_list
        group_entry["offsets"] = [m['anchors']['black'] for m in self.group_metadata]
        return group_entry

    def cleanup(self):
        for aid in self.after_ids: self.parent.after_cancel(aid)
        for aid in self.preview_after_ids: self.parent.after_cancel(aid)
        for aid in self.overlay_after_ids: self.parent.after_cancel(aid)
        self.after_ids.clear()
        self.preview_after_ids.clear()
        self.overlay_after_ids.clear()

    def _start_animation_loop(self, label, frames, durations, id_storage_list):
        current_frame = [0]
        def update():
            if not label.winfo_exists() or not frames: return
            idx = current_frame[0] % len(frames)
            frame = frames[idx]
            frame.thumbnail((200, 200)); img = ImageTk.PhotoImage(frame)
            label.config(image=img); label.image = img
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