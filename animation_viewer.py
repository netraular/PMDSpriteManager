# animation_viewer.py

import os
import json
from tkinter import Frame, Label, Canvas, Scrollbar, messagebox, Toplevel, Button
from PIL import Image, ImageTk
import xml.etree.ElementTree as ET
from sprite_sheet_handler import SpriteSheetHandler
import math
from sprite_matcher import SpriteMatcher
from animation_group_ui import AnimationGroupUI

class AnimationViewer:
    def __init__(self, parent_frame, anim_folder):
        self.parent_frame = parent_frame
        self.anim_folder = anim_folder
        self.sprite_folder = os.path.join(anim_folder, "Sprites")
        self.anim_data = self.load_anim_data()
        self.current_anim_index = 0
        self.group_ui_instances = []
        
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
        anim_data_path = os.path.join(self.anim_folder, "Animations", "AnimData.xml")
        if not os.path.exists(anim_data_path):
            raise FileNotFoundError(f"XML file not found in: {self.anim_folder}/Animations")
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
                    if source_name not in xml_anims_map: continue
                    source_anim_xml = xml_anims_map[source_name]
                    anim_data = {"name": anim_name, "frame_width": int(source_anim_xml.find("FrameWidth").text), "frame_height": int(source_anim_xml.find("FrameHeight").text), "durations": [int(d.text) for d in source_anim_xml.findall("Durations/Duration")], "image_path": os.path.join(self.anim_folder, "Animations", f"{anim_name}-Anim.png")}
                else:
                    fw_tag, fh_tag = anim_xml.find("FrameWidth"), anim_xml.find("FrameHeight")
                    if fw_tag is None or fh_tag is None: continue
                    anim_data = {"name": anim_name, "frame_width": int(fw_tag.text), "frame_height": int(fh_tag.text), "durations": [int(d.text) for d in anim_xml.findall("Durations/Duration")], "image_path": os.path.join(self.anim_folder, "Animations", f"{anim_name}-Anim.png")}
                if not os.path.exists(anim_data["image_path"]): continue
                with Image.open(anim_data["image_path"]) as img:
                    anim_data["total_groups"] = img.height // anim_data["frame_height"]
                    anim_data["frames_per_group"] = img.width // anim_data["frame_width"]
                animations.append(anim_data)
            except Exception as e:
                print(f"Error processing animation '{anim_name}': {e}. Skipping.")
        return animations

    def show_animation(self):
        self.clear_animations()
        for widget in self.scroll_frame.winfo_children(): widget.destroy()
        if not self.anim_data:
             Label(self.scroll_frame, text="No animations found or loaded.", font=('Arial', 14, 'bold')).pack(pady=20); return
        
        anim = self.anim_data[self.current_anim_index]
        
        all_frames, all_offsets_frames, all_metadata = self._load_animation_assets(anim)
        
        json_data = self.load_json_data(anim["name"])
        run_ai_automatically = json_data is None

        Label(self.scroll_frame, text=f"Animation: {anim['name']}", font=('Arial', 14, 'bold')).pack(pady=10)
        
        for group_idx in range(anim["total_groups"]):
            start, end = group_idx * anim["frames_per_group"], (group_idx + 1) * anim["frames_per_group"]
            
            group_ui = AnimationGroupUI(
                parent=self.scroll_frame,
                group_idx=group_idx,
                anim_data=anim,
                group_frames=all_frames[start:end],
                group_offsets_frames=all_offsets_frames[start:end] if all_offsets_frames else [],
                group_metadata=all_metadata[start:end],
                sprite_folder=self.sprite_folder,
                json_group_data=json_data["sprites"].get(str(group_idx + 1)) if json_data else None,
                ai_callback=self.identify_group_sprites
            )
            self.group_ui_instances.append(group_ui)

            if run_ai_automatically:
                self.identify_group_sprites(group_ui)

    def _load_animation_assets(self, anim):
        handler = SpriteSheetHandler(anim["image_path"])
        all_frames = handler.split_animation_frames(anim["frame_width"], anim["frame_height"])
        
        all_offsets_frames = []
        all_metadata = []
        offsets_image_path = anim["image_path"].replace("-Anim.png", "-Offsets.png")
        if os.path.exists(offsets_image_path):
            offsets_handler = SpriteSheetHandler(offsets_image_path)
            all_offsets_frames = offsets_handler.split_animation_frames(anim["frame_width"], anim["frame_height"])
            all_metadata = [self._get_frame_metadata(f) for f in all_offsets_frames]
        else:
            default_anchor = (anim["frame_width"] // 2, anim["frame_height"] // 2)
            num_frames = anim["total_groups"] * anim["frames_per_group"]
            all_metadata = [{"anchors": {"black": default_anchor}}] * num_frames
            
        return all_frames, all_offsets_frames, all_metadata

    def _get_frame_metadata(self, frame_image):
        if frame_image.mode != 'RGBA': frame_image = frame_image.convert('RGBA')
        width, height = frame_image.size; pixels = frame_image.load()
        anchor_colors = {"black": (0, 0, 0, 255), "red": (255, 0, 0, 255), "green": (0, 255, 0, 255), "blue": (0, 0, 255, 255)}
        found_anchors = {color: None for color in anchor_colors}
        for x in range(width):
            for y in range(height):
                for color_name, color_value in anchor_colors.items():
                    if pixels[x, y] == color_value: found_anchors[color_name] = (x, y)
        if found_anchors["black"] is None: found_anchors["black"] = (width // 2, height // 2)
        return {"anchors": found_anchors}

    def identify_group_sprites(self, group_ui_instance):
        try:
            if not os.path.exists(self.sprite_folder): return
            matcher = SpriteMatcher(self.sprite_folder)
            match_data = matcher.match_group(group_ui_instance.group_frames)
            group_ui_instance.set_sprite_values(match_data["frame_matches"], match_data["per_frame_mirror"])
            group_ui_instance.load_result_animation()
            group_ui_instance.load_overlay_animation()
        except Exception as e:
            messagebox.showerror("Error", f"Error during identification: {str(e)}")

    def clear_animations(self):
        for instance in self.group_ui_instances:
            instance.cleanup()
        self.group_ui_instances.clear()

    def prev_animation(self):
        if self.anim_data: self.current_anim_index = (self.current_anim_index - 1) % len(self.anim_data); self.show_animation()
    def next_animation(self):
        if self.anim_data: self.current_anim_index = (self.current_anim_index + 1) % len(self.anim_data); self.show_animation()
    
    def view_sprites(self):
        if not os.path.exists(self.sprite_folder): messagebox.showwarning("Warning", "No 'Sprites' folder found"); return
        sprite_files = sorted([f for f in os.listdir(self.sprite_folder) if f.lower().endswith('.png')], key=lambda x: int(x.split('_')[-1].split('.')[0]))
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
                img = Image.open(os.path.join(self.sprite_folder, file)); img.thumbnail((100, 100)); photo = ImageTk.PhotoImage(img)
                frame = Frame(scroll_frame); frame.grid(row=row, column=col, padx=5, pady=5)
                Label(frame, image=photo).pack(); Label(frame, text=file, font=('Arial', 8)).pack(); frame.photo = photo
            except Exception as e: print(f"Error loading {file}: {str(e)}")

    def _get_data_from_current_view(self):
        try:
            anim = self.anim_data[self.current_anim_index]
            grouped_sprites = {}
            group_names = []
            for i, instance in enumerate(self.group_ui_instances):
                group_data = instance.get_data()
                group_name = group_data["name"]
                if not group_name: messagebox.showerror("Error", "All group names must be filled."); return None
                if group_name in group_names: messagebox.showerror("Error", "Duplicate group names are not allowed."); return None
                group_names.append(group_name)
                grouped_sprites[str(i + 1)] = group_data
            
            return {"index": self.current_anim_index, "name": anim["name"], "framewidth": anim["frame_width"], "frameheight": anim["frame_height"], "sprites": grouped_sprites, "durations": anim["durations"]}
        except Exception as e: messagebox.showerror("Error", f"Failed to gather data from view: {str(e)}"); return None

    def _generate_headless_data(self, index):
        anim = self.anim_data[index]
        json_data = self.load_json_data(anim['name'])
        if json_data: return json_data
        
        all_frames, all_offsets_frames, all_metadata = self._load_animation_assets(anim)
        
        grouped_sprites = {}
        try:
            matcher = SpriteMatcher(self.sprite_folder) if os.path.exists(self.sprite_folder) else None
            for group_idx in range(anim["total_groups"]):
                start, end = group_idx * anim["frames_per_group"], (group_idx + 1) * anim["frames_per_group"]
                
                values = []
                if matcher:
                    match_data = matcher.match_group(all_frames[start:end])
                    values = [{"id": sid, "mirrored": m} for sid, m in zip(match_data["frame_matches"], match_data["per_frame_mirror"])]
                else:
                    values = [{"id": 0, "mirrored": False}] * anim["frames_per_group"]
                
                group_metadata = all_metadata[start:end]
                offsets = [m['anchors']['black'] for m in group_metadata]
                
                group_ui_for_name = AnimationGroupUI(self.scroll_frame, group_idx, anim, [], [], [], "", {}, lambda s: None)
                group_name = group_ui_for_name._get_default_group_name()
                group_ui_for_name.cleanup()

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