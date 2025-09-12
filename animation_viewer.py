# animation_viewer.py

import os
import json
from tkinter import Frame, Label, Canvas, Scrollbar, Entry, messagebox, Toplevel, BooleanVar, Checkbutton, OptionMenu, StringVar, Button, TclError
from PIL import Image, ImageTk, ImageDraw, ImageOps
import xml.etree.ElementTree as ET
from sprite_sheet_handler import SpriteSheetHandler
import math
from sprite_matcher import SpriteMatcher

class AnimationViewer:
    def __init__(self, parent_frame, anim_folder):
        self.parent_frame = parent_frame
        self.anim_folder = anim_folder
        self.sprite_folder = os.path.join(anim_folder, "Animations")
        self.anim_data = self.load_anim_data()
        self.current_anim_index = 0
        self.after_ids = []
        self.current_sprites_entries = []
        self.group_widgets = {}
        
        self.setup_interface()
        self.show_animation()

    def setup_interface(self):
        self.main_canvas = Canvas(self.parent_frame)
        self.scrollbar = Scrollbar(self.parent_frame, orient="vertical", command=self.main_canvas.yview)
        self.scroll_frame = Frame(self.main_canvas)
        
        self.scroll_frame.bind("<Configure>", lambda e: self.main_canvas.configure(
            scrollregion=self.main_canvas.bbox("all")
        ))
        
        self.main_canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.main_canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.main_canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

    def load_anim_data(self):
        anim_data_path = os.path.join(self.sprite_folder, "AnimData.xml")
        if not os.path.exists(anim_data_path):
            raise FileNotFoundError(f"XML file not found in: {self.sprite_folder}")
        tree = ET.parse(anim_data_path)
        return self.process_xml(tree)

    def process_xml(self, tree):
        animations = []
        anims_root = tree.getroot().find("Anims")
        xml_anims_map = {anim.find('Name').text: anim for anim in anims_root.findall('Anim')}
        for anim_name, anim_xml in xml_anims_map.items():
            copy_of_tag = anim_xml.find('CopyOf')
            anim_data = {}
            try:
                if copy_of_tag is not None:
                    source_name = copy_of_tag.text
                    if source_name not in xml_anims_map:
                        print(f"Warning: Source animation '{source_name}' for '{anim_name}' not found. Skipping.")
                        continue
                    source_anim_xml = xml_anims_map[source_name]
                    anim_data = {"name": anim_name, "frame_width": int(source_anim_xml.find("FrameWidth").text), "frame_height": int(source_anim_xml.find("FrameHeight").text), "durations": [int(d.text) for d in source_anim_xml.findall("Durations/Duration")], "image_path": os.path.join(self.sprite_folder, f"{anim_name}-Anim.png")}
                else:
                    fw_tag, fh_tag = anim_xml.find("FrameWidth"), anim_xml.find("FrameHeight")
                    if fw_tag is None or fh_tag is None:
                        print(f"Warning: Animation '{anim_name}' is missing FrameWidth/FrameHeight and is not a copy. Skipping.")
                        continue
                    anim_data = {"name": anim_name, "frame_width": int(fw_tag.text), "frame_height": int(fh_tag.text), "durations": [int(d.text) for d in anim_xml.findall("Durations/Duration")], "image_path": os.path.join(self.sprite_folder, f"{anim_name}-Anim.png")}
                if not os.path.exists(anim_data["image_path"]):
                    print(f"Warning: Image file for animation '{anim_data['name']}' not found. Skipping: {anim_data['image_path']}")
                    continue
                with Image.open(anim_data["image_path"]) as img:
                    anim_data["total_groups"] = img.height // anim_data["frame_height"]
                    anim_data["frames_per_group"] = img.width // anim_data["frame_width"]
                animations.append(anim_data)
            except Exception as e:
                print(f"Error processing animation '{anim_name}': {e}. Skipping.")
        return animations

    def _get_default_group_name(self, anim_name, total_groups, group_idx):
        DIRECTIONAL_NAMES_8 = ("down", "down-right", "right", "up-right", "up", "up-left", "left", "down-left")
        if total_groups == 8 and 0 <= group_idx < len(DIRECTIONAL_NAMES_8):
            return DIRECTIONAL_NAMES_8[group_idx]
        elif total_groups == 1:
            return anim_name.lower()
        return f"group{group_idx + 1}"

    def show_animation(self):
        self.clear_animations()
        self.group_names, self.group_widgets = [], {}
        for widget in self.scroll_frame.winfo_children(): widget.destroy()
        if not self.anim_data:
             Label(self.scroll_frame, text="No animations found or loaded.", font=('Arial', 14, 'bold')).pack(pady=20); return
        anim = self.anim_data[self.current_anim_index]
        handler = SpriteSheetHandler(anim["image_path"])
        all_frames = handler.split_animation_frames(anim["frame_width"], anim["frame_height"])
        
        total_groups, frames_per_group = anim["total_groups"], anim["frames_per_group"]
        json_data = self.load_json_data(anim["name"])
        run_ai_automatically = json_data is None
        Label(self.scroll_frame, text=f"Animation: {anim['name']}", font=('Arial', 14, 'bold')).pack(pady=10)
        for group_idx in range(total_groups):
            row_container = Frame(self.scroll_frame); row_container.pack(fill='x', padx=5, pady=5)
            group_frame = Frame(row_container, bd=2, relief="groove"); group_frame.pack(side='left', fill='both', expand=True, padx=(0, 5))
            header_frame = Frame(group_frame); header_frame.pack(fill='x', pady=5, padx=5)
            header_left = Frame(header_frame); header_left.pack(side='left', fill='x', expand=True)
            Label(header_left, text=f"Group {group_idx + 1}", font=('Arial', 12, 'bold')).pack(side='left')
            group_name_entry = Entry(header_left, width=20); group_name_entry.pack(side='left', padx=10)
            self.group_names.append(group_name_entry)

            ai_button = Button(header_left, text="AI Identify Sprites", command=lambda idx=group_idx: self.identify_group_sprites(idx)); ai_button.pack(side='left', padx=10)
            
            content_frame = Frame(group_frame); content_frame.pack(fill="both", expand=True)
            animation_previews_container = Frame(content_frame); animation_previews_container.pack(side="left", padx=10)
            anim_panel = Frame(animation_previews_container); anim_panel.pack(side="left", padx=5)
            anim_panel_copy = Frame(animation_previews_container); anim_panel_copy.pack(side="left", padx=5)
            frames_panel = Frame(content_frame); frames_panel.pack(side="left", fill="x", expand=True)
            result_preview_frame = Frame(row_container, bd=1, relief="sunken"); result_preview_frame.pack(side='left', fill='y', padx=(5, 0))
            Button(result_preview_frame, text="Load Preview", command=lambda idx=group_idx: self.load_result_animation(idx)).pack(pady=2, padx=2)
            result_label = Label(result_preview_frame); result_label.pack(pady=5, padx=5, expand=True)
            
            self.group_widgets[group_idx] = {
                "ai_button": ai_button,
                "entries": [], "frame": frames_panel, "result_label": result_label,
                "preview_after_ids": [], "custom_sprite_labels": [], "string_vars": [], "mirror_vars": []
            }
            start, end = group_idx * frames_per_group, (group_idx + 1) * frames_per_group
            group_frames = all_frames[start:end]
            durations = anim["durations"] * (len(group_frames) // len(anim["durations"]) + 1)
            
            anim_label = Label(anim_panel); anim_label.pack()
            self._start_animation_loop(anim_label, [f.copy() for f in group_frames], durations[:len(group_frames)], self.after_ids)
            
            anim_label_copy = Label(anim_panel_copy, bg="lightgrey"); anim_label_copy.pack()
            offsets_image_path = anim["image_path"].replace("-Anim.png", "-Offsets.png")
            if os.path.exists(offsets_image_path):
                offsets_handler = SpriteSheetHandler(offsets_image_path)
                all_offsets_frames = offsets_handler.split_animation_frames(anim["frame_width"], anim["frame_height"])
                group_offsets_frames = all_offsets_frames[start:end]
                self._start_animation_loop(anim_label_copy, [f.copy() for f in group_offsets_frames], durations[:len(group_offsets_frames)], self.after_ids)

            for idx, frame in enumerate(group_frames):
                frame_container = Frame(frames_panel); frame_container.grid(row=0, column=idx, padx=2, pady=2)
                
                frame.thumbnail((80, 80)); img = ImageTk.PhotoImage(frame)
                lbl = Label(frame_container, image=img, relief="sunken", bd=1); lbl.image = img; lbl.pack()
                
                custom_sprite_lbl = Label(frame_container, relief="sunken", bd=1); custom_sprite_lbl.pack()
                self.group_widgets[group_idx]["custom_sprite_labels"].append(custom_sprite_lbl)

                input_frame = Frame(frame_container); input_frame.pack()
                sv = StringVar()
                entry = Entry(input_frame, width=5, textvariable=sv); entry.insert(0, "0")
                entry.pack(side='left')
                
                mirror_var = BooleanVar()
                cb = Checkbutton(input_frame, variable=mirror_var); cb.pack(side='left')

                self.group_widgets[group_idx]["entries"].append(entry)
                self.group_widgets[group_idx]["string_vars"].append(sv)
                self.group_widgets[group_idx]["mirror_vars"].append(mirror_var)
                
                global_frame_idx = start + idx
                callback = lambda *args, g_idx=group_idx, f_idx=idx, gfi=global_frame_idx: self.update_custom_sprite_preview(g_idx, f_idx, gfi)
                sv.trace_add("write", callback)
                mirror_var.trace_add("write", callback)

                Label(frame_container, text=f"Dur: {durations[idx]}", font=('Arial', 7)).pack()
            
            default_name = self._get_default_group_name(anim["name"], total_groups, group_idx)
            group_name_entry.insert(0, default_name)

            if json_data and "sprites" in json_data:
                group_info = json_data["sprites"].get(str(group_idx + 1), {})
                if group_info:
                    group_name_entry.delete(0, 'end'); group_name_entry.insert(0, group_info.get("name", default_name))
                    sprite_values = group_info.get("values", [])
                    for idx, sv in enumerate(self.group_widgets[group_idx]["string_vars"]):
                        if idx < len(sprite_values):
                            frame_val = sprite_values[idx]
                            sprite_id = frame_val if isinstance(frame_val, int) else frame_val.get("id", 0)
                            per_sprite_mirror = False if isinstance(frame_val, int) else frame_val.get("mirrored", False)
                            sv.set(str(sprite_id))
                            self.group_widgets[group_idx]["mirror_vars"][idx].set(per_sprite_mirror)
            
            if run_ai_automatically and not (json_data and "sprites" in json_data):
                self.identify_group_sprites(group_idx)

            self.load_result_animation(group_idx)

    def refresh_all_custom_previews_in_group(self, group_idx):
        anim = self.anim_data[self.current_anim_index]
        start_frame_index = group_idx * anim["frames_per_group"]
        num_frames = len(self.group_widgets[group_idx]["string_vars"])
        for i in range(num_frames):
            global_frame_idx = start_frame_index + i
            self.update_custom_sprite_preview(group_idx, i, global_frame_idx)

    def update_custom_sprite_preview(self, group_idx, frame_idx, global_frame_idx):
        widgets = self.group_widgets[group_idx]
        sv = widgets["string_vars"][frame_idx]
        mirror_var = widgets["mirror_vars"][frame_idx]
        label_to_update = widgets["custom_sprite_labels"][frame_idx]
        
        sprite_num_str = sv.get()
        if not sprite_num_str.isdigit() or int(sprite_num_str) <= 0:
            label_to_update.config(image=''); return

        sprite_path = os.path.join(self.anim_folder, "Sprites", f"sprite_{int(sprite_num_str)}.png")
        
        try:
            sprite_img = Image.open(sprite_path).convert('RGBA')
            
            if mirror_var.get():
                sprite_img = ImageOps.mirror(sprite_img)

            sprite_img.thumbnail((80, 80))
            img_tk = ImageTk.PhotoImage(sprite_img)
            label_to_update.config(image=img_tk)
            label_to_update.image = img_tk
        except FileNotFoundError:
            label_to_update.config(image='')

    def _get_frame_metadata(self, frame_image):
        if frame_image.mode != 'RGBA':
            frame_image = frame_image.convert('RGBA')
        
        width, height = frame_image.size
        pixels = frame_image.load()
        
        anchor = None
        for x in range(width):
            for y in range(height):
                if pixels[x, y] == (0, 0, 0, 255):
                    anchor = (x, y)
                    break
            if anchor:
                break
        
        return {"anchor": anchor or (width // 2, height // 2)}

    def load_result_animation(self, group_idx):
        widgets = self.group_widgets[group_idx]
        
        for aid in widgets["preview_after_ids"]:
            self.parent_frame.after_cancel(aid)
        widgets["preview_after_ids"].clear()

        entries = widgets["entries"]
        result_label = widgets["result_label"]
        anim = self.anim_data[self.current_anim_index]
        
        sprite_numbers = [int(entry.get()) if entry.get().isdigit() else 0 for entry in entries]
        sprites_folder = os.path.join(self.anim_folder, "Sprites")
        if not os.path.exists(sprites_folder):
            messagebox.showwarning("Warning", "The 'Sprites' folder was not found."); return

        frame_metadata = []
        offsets_image_path = anim["image_path"].replace("-Anim.png", "-Offsets.png")
        if os.path.exists(offsets_image_path):
            offsets_handler = SpriteSheetHandler(offsets_image_path)
            all_offsets_frames = offsets_handler.split_animation_frames(anim["frame_width"], anim["frame_height"])
            start, end = group_idx * anim["frames_per_group"], (group_idx + 1) * anim["frames_per_group"]
            frame_metadata = [self._get_frame_metadata(f) for f in all_offsets_frames[start:end]]
        else:
            default_anchor = (anim["frame_width"] // 2, anim["frame_height"] // 2)
            frame_metadata = [{"anchor": default_anchor}] * len(sprite_numbers)

        result_frames = []
        canvas_width, canvas_height = anim["frame_width"] * 2, anim["frame_height"] * 2

        for i, num in enumerate(sprite_numbers):
            composite_frame = Image.new('RGBA', (canvas_width, canvas_height), (0, 0, 0, 0))
            sprite_to_paste = None
            if num <= 0:
                placeholder = Image.new('RGBA', (40, 40), (0, 0, 0, 0)); draw = ImageDraw.Draw(placeholder)
                draw.text((10, 10), "?", fill="red"); sprite_to_paste = placeholder
            else:
                sprite_path = os.path.join(sprites_folder, f"sprite_{num}.png")
                try:
                    sprite_img = Image.open(sprite_path).convert('RGBA')
                    sprite_to_paste = sprite_img
                except FileNotFoundError:
                    placeholder = Image.new('RGBA', (40, 40), (0, 0, 0, 0)); draw = ImageDraw.Draw(placeholder)
                    draw.text((5, 10), f"!{num}!", fill="red"); sprite_to_paste = placeholder
            
            if sprite_to_paste:
                anchor_x, anchor_y = frame_metadata[i]['anchor']
                per_sprite_mirror = widgets["mirror_vars"][i].get()
                
                if per_sprite_mirror:
                    sprite_to_paste = ImageOps.mirror(sprite_to_paste)
                    anchor_x = anim["frame_width"] - 1 - anchor_x

                base_x, base_y = anchor_x + (anim["frame_width"] // 2), anchor_y + (anim["frame_height"] // 2)
                sprite_w, sprite_h = sprite_to_paste.size
                paste_x, paste_y = base_x - sprite_w // 2, base_y - sprite_h // 2
                
                composite_frame.paste(sprite_to_paste, (paste_x, paste_y), sprite_to_paste)

            result_frames.append(composite_frame)
        
        durations = anim["durations"] * (len(result_frames) // len(anim["durations"]) + 1)
        self._start_animation_loop(result_label, result_frames, durations[:len(result_frames)], widgets["preview_after_ids"])

    def identify_group_sprites(self, group_idx):
        try:
            anim = self.anim_data[self.current_anim_index]
            handler = SpriteSheetHandler(anim["image_path"])
            group_frames = handler.split_animation_frames(anim["frame_width"], anim["frame_height"])[group_idx * anim["frames_per_group"]:(group_idx + 1) * anim["frames_per_group"]]
            sprites_folder = os.path.join(self.anim_folder, "Sprites")
            if not os.path.exists(sprites_folder):
                print(f"Warning: 'Sprites' folder not found. Cannot run AI identification."); return
            
            matcher = SpriteMatcher(sprites_folder)
            match_data = matcher.match_group(group_frames)
            
            sprite_numbers = match_data["frame_matches"]
            per_frame_mirrors = match_data["per_frame_mirror"]

            for idx, sprite_number in enumerate(sprite_numbers):
                if sprite_number > 0:
                    self.group_widgets[group_idx]["string_vars"][idx].set(str(sprite_number))
                    self.group_widgets[group_idx]["mirror_vars"][idx].set(per_frame_mirrors[idx])
        except Exception as e:
            if isinstance(e, FileNotFoundError) and "Sprites folder not found" in str(e):
                 print(f"Warning: 'Sprites' folder not found. Cannot run AI identification.")
            else: messagebox.showerror("Error", f"Error during identification: {str(e)}")

    def clear_animations(self):
        for aid in self.after_ids: self.parent_frame.after_cancel(aid)
        self.after_ids.clear()
        for group_idx in self.group_widgets:
            for aid in self.group_widgets[group_idx].get("preview_after_ids", []):
                self.parent_frame.after_cancel(aid)
            if "preview_after_ids" in self.group_widgets[group_idx]:
                self.group_widgets[group_idx]["preview_after_ids"].clear()

    def _start_animation_loop(self, label, frames, durations, id_storage_list):
        current_frame = [0]
        def update():
            if not label.winfo_exists() or not frames: return
            idx = current_frame[0] % len(frames)
            frame = frames[idx]
            frame.thumbnail((200, 200)); img = ImageTk.PhotoImage(frame)
            label.config(image=img); label.image = img
            delay = durations[idx % len(durations)] * 33; current_frame[0] += 1
            after_id = self.parent_frame.after(delay, update)
            id_storage_list.append(after_id)
        update()

    def prev_animation(self):
        if self.anim_data: self.current_anim_index = (self.current_anim_index - 1) % len(self.anim_data); self.show_animation()
    def next_animation(self):
        if self.anim_data: self.current_anim_index = (self.current_anim_index + 1) % len(self.anim_data); self.show_animation()
    
    def view_sprites(self):
        sprites_folder = os.path.join(self.anim_folder, "Sprites")
        if not os.path.exists(sprites_folder): messagebox.showwarning("Warning", "No 'Sprites' folder found"); return
        sprite_files = sorted([f for f in os.listdir(sprites_folder) if f.lower().endswith('.png')], key=lambda x: int(x.split('_')[-1].split('.')[0]))
        if not sprite_files: messagebox.showwarning("Warning", "No sprites found in the 'Sprites' folder"); return
        num_sprites = len(sprite_files); grid_size = math.ceil(math.sqrt(num_sprites))
        sprite_window = Toplevel(self.parent_frame); sprite_window.title(f"Sprites Gallery ({num_sprites} sprites)")
        canvas = Canvas(sprite_window); scrollbar = Scrollbar(sprite_window, orient="vertical", command=canvas.yview)
        scroll_frame = Frame(canvas); scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw"); canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True); scrollbar.pack(side="right", fill="y")
        for idx, file in enumerate(sprite_files):
            try:
                sprite_number = int(file.split('_')[-1].split('.')[0])
                row, col = (sprite_number - 1) // grid_size, (sprite_number - 1) % grid_size
                img = Image.open(os.path.join(sprites_folder, file)); img.thumbnail((100, 100)); photo = ImageTk.PhotoImage(img)
                frame = Frame(scroll_frame); frame.grid(row=row, column=col, padx=5, pady=5)
                Label(frame, image=photo).pack(); Label(frame, text=file, font=('Arial', 8)).pack(); frame.photo = photo
            except Exception as e: print(f"Error loading {file}: {str(e)}")

    def _get_data_from_current_view(self):
        try:
            group_names = [entry.get().strip() for entry in self.group_names]
            if any(not name for name in group_names): messagebox.showerror("Error", "All group names must be filled."); return None
            if len(group_names) != len(set(group_names)): messagebox.showerror("Error", "Duplicate group names are not allowed."); return None
            anim = self.anim_data[self.current_anim_index]; grouped_sprites = {}
            for group_idx, group_name in enumerate(group_names):
                group_entry = {"name": group_name, "mirrored": False}
                
                entries = self.group_widgets[group_idx]["entries"]
                mirror_vars = self.group_widgets[group_idx]["mirror_vars"]
                values_list = []
                for i, entry in enumerate(entries):
                    sprite_id = int(entry.get()) if entry.get().isdigit() else 0
                    is_mirrored = mirror_vars[i].get()
                    values_list.append({"id": sprite_id, "mirrored": is_mirrored})
                
                group_entry["values"] = values_list
                
                offsets = []
                offsets_image_path = anim["image_path"].replace("-Anim.png", "-Offsets.png")
                if os.path.exists(offsets_image_path):
                    offsets_handler = SpriteSheetHandler(offsets_image_path)
                    all_offsets_frames = offsets_handler.split_animation_frames(anim["frame_width"], anim["frame_height"])
                    start, end = group_idx * anim["frames_per_group"], (group_idx + 1) * anim["frames_per_group"]
                    offsets = [self._get_frame_metadata(f)['anchor'] for f in all_offsets_frames[start:end]]
                group_entry["offsets"] = offsets

                grouped_sprites[str(group_idx + 1)] = group_entry
            return {"index": self.current_anim_index, "name": anim["name"], "framewidth": anim["frame_width"], "frameheight": anim["frame_height"], "sprites": grouped_sprites, "durations": anim["durations"]}
        except Exception as e: messagebox.showerror("Error", f"Failed to gather data from view: {str(e)}"); return None

    def _generate_headless_data(self, index):
        anim = self.anim_data[index]
        json_data = self.load_json_data(anim['name'])
        if json_data: return json_data
        print(f"Generating default data for '{anim['name']}'...")
        grouped_sprites = {}
        try:
            sprites_folder = os.path.join(self.anim_folder, "Sprites")
            matcher = SpriteMatcher(sprites_folder) if os.path.exists(sprites_folder) else None
            handler = SpriteSheetHandler(anim["image_path"])
            all_frames = handler.split_animation_frames(anim["frame_width"], anim["frame_height"])
            
            offsets_image_path = anim["image_path"].replace("-Anim.png", "-Offsets.png")
            all_offsets_frames = []
            if os.path.exists(offsets_image_path):
                offsets_handler = SpriteSheetHandler(offsets_image_path)
                all_offsets_frames = offsets_handler.split_animation_frames(anim["frame_width"], anim["frame_height"])

            for group_idx in range(anim["total_groups"]):
                group_name = self._get_default_group_name(anim["name"], anim["total_groups"], group_idx)
                values, offsets = [], []
                start, end = group_idx * anim["frames_per_group"], (group_idx + 1) * anim["frames_per_group"]
                
                if matcher:
                    match_data = matcher.match_group(all_frames[start:end])
                    values = [{"id": sprite_id, "mirrored": mirror_flag} for sprite_id, mirror_flag in zip(match_data["frame_matches"], match_data["per_frame_mirror"])]
                else:
                    values = [{"id": 0, "mirrored": False}] * anim["frames_per_group"]
                
                if all_offsets_frames:
                    offsets = [self._get_frame_metadata(f)['anchor'] for f in all_offsets_frames[start:end]]

                grouped_sprites[str(group_idx + 1)] = {"name": group_name, "mirrored": False, "values": values, "offsets": offsets}
        except Exception as e: print(f"Could not auto-generate data for '{anim['name']}': {e}"); return None
        return {"index": index, "name": anim["name"], "framewidth": anim["frame_width"], "frameheight": anim["frame_height"], "sprites": grouped_sprites, "durations": anim["durations"]}

    def generate_json(self):
        json_data = self._get_data_from_current_view()
        if json_data:
            folder_name = os.path.basename(self.anim_folder) + "AnimationData"
            output_folder = os.path.join(self.anim_folder, folder_name)
            os.makedirs(output_folder, exist_ok=True)
            output_path = os.path.join(output_folder, f"{json_data['name']}-AnimData.json")
            with open(output_path, 'w') as f: json.dump(json_data, f, indent=4)
            messagebox.showinfo("Success", f"JSON saved for {json_data['name']} in:\n{output_path}")

    def save_all_animations(self):
        saved_count, generated_count, failed_count = 0, 0, 0
        folder_name = os.path.basename(self.anim_folder) + "AnimationData"
        output_folder = os.path.join(self.anim_folder, folder_name)
        os.makedirs(output_folder, exist_ok=True)
        for index, anim in enumerate(self.anim_data):
            json_data, was_generated = None, False
            if index == self.current_anim_index: json_data = self._get_data_from_current_view()
            else:
                json_data = self.load_json_data(anim['name'])
                if not json_data:
                    json_data = self._generate_headless_data(index)
                    if json_data: was_generated = True
            if json_data:
                output_path = os.path.join(output_folder, f"{anim['name']}-AnimData.json")
                try:
                    with open(output_path, 'w') as f: json.dump(json_data, f, indent=4)
                    saved_count += 1
                    if was_generated: generated_count +=1
                except Exception as e: print(f"Failed to write file for {anim['name']}: {e}"); failed_count += 1
            else: failed_count += 1
        messagebox.showinfo("Batch Save Complete", f"Process finished.\n\nTotal Files Saved: {saved_count}\nNewly Generated: {generated_count}\nFailed/Skipped: {failed_count}")

    def load_json_data(self, anim_name):
        folder_name = os.path.basename(self.anim_folder) + "AnimationData"
        json_path = os.path.join(self.anim_folder, folder_name, f"{anim_name}-AnimData.json")
        if not os.path.exists(json_path): return None
        try:
            with open(json_path, 'r') as f: return json.load(f)
        except Exception as e: print(f"Error loading JSON for {anim_name}: {str(e)}"); return None