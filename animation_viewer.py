import os
import json
from tkinter import Frame, Label, Canvas, Scrollbar, Entry, messagebox, Toplevel, BooleanVar, Checkbutton, OptionMenu, StringVar, Button, TclError
from PIL import Image, ImageTk
import xml.etree.ElementTree as ET
from sprite_sheet_handler import SpriteSheetHandler
import math
from sprite_matcher import SpriteMatcher

class AnimationViewer:
    def __init__(self, parent_frame, anim_folder):
        self.parent_frame = parent_frame
        self.anim_folder = anim_folder
        self.sprite_folder = os.path.join(anim_folder, "sprite")
        self.anim_data = self.load_anim_data()
        self.current_anim_index = 0
        self.after_ids = []
        self.current_sprites_entries = []  # Store sprite inputs
        self.group_widgets = {}  # Store widgets for each group
        self.linked_groups = {}  # Store relationships between groups {current_group: source_group}
        
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
                    anim_data = {
                        "name": anim_name,
                        "frame_width": int(source_anim_xml.find("FrameWidth").text),
                        "frame_height": int(source_anim_xml.find("FrameHeight").text),
                        "durations": [int(d.text) for d in source_anim_xml.findall("Durations/Duration")],
                        "image_path": os.path.join(self.sprite_folder, f"{anim_name}-Anim.png")
                    }
                else:
                    fw_tag = anim_xml.find("FrameWidth")
                    fh_tag = anim_xml.find("FrameHeight")
                    if fw_tag is None or fh_tag is None:
                        print(f"Warning: Animation '{anim_name}' is missing FrameWidth/FrameHeight and is not a copy. Skipping.")
                        continue
                    anim_data = {
                        "name": anim_name,
                        "frame_width": int(fw_tag.text),
                        "frame_height": int(fh_tag.text),
                        "durations": [int(d.text) for d in anim_xml.findall("Durations/Duration")],
                        "image_path": os.path.join(self.sprite_folder, f"{anim_name}-Anim.png")
                    }
                if not os.path.exists(anim_data["image_path"]):
                    print(f"Warning: Image file for animation '{anim_data['name']}' not found. Skipping: {anim_data['image_path']}")
                    continue
                with Image.open(anim_data["image_path"]) as img:
                    anim_data["total_groups"] = img.height // anim_data["frame_height"]
                    anim_data["frames_per_group"] = img.width // anim_data["frame_width"]
                animations.append(anim_data)
            except Exception as e:
                print(f"Error processing animation '{anim_name}': {e}. Skipping.")
                continue
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
        self.current_sprites_entries = []
        self.group_names = []
        self.group_widgets = {}
        self.linked_groups = {}
        
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        
        if not self.anim_data:
             Label(self.scroll_frame, text="No animations found or loaded.", font=('Arial', 14, 'bold')).pack(pady=20)
             return

        anim = self.anim_data[self.current_anim_index]
        handler = SpriteSheetHandler(anim["image_path"])
        all_frames = handler.split_animation_frames(anim["frame_width"], anim["frame_height"])
        
        total_groups = anim["total_groups"]
        frames_per_group = anim["frames_per_group"]
        json_data = self.load_json_data(anim["name"])
        run_ai_automatically = json_data is None

        Label(self.scroll_frame, text=f"Animation: {anim['name']}", font=('Arial', 14, 'bold')).pack(pady=10)
        
        for group_idx in range(total_groups):
            group_frame = Frame(self.scroll_frame, bd=2, relief="groove")
            group_frame.pack(fill="x", padx=5, pady=5)
            header_frame = Frame(group_frame)
            header_frame.pack(fill="x", pady=5)
            Label(header_frame, text=f"Group {group_idx + 1}", font=('Arial', 12, 'bold')).pack(side='left')
            
            group_name_entry = Entry(header_frame, width=20)
            default_name = self._get_default_group_name(anim["name"], total_groups, group_idx)
            group_name = default_name
            if json_data and "sprites" in json_data:
                group_id = str(group_idx + 1)
                group_info = json_data["sprites"].get(group_id, {})
                group_name = group_info.get("name", default_name)
            group_name_entry.insert(0, group_name)
            group_name_entry.pack(side='left', padx=10)
            self.group_names.append(group_name_entry)
            
            ai_button = Button(header_frame, text="AI Identify Sprites", command=lambda idx=group_idx: self.identify_group_sprites(idx))
            ai_button.pack(side='left', padx=10)
            
            control_frame = Frame(group_frame)
            control_frame.pack(side='right', padx=10)
            
            mirror_var, dropdown, dropdown_var = None, None, None
            if total_groups > 1:
                mirror_var = BooleanVar()
                Checkbutton(control_frame, text="mirror & copy", variable=mirror_var, command=lambda idx=group_idx: self.toggle_mirror_copy(idx)).pack()
                group_names_list = [f"Group {i+1}" for i in range(total_groups) if i != group_idx]
                dropdown_var = StringVar()
                if group_names_list:
                    dropdown_var.set(group_names_list[0])
                dropdown = OptionMenu(control_frame, dropdown_var, *group_names_list)
                dropdown.pack_forget()
                dropdown_var.trace_add("write", lambda *args, idx=group_idx: self.update_linked_group(idx))
            
            self.group_widgets[group_idx] = {"mirror_var": mirror_var, "dropdown": dropdown, "dropdown_var": dropdown_var, "ai_button": ai_button, "entries": [], "frame": None}
            
            content_frame = Frame(group_frame)
            content_frame.pack(fill="x")
            anim_panel = Frame(content_frame)
            anim_panel.pack(side="left", padx=10)
            frames_panel = Frame(content_frame)
            frames_panel.pack(side="right", fill="x", expand=True)
            self.group_widgets[group_idx]["frame"] = frames_panel
            
            start = group_idx * frames_per_group
            end = start + frames_per_group
            group_frames = all_frames[start:end]
            durations = anim["durations"] * (len(group_frames) // len(anim["durations"]) + 1)
            
            anim_label = Label(anim_panel)
            anim_label.pack()
            self.start_group_animation(anim_label, group_frames, durations[:len(group_frames)])
            
            group_entries = []
            for idx, frame in enumerate(group_frames):
                frame.thumbnail((80, 80))
                img = ImageTk.PhotoImage(frame)
                lbl = Label(frames_panel, image=img)
                lbl.image = img
                lbl.grid(row=0, column=idx, padx=2)
                
                entry = Entry(frames_panel, width=5)
                entry.insert(0, "0")
                if json_data and "sprites" in json_data:
                    group_id = str(group_idx + 1)
                    group_info = json_data["sprites"].get(group_id, {})
                    if not group_info.get("mirrored", False):
                        sprite_values = group_info.get("values", [])
                        if idx < len(sprite_values):
                            entry.delete(0, "end")
                            entry.insert(0, str(sprite_values[idx]))
                entry.grid(row=1, column=idx, padx=2)
                group_entries.append(entry)
                Label(frames_panel, text=f"Dur: {durations[idx]}", font=('Arial', 7)).grid(row=2, column=idx)
            
            self.group_widgets[group_idx]["entries"] = group_entries
            
            is_mirrored = False
            if json_data and "sprites" in json_data:
                group_id = str(group_idx + 1)
                group_info = json_data["sprites"].get(group_id, {})
                if group_info.get("mirrored", False) and mirror_var:
                    is_mirrored = True
                    mirror_var.set(True)
                    source_group = group_info.get("copy", "1")
                    dropdown_var.set(f"Group {source_group}")
                    dropdown.pack()
                    ai_button.pack_forget()
                    for entry in group_entries:
                        entry.grid_remove()
                    self.linked_groups[group_idx] = int(source_group) - 1
            
            if run_ai_automatically and not is_mirrored:
                self.identify_group_sprites(group_idx)

    def identify_group_sprites(self, group_idx):
        try:
            anim = self.anim_data[self.current_anim_index]
            handler = SpriteSheetHandler(anim["image_path"])
            group_frames = handler.split_animation_frames(anim["frame_width"], anim["frame_height"])[group_idx * anim["frames_per_group"]:(group_idx + 1) * anim["frames_per_group"]]
            
            edited_folder = os.path.join(self.anim_folder, os.path.basename(self.anim_folder) + "Edited")
            if not os.path.exists(edited_folder):
                print(f"Warning: 'Edited' sprites folder not found. Cannot run AI identification.")
                return
            
            matcher = SpriteMatcher(edited_folder)
            matches = matcher.match_group(group_frames)
            
            for idx, match in enumerate(matches):
                if match:
                    sprite_number = int(match.split('_')[-1].split('.')[0])
                    entry = self.group_widgets[group_idx]["entries"][idx]
                    entry.delete(0, "end")
                    entry.insert(0, str(sprite_number))
        except Exception as e:
            if isinstance(e, FileNotFoundError) and "Edited sprites folder not found" in str(e):
                 print(f"Warning: 'Edited' sprites folder not found. Cannot run AI identification.")
            else:
                messagebox.showerror("Error", f"Error during identification: {str(e)}")

    def update_linked_group(self, group_idx):
        widgets = self.group_widgets.get(group_idx)
        if widgets and widgets.get("mirror_var") and widgets["mirror_var"].get():
            selected_group_name = widgets["dropdown_var"].get()
            if selected_group_name:
                selected_group = int(selected_group_name.split()[-1]) - 1
                self.linked_groups[group_idx] = selected_group

    def toggle_mirror_copy(self, group_idx):
        widgets = self.group_widgets[group_idx]
        is_mirrored = widgets["mirror_var"].get()
        widgets["dropdown"].pack() if is_mirrored else widgets["dropdown"].pack_forget()
        widgets["ai_button"].pack_forget() if is_mirrored else widgets["ai_button"].pack(side='left', padx=10)
        for entry in widgets["entries"]:
            entry.grid_remove() if is_mirrored else entry.grid()
        if is_mirrored:
            self.update_linked_group(group_idx)
        else:
            self.linked_groups.pop(group_idx, None)

    def clear_animations(self):
        for aid in self.after_ids:
            self.parent_frame.after_cancel(aid)
        self.after_ids.clear()

    def start_group_animation(self, label, frames, durations):
        current_frame = [0]
        def update():
            if not label.winfo_exists(): return
            idx = current_frame[0] % len(frames)
            frame = frames[idx]
            frame.thumbnail((200, 200))
            img = ImageTk.PhotoImage(frame)
            label.config(image=img)
            label.image = img
            delay = durations[idx] * 33
            current_frame[0] += 1
            self.after_ids.append(self.parent_frame.after(delay, update))
        update()

    def prev_animation(self):
        if self.anim_data: self.current_anim_index = (self.current_anim_index - 1) % len(self.anim_data); self.show_animation()
    def next_animation(self):
        if self.anim_data: self.current_anim_index = (self.current_anim_index + 1) % len(self.anim_data); self.show_animation()
    
    def view_sprites(self):
        edited_folder = os.path.join(self.anim_folder, os.path.basename(self.anim_folder) + "Edited")
        if not os.path.exists(edited_folder): messagebox.showwarning("Warning", "No edited sprites folder found"); return
        sprite_files = sorted([f for f in os.listdir(edited_folder) if f.lower().endswith('.png')], key=lambda x: int(x.split('_')[-1].split('.')[0]))
        if not sprite_files: messagebox.showwarning("Warning", "No sprites found in edited folder"); return
        
        num_sprites = len(sprite_files)
        grid_size = math.ceil(math.sqrt(num_sprites))
        sprite_window = Toplevel(self.parent_frame)
        sprite_window.title(f"Sprites Gallery ({num_sprites} sprites)")
        canvas = Canvas(sprite_window)
        scrollbar = Scrollbar(sprite_window, orient="vertical", command=canvas.yview)
        scroll_frame = Frame(canvas)
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        for idx, file in enumerate(sprite_files):
            try:
                sprite_number = int(file.split('_')[-1].split('.')[0])
                row, col = (sprite_number - 1) // grid_size, (sprite_number - 1) % grid_size
                img = Image.open(os.path.join(edited_folder, file))
                img.thumbnail((100, 100))
                photo = ImageTk.PhotoImage(img)
                frame = Frame(scroll_frame)
                frame.grid(row=row, column=col, padx=5, pady=5)
                Label(frame, image=photo).pack()
                Label(frame, text=file, font=('Arial', 8)).pack()
                frame.photo = photo
            except Exception as e:
                print(f"Error loading {file}: {str(e)}")

    def _get_data_from_current_view(self):
        """Gathers JSON data from the currently displayed UI widgets."""
        try:
            group_names = [entry.get().strip() for entry in self.group_names]
            if any(not name for name in group_names): messagebox.showerror("Error", "All group names must be filled."); return None
            if len(group_names) != len(set(group_names)): messagebox.showerror("Error", "Duplicate group names are not allowed."); return None
            
            anim = self.anim_data[self.current_anim_index]
            grouped_sprites = {}
            for group_idx, group_name in enumerate(group_names):
                mirrored = group_idx in self.linked_groups
                group_entry = {"name": group_name, "mirrored": mirrored}
                if mirrored:
                    group_entry["copy"] = str(self.linked_groups[group_idx] + 1)
                else:
                    values = []
                    for entry in self.group_widgets[group_idx]["entries"]:
                        try: values.append(int(entry.get()))
                        except (ValueError, TclError): values.append(0)
                    group_entry["values"] = values
                grouped_sprites[str(group_idx + 1)] = group_entry
            
            return {
                "index": self.current_anim_index, "name": anim["name"],
                "framewidth": anim["frame_width"], "frameheight": anim["frame_height"],
                "sprites": grouped_sprites, "durations": anim["durations"]
            }
        except Exception as e:
            messagebox.showerror("Error", f"Failed to gather data from view: {str(e)}")
            return None

    def _generate_headless_data(self, index):
        """Generates JSON data for an animation not currently in view, using defaults and AI."""
        anim = self.anim_data[index]
        json_data = self.load_json_data(anim['name'])
        if json_data: return json_data # Return existing data if found

        print(f"Generating default data for '{anim['name']}'...")
        grouped_sprites = {}
        try:
            edited_folder = os.path.join(self.anim_folder, os.path.basename(self.anim_folder) + "Edited")
            matcher = SpriteMatcher(edited_folder) if os.path.exists(edited_folder) else None
            handler = SpriteSheetHandler(anim["image_path"])
            all_frames = handler.split_animation_frames(anim["frame_width"], anim["frame_height"])

            for group_idx in range(anim["total_groups"]):
                group_name = self._get_default_group_name(anim["name"], anim["total_groups"], group_idx)
                group_entry = {"name": group_name, "mirrored": False}
                
                values = [0] * anim["frames_per_group"]
                if matcher:
                    start, end = group_idx * anim["frames_per_group"], (group_idx + 1) * anim["frames_per_group"]
                    matches = matcher.match_group(all_frames[start:end])
                    for i, match in enumerate(matches):
                        if match: values[i] = int(match.split('_')[-1].split('.')[0])
                
                group_entry["values"] = values
                grouped_sprites[str(group_idx + 1)] = group_entry
        except Exception as e:
            print(f"Could not auto-generate data for '{anim['name']}': {e}")
            return None # Fail gracefully for this animation

        return {
            "index": index, "name": anim["name"],
            "framewidth": anim["frame_width"], "frameheight": anim["frame_height"],
            "sprites": grouped_sprites, "durations": anim["durations"]
        }

    def generate_json(self):
        """Saves the JSON for the single, currently viewed animation."""
        json_data = self._get_data_from_current_view()
        if json_data:
            anim_name = json_data["name"]
            folder_name = os.path.basename(self.anim_folder) + "AnimationData"
            output_folder = os.path.join(self.anim_folder, folder_name)
            os.makedirs(output_folder, exist_ok=True)
            output_path = os.path.join(output_folder, f"{anim_name}-AnimData.json")
            with open(output_path, 'w') as f:
                json.dump(json_data, f, indent=4)
            messagebox.showinfo("Success", f"JSON saved for {anim_name} in:\n{output_path}")

    def save_all_animations(self):
        """Saves JSON files for all animations, generating defaults if they don't exist."""
        saved_count = 0
        generated_count = 0
        failed_count = 0
        
        folder_name = os.path.basename(self.anim_folder) + "AnimationData"
        output_folder = os.path.join(self.anim_folder, folder_name)
        os.makedirs(output_folder, exist_ok=True)

        for index, anim in enumerate(self.anim_data):
            json_data = None
            was_generated = False
            
            if index == self.current_anim_index:
                json_data = self._get_data_from_current_view()
            else:
                # Check if data exists before generating new
                existing_data = self.load_json_data(anim['name'])
                if existing_data:
                    json_data = existing_data
                else:
                    json_data = self._generate_headless_data(index)
                    if json_data: was_generated = True
            
            if json_data:
                output_path = os.path.join(output_folder, f"{anim['name']}-AnimData.json")
                try:
                    with open(output_path, 'w') as f:
                        json.dump(json_data, f, indent=4)
                    saved_count += 1
                    if was_generated: generated_count +=1
                except Exception as e:
                    print(f"Failed to write file for {anim['name']}: {e}")
                    failed_count += 1
            else:
                failed_count += 1

        messagebox.showinfo("Batch Save Complete", 
                            f"Process finished.\n\n"
                            f"Total Files Saved: {saved_count}\n"
                            f"Newly Generated: {generated_count}\n"
                            f"Failed/Skipped: {failed_count}")

    def is_group_mirrored(self, entry):
        for widgets in self.group_widgets.values():
            if entry in widgets["entries"]:
                mirror_var = widgets.get("mirror_var")
                return mirror_var.get() if mirror_var else False
        return False

    def load_json_data(self, anim_name):
        folder_name = os.path.basename(self.anim_folder) + "AnimationData"
        json_path = os.path.join(self.anim_folder, folder_name, f"{anim_name}-AnimData.json")
        if not os.path.exists(json_path): return None
        try:
            with open(json_path, 'r') as f: return json.load(f)
        except Exception as e:
            print(f"Error loading JSON for {anim_name}: {str(e)}")
            return None