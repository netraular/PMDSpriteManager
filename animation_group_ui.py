# animation_group_ui.py

import os
from tkinter import Frame, Label, Button, Entry, BooleanVar, Checkbutton, StringVar
from PIL import Image, ImageTk, ImageDraw, ImageOps
import math
from ui_components.animation_player import AnimationPlayer
from ui_components.preview_generator import PreviewGenerator

class AnimationGroupUI:
    def __init__(self, parent, viewer, group_idx, anim_data, group_frames, group_offsets_frames, group_shadow_frames, group_metadata, sprite_folder, anim_folder, json_group_data, ai_callback):
        self.parent = parent
        self.viewer = viewer
        self.group_idx = group_idx
        self.anim_data = anim_data
        self.group_frames = group_frames
        self.sprite_folder = sprite_folder
        self.group_metadata = group_metadata
        self.json_group_data = json_group_data or {}
        self.ai_callback = ai_callback

        self.preview_generator = PreviewGenerator(
            anim_data, group_frames, group_metadata, group_shadow_frames, sprite_folder, anim_folder
        )
        self.players = {}
        
        self.string_vars = []
        self.mirror_vars = []
        self.custom_sprite_labels = []

        self._setup_ui()
        self._populate_initial_data()
        
        durations = self.anim_data["durations"]
        self.players["original"].set_animation([f.copy() for f in group_frames], durations)
        self.players["original"].play()
        if group_offsets_frames:
            self.players["offsets"].set_animation([f.copy() for f in group_offsets_frames], durations)
            self.players["offsets"].play()
        if group_shadow_frames:
            self.players["shadow"].set_animation([f.copy() for f in group_shadow_frames], durations)
            self.players["shadow"].play()

        self.refresh_all_custom_previews()
        self.refresh_all_previews()

    def _setup_ui(self):
        # Main container for the entire group UI
        main_container = Frame(self.parent, bd=2, relief="groove")
        main_container.pack(fill='x', padx=5, pady=5)

        # --- Column 1: Original Animation Previews ---
        self.col1_frame = Frame(main_container)

        # Header for Column 1
        col1_header = Frame(self.col1_frame)
        col1_header.pack(fill='x', pady=(0, 5))
        Label(col1_header, text=f"Group {self.group_idx + 1}", font=('Arial', 12, 'bold')).pack(side='left')
        self.name_entry = Entry(col1_header, width=20)
        self.name_entry.pack(side='left', padx=10)

        # Content for Column 1
        col1_content = Frame(self.col1_frame)
        col1_content.pack(fill='both', expand=True)
        self.players["original"] = AnimationPlayer(self.parent, Label(col1_content, bg="lightgrey"))
        self.players["original"].image_label.pack(side="left", padx=5)
        self.players["offsets"] = AnimationPlayer(self.parent, Label(col1_content, bg="lightgrey"))
        self.players["offsets"].image_label.pack(side="left", padx=5)
        self.players["shadow"] = AnimationPlayer(self.parent, Label(col1_content, bg="lightgrey"))
        self.players["shadow"].image_label.pack(side="left", padx=5)

        # --- Column 2: Individual Sprite Editor ---
        self.col2_frame = Frame(main_container)

        # Header for Column 2
        col2_header = Frame(self.col2_frame)
        col2_header.pack(fill='x', pady=(0, 5))
        Button(col2_header, text="AI Identify Sprites", command=lambda: self.ai_callback(self)).pack()

        # Content for Column 2 (the grid of frames)
        col2_content = Frame(self.col2_frame)
        col2_content.pack(fill='both', expand=True)
        
        durations = self.anim_data["durations"] * (len(self.group_frames) // len(self.anim_data["durations"]) + 1)
        for idx, frame in enumerate(self.group_frames):
            frame_cont = Frame(col2_content)
            frame_cont.grid(row=0, column=idx, padx=2, pady=2)
            
            disp_frame = self._draw_anchors_on_frame(frame.copy(), idx)
            disp_frame.thumbnail((80, 80))
            img = ImageTk.PhotoImage(disp_frame)
            Label(frame_cont, image=img, relief="sunken", bd=1).image = img
            Label(frame_cont, image=img).pack()
            
            custom_lbl = Label(frame_cont, relief="sunken", bd=1)
            custom_lbl.pack()
            self.custom_sprite_labels.append(custom_lbl)

            input_frame = Frame(frame_cont)
            input_frame.pack()
            sv = StringVar(value="0")
            Entry(input_frame, width=5, textvariable=sv).pack(side='left')
            mirror_var = BooleanVar()
            Checkbutton(input_frame, variable=mirror_var).pack(side='left')

            self.string_vars.append(sv)
            self.mirror_vars.append(mirror_var)
            
            callback = lambda *args, f_idx=idx: self.update_custom_sprite_preview(f_idx)
            sv.trace_add("write", callback)
            mirror_var.trace_add("write", callback)

            Label(frame_cont, text=f"Dur: {durations[idx]}", font=('Arial', 7)).pack()

        # --- Column 3: Generated Previews ---
        self.col3_frame = Frame(main_container)

        # Header for Column 3
        col3_header = Frame(self.col3_frame)
        col3_header.pack(fill='x', pady=(0, 5))
        Button(col3_header, text="Refresh Previews", command=self.refresh_all_previews).pack()

        # Content for Column 3
        col3_content = Frame(self.col3_frame)
        col3_content.pack(fill='both', expand=True)
        self._create_preview_panel(col3_content, "overlay", "Uncorrected Overlay", "Offset: (N/A)")
        self._create_preview_panel(col3_content, "corrected", "Corrected Preview", "Offset: (N/A)")
        self._create_preview_panel(col3_content, "iso_shadow", "Isometric Shadow", "Offset: (N/A)")
        self._create_preview_panel(col3_content, "iso_combined", "Isometric Combined", "Offset: (N/A)")

    def set_section_visibility(self, original_visible, editor_visible, previews_visible):
        if original_visible:
            self.col1_frame.pack(side='left', fill='y', padx=5, pady=5, anchor='n')
        else:
            self.col1_frame.pack_forget()

        if editor_visible:
            self.col2_frame.pack(side='left', fill='y', padx=5, pady=5, anchor='n')
        else:
            self.col2_frame.pack_forget()

        if previews_visible:
            self.col3_frame.pack(side='left', fill='y', padx=5, pady=5, anchor='n')
        else:
            self.col3_frame.pack_forget()

    def _create_preview_panel(self, parent, key, title, initial_text):
        frame = Frame(parent, bd=1, relief="sunken")
        frame.pack(side='left', fill='y', padx=(5, 0))
        Label(frame, text=title, font=('Arial', 8, 'bold')).pack(pady=(5,0))
        img_label = Label(frame); img_label.pack(pady=5, padx=5, expand=True)
        txt_label = Label(frame, text=initial_text, font=('Arial', 8)); txt_label.pack(pady=(0,5))
        self.players[key] = AnimationPlayer(self.parent, img_label, txt_label)

    def _populate_initial_data(self):
        default_name = self._get_default_group_name()
        self.name_entry.insert(0, self.json_group_data.get("name", default_name))
        
        values = self.json_group_data.get("values", [])
        for idx, sv in enumerate(self.string_vars):
            if idx < len(values):
                val = values[idx]
                sprite_id = val.get("id", 0) if isinstance(val, dict) else val
                mirrored = val.get("mirrored", False) if isinstance(val, dict) else False
                sv.set(str(sprite_id))
                self.mirror_vars[idx].set(mirrored)

    def _draw_anchors_on_frame(self, frame, frame_idx):
        if frame_idx < len(self.group_metadata):
            metadata = self.group_metadata[frame_idx]
            draw = ImageDraw.Draw(frame)
            s = 2
            for color, coords in metadata.get('anchors', {}).items():
                if coords:
                    x, y = coords
                    draw.line((x-s, y, x+s, y), fill=color, width=1)
                    draw.line((x, y-s, x, y+s), fill=color, width=1)
        return frame

    def refresh_all_custom_previews(self):
        for i in range(len(self.string_vars)):
            self.update_custom_sprite_preview(i)

    def update_custom_sprite_preview(self, frame_idx):
        sv, mirror_var = self.string_vars[frame_idx], self.mirror_vars[frame_idx]
        w, h = self.anim_data["frame_width"], self.anim_data["frame_height"]
        comp = Image.new('RGBA', (w, h))

        try:
            sprite_num = int(sv.get())
            sprite_img = self.preview_generator._load_sprite(sprite_num, mirror_var.get())
            if sprite_img:
                metadata = self.group_metadata[frame_idx]
                anchors = metadata.get('anchors', {})
                target = anchors.get("green") or anchors.get("black")
                if target:
                    paste_pos = (target[0] - sprite_img.width // 2, target[1] - sprite_img.height // 2)
                    comp.paste(sprite_img, paste_pos, sprite_img)
            elif sprite_num > 0:
                draw = ImageDraw.Draw(comp)
                draw.text((w // 2, h // 2), f"?{sprite_num}?", fill="red", anchor="mm")

            comp = self._draw_anchors_on_frame(comp, frame_idx)
        finally:
            comp.thumbnail((80, 80))
            img_tk = ImageTk.PhotoImage(comp)
            self.custom_sprite_labels[frame_idx].config(image=img_tk)
            self.custom_sprite_labels[frame_idx].image = img_tk

    def refresh_all_previews(self):
        ids = [int(sv.get()) if sv.get().isdigit() else 0 for sv in self.string_vars]
        mirrors = [mv.get() for mv in self.mirror_vars]
        durations = self.anim_data["durations"]

        uncorrected_data = self.preview_generator.get_generated_frame_data(ids, mirrors, False)
        corrected_data = self.preview_generator.get_generated_frame_data(ids, mirrors, True)

        overlay_res = self.preview_generator.generate_overlay_preview(uncorrected_data)
        self.players["overlay"].set_animation(**overlay_res)
        self.players["overlay"].play()

        corrected_res = self.preview_generator.generate_corrected_preview(corrected_data)
        self.players["corrected"].set_animation(**corrected_res)
        self.players["corrected"].play()
        
        iso_shadow_res = self.preview_generator.generate_iso_shadow_preview()
        self.players["iso_shadow"].set_animation(**iso_shadow_res)
        self.players["iso_shadow"].play()

        iso_combined_res = self.preview_generator.generate_iso_combined_preview(corrected_data)
        self.players["iso_combined"].set_animation(**iso_combined_res)
        self.players["iso_combined"].play()
    
    def set_sprite_values(self, sprite_numbers, mirror_flags):
        for idx, num in enumerate(sprite_numbers):
            if num > 0:
                self.string_vars[idx].set(str(num))
                self.mirror_vars[idx].set(mirror_flags[idx])

    def get_data(self):
        ids = [int(sv.get()) if sv.get().isdigit() else 0 for sv in self.string_vars]
        mirrors = [mv.get() for mv in self.mirror_vars]
        
        corrected_data = self.preview_generator.get_generated_frame_data(ids, mirrors, True)
        min_x, min_y, max_x, max_y = self.preview_generator.get_group_bounds(corrected_data)
        
        offsets = [[round(d["pos"][0] - min_x), round(d["pos"][1] - min_y)] if d["image"] else [0,0] for d in corrected_data]
        values = [{"id": i, "mirrored": m} for i, m in zip(ids, mirrors)]

        return {
            "name": self.name_entry.get().strip(),
            "framewidth": math.ceil(max_x - min_x),
            "frameheight": math.ceil(max_y - min_y),
            "values": values,
            "offsets": offsets
        }

    def cleanup(self):
        for player in self.players.values():
            player.stop()
        self.players.clear()

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