# animation_viewer.py

import os
import json
from tkinter import Frame, Label, Canvas, Scrollbar, messagebox, Toplevel, Button, OptionMenu, StringVar
from PIL import Image, ImageTk, ImageOps
import math
from animation_group_ui import AnimationGroupUI
from animation_data_handler import AnimationDataHandler

class AnimationViewer:
    def __init__(self, parent_frame, anim_folder):
        self.parent_frame = parent_frame
        self.anim_folder = anim_folder
        self.sprite_folder = os.path.join(anim_folder, "Sprites")
        
        self.data_handler = AnimationDataHandler(self.anim_folder)
        self.anim_data = self.data_handler.anim_data
        
        self.current_anim_index = 0
        self.group_ui_instances = []
        
        self.selected_anim_var = StringVar()

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

    def on_animation_selected(self, selected_name):
        new_index = -1
        for i, anim in enumerate(self.anim_data):
            if anim['name'] == selected_name:
                new_index = i
                break
        
        if new_index != -1 and new_index != self.current_anim_index:
            self.current_anim_index = new_index
            self.show_animation()

    def show_animation(self):
        self.clear_animations()
        for widget in self.scroll_frame.winfo_children(): widget.destroy()
        if not self.anim_data:
             Label(self.scroll_frame, text="No animations found or loaded.", font=('Arial', 14, 'bold')).pack(pady=20); return
        
        anim = self.anim_data[self.current_anim_index]
        
        all_frames, all_offsets_frames, all_metadata = self.data_handler._load_animation_assets(anim)
        
        ui_compatible_json_data = self.load_and_convert_optimized_json(anim["name"])
        run_ai_automatically = ui_compatible_json_data is None

        header_frame = Frame(self.scroll_frame)
        header_frame.pack(fill='x', pady=10)
        
        Label(header_frame, text="Animation:", font=('Arial', 14, 'bold')).pack(side='left', padx=(10, 5))
        anim_names = [a['name'] for a in self.anim_data]
        self.selected_anim_var.set(anim['name'])
        anim_dropdown = OptionMenu(header_frame, self.selected_anim_var, *anim_names, command=self.on_animation_selected)
        anim_dropdown.config(font=('Arial', 12))
        anim_dropdown.pack(side='left', padx=5)

        count_text = f"({self.current_anim_index + 1} of {len(self.anim_data)})"
        Label(header_frame, text=count_text, font=('Arial', 12, 'italic')).pack(side='left', padx=10)

        for group_idx in range(anim["total_groups"]):
            start, end = group_idx * anim["frames_per_group"], (group_idx + 1) * anim["frames_per_group"]
            
            group_ui = AnimationGroupUI(
                parent=self.scroll_frame,
                viewer=self,
                group_idx=group_idx,
                anim_data=anim,
                group_frames=all_frames[start:end],
                group_offsets_frames=all_offsets_frames[start:end] if all_offsets_frames else [],
                group_metadata=all_metadata[start:end],
                sprite_folder=self.sprite_folder,
                json_group_data=ui_compatible_json_data["sprites"].get(str(group_idx + 1)) if ui_compatible_json_data else None,
                ai_callback=self.identify_group_sprites
            )
            self.group_ui_instances.append(group_ui)

            if run_ai_automatically:
                self.identify_group_sprites(group_ui)

    def get_animation_bounds(self):
        min_x, min_y, max_x, max_y = float('inf'), float('inf'), float('-inf'), float('-inf')
        has_visible_sprites = False

        all_frames_data = []
        for instance in self.group_ui_instances:
            group_data = instance.get_data()
            offsets = group_data.get('offsets', [])
            for i, value in enumerate(group_data.get('values', [])):
                if i < len(offsets):
                    all_frames_data.append({
                        "id": value.get('id', 0),
                        "offset": offsets[i]
                    })

        for frame_data in all_frames_data:
            sprite_id = frame_data["id"]
            if sprite_id == 0:
                continue

            try:
                source_path = os.path.join(self.sprite_folder, f"sprite_{sprite_id}.png")
                with Image.open(source_path) as img:
                    sprite_w, sprite_h = img.size
                
                has_visible_sprites = True
                ox, oy = frame_data["offset"]
                
                x0 = ox - sprite_w / 2
                y0 = oy - sprite_h / 2
                x1 = ox + sprite_w / 2
                y1 = oy + sprite_h / 2
                
                min_x = min(min_x, x0)
                min_y = min(min_y, y0)
                max_x = max(max_x, x1)
                max_y = max(max_y, y1)

            except FileNotFoundError:
                continue
        
        if not has_visible_sprites:
            anim = self.anim_data[self.current_anim_index]
            w, h = anim["frame_width"], anim["frame_height"]
            return (0, 0, w, h)

        return (min_x, min_y, max_x, max_y)

    def identify_group_sprites(self, group_ui_instance):
        try:
            if not os.path.exists(self.sprite_folder): return
            from sprite_matcher import SpriteMatcher
            matcher = SpriteMatcher(self.sprite_folder)
            match_data = matcher.match_group(group_ui_instance.group_frames)
            group_ui_instance.set_sprite_values(match_data["frame_matches"], match_data["per_frame_mirror"])
            group_ui_instance.refresh_all_previews()
        except Exception as e:
            messagebox.showerror("Error", f"Error during identification: {str(e)}")

    def clear_animations(self):
        for instance in self.group_ui_instances:
            instance.cleanup()
        self.group_ui_instances.clear()

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

    def generate_json(self):
        json_data = self._get_data_from_current_view()
        if json_data:
            output_path, error = self.data_handler.export_optimized_animation(json_data)
            if error:
                messagebox.showerror("Export Error", error)
            else:
                messagebox.showinfo("Success", f"Optimized animation saved for {json_data['name']} in:\n{os.path.dirname(output_path)}")

    def save_all_animations(self):
        saved_count, failed_count = 0, 0
        
        for index, anim in enumerate(self.anim_data):
            json_data = None
            if index == self.current_anim_index:
                json_data = self._get_data_from_current_view()
            else:
                json_data = self.data_handler.generate_animation_data(index)

            if json_data:
                _, error = self.data_handler.export_optimized_animation(json_data)
                if error:
                    print(f"Failed to export {anim['name']}: {error}")
                    failed_count += 1
                else:
                    saved_count += 1
            else:
                failed_count += 1
        
        messagebox.showinfo("Batch Export Complete", f"Process finished.\n\nTotal Animations Exported: {saved_count}\nFailed/Skipped: {failed_count}")

    def load_and_convert_optimized_json(self, anim_name):
        folder_name = "AnimationData"
        json_path = os.path.join(self.anim_folder, folder_name, f"{anim_name}-AnimData.json")
        if not os.path.exists(json_path): return None
        try:
            with open(json_path, 'r') as f: optimized_data = json.load(f)
        except Exception as e:
            print(f"Error loading optimized JSON for {anim_name}: {str(e)}"); return None
        
        ui_data = optimized_data.copy()
        ui_data['sprites'] = {}
        for group_id, group_data in optimized_data.get('sprites', {}).items():
            ui_group = {'name': group_data.get('name'), 'values': [], 'offsets': []}
            for frame in group_data.get('frames', []):
                sprite_id_str = frame.get('id', '0')
                offset = frame.get('offset', [0, 0])
                is_mirrored = "_mirrored" in sprite_id_str
                base_id = int(sprite_id_str.replace("_mirrored", "")) if sprite_id_str.replace("_mirrored", "").isdigit() else 0
                ui_group['values'].append({'id': base_id, 'mirrored': is_mirrored})
                ui_group['offsets'].append(offset)
            ui_data['sprites'][group_id] = ui_group
        return ui_data