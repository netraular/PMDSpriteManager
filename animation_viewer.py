import os
import json
from tkinter import Frame, Label, Canvas, Scrollbar, Entry, messagebox, Toplevel, BooleanVar, Checkbutton, OptionMenu, StringVar, Button
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

        # Step 1: Create a map of all animations by name for quick lookups.
        # This allows us to find the "Attack" animation when processing "Strike".
        xml_anims_map = {anim.find('Name').text: anim for anim in anims_root.findall('Anim')}

        # Step 2: Iterate over each animation and process it.
        for anim_name, anim_xml in xml_anims_map.items():
            copy_of_tag = anim_xml.find('CopyOf')
            anim_data = {}

            try:
                if copy_of_tag is not None:
                    # This is a copied animation.
                    source_name = copy_of_tag.text
                    if source_name not in xml_anims_map:
                        print(f"Warning: Source animation '{source_name}' for '{anim_name}' not found. Skipping.")
                        continue
                    
                    # Get the data from the source animation's XML.
                    source_anim_xml = xml_anims_map[source_name]
                    anim_data = {
                        "name": anim_name,
                        "frame_width": int(source_anim_xml.find("FrameWidth").text),
                        "frame_height": int(source_anim_xml.find("FrameHeight").text),
                        "durations": [int(d.text) for d in source_anim_xml.findall("Durations/Duration")],
                        "image_path": os.path.join(self.sprite_folder, f"{anim_name}-Anim.png")
                    }
                else:
                    # This is a normal animation.
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

                # Common processing for both animation types
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
        """
        Determines the default group name based on the total number of groups.
        """
        # Names for animations with 8 directions
        DIRECTIONAL_NAMES_8 = (
            "down", "down-right", "right", "up-right",
            "up", "up-left", "left", "down-left"
        )
        
        # Condition 1: If there are exactly 8 groups, use directional names.
        if total_groups == 8:
            # Ensure the index is within the expected range
            if 0 <= group_idx < len(DIRECTIONAL_NAMES_8):
                return DIRECTIONAL_NAMES_8[group_idx]

        # Condition 2: If there is only 1 group, use the animation name in lowercase.
        elif total_groups == 1:
            return anim_name.lower()

        # Default case: For any other number of groups, use "groupX".
        return f"group{group_idx + 1}"

    def show_animation(self):
        self.clear_animations()
        self.current_sprites_entries = []  # Reset inputs
        self.group_names = []  # Store group names
        self.group_widgets = {}  # Reset group widgets
        self.linked_groups = {}  # Reset group relationships
        
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        
        anim = self.anim_data[self.current_anim_index]
        handler = SpriteSheetHandler(anim["image_path"])
        all_frames = handler.split_animation_frames(anim["frame_width"], anim["frame_height"])
        
        total_groups = anim["total_groups"]
        frames_per_group = anim["frames_per_group"]
        
        # Load JSON data if it exists
        json_data = self.load_json_data(anim["name"])
        
        # >>> NEW CODE BLOCK [START] <<<
        # Set a flag to run AI automatically only if no JSON file was found
        run_ai_automatically = json_data is None
        # >>> NEW CODE BLOCK [END] <<<

        main_title = Label(self.scroll_frame, 
                        text=f"Animation: {anim['name']}",
                        font=('Arial', 14, 'bold'))
        main_title.pack(pady=10)
        
        for group_idx in range(total_groups):
            group_frame = Frame(self.scroll_frame, bd=2, relief="groove")
            group_frame.pack(fill="x", padx=5, pady=5)
            
            # Group header with name entry field
            header_frame = Frame(group_frame)
            header_frame.pack(fill="x", pady=5)
            
            Label(header_frame, 
                text=f"Group {group_idx + 1}", 
                font=('Arial', 12, 'bold')).pack(side='left')
            
            # Entry field for group name
            group_name_entry = Entry(header_frame, width=20)
            
            # 1. Get the default name using our new logic
            default_name = self._get_default_group_name(anim["name"], total_groups, group_idx)
            
            # 2. If a JSON file exists, try to load the name from there.
            #    If it's not in the JSON, fall back to our default name.
            if json_data and "sprites" in json_data:
                group_id = str(group_idx + 1)
                group_info = json_data["sprites"].get(group_id, {})
                group_name = group_info.get("name", default_name)
                group_name_entry.insert(0, group_name)
            else:
                # 3. If no JSON file exists, use our default name directly.
                group_name_entry.insert(0, default_name)

            group_name_entry.pack(side='left', padx=10)
            self.group_names.append(group_name_entry)  # Save reference
            
            # Button to automatically identify sprites
            ai_button = Button(header_frame, text="AI Identify Sprites", 
                            command=lambda idx=group_idx: self.identify_group_sprites(idx))
            ai_button.pack(side='left', padx=10)
            
            # Frame for "mirror & copy" controls
            control_frame = Frame(group_frame)
            control_frame.pack(side='right', padx=10)
            
            # Only show checkbox and dropdown if there is more than 1 group
            if total_groups > 1:
                # "mirror & copy" checkbox
                mirror_var = BooleanVar()
                Checkbutton(
                    control_frame, 
                    text="mirror & copy", 
                    variable=mirror_var,
                    command=lambda idx=group_idx: self.toggle_mirror_copy(idx)
                ).pack()
                
                # Group dropdown (initially hidden)
                group_names_list = [f"Group {i+1}" for i in range(total_groups) if i != group_idx]
                dropdown_var = StringVar()
                if group_names_list:
                    dropdown_var.set(group_names_list[0])  # Set the first group as default
                dropdown = OptionMenu(control_frame, dropdown_var, *group_names_list)
                dropdown.pack_forget()
                
                # Save references
                self.group_widgets[group_idx] = {
                    "mirror_var": mirror_var,
                    "dropdown": dropdown,
                    "dropdown_var": dropdown_var,
                    "ai_button": ai_button,  # Save button reference
                    "entries": [],
                    "frame": None
                }
                
                # Track changes in the dropdown
                dropdown_var.trace_add("write", lambda *args, idx=group_idx: self.update_linked_group(idx))
                
                # If there is JSON data, configure the checkbox and dropdown
                if json_data and "sprites" in json_data:
                    group_id = str(group_idx + 1)
                    group_info = json_data["sprites"].get(group_id, {})
                    if group_info.get("mirrored", False):
                        # Check the checkbox and select the group in the dropdown
                        mirror_var.set(True)
                        source_group = group_info.get("copy", "1")
                        dropdown_var.set(f"Group {source_group}")
                        dropdown.pack()
                        
                        # Hide inputs and AI button
                        for entry in self.group_widgets[group_idx]["entries"]:
                            entry.grid_remove()
                        ai_button.pack_forget()
                        
                        # Register group relationship
                        self.linked_groups[group_idx] = int(source_group) - 1
            else:
                # If there is only 1 group, do not show "mirror & copy" controls
                self.group_widgets[group_idx] = {
                    "mirror_var": None,
                    "dropdown": None,
                    "dropdown_var": None,
                    "ai_button": ai_button,  # Save button reference
                    "entries": [],
                    "frame": None
                }
            
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
            
            durations = anim["durations"]
            if len(durations) < len(group_frames):
                durations = durations * (len(group_frames) // len(durations) + 1)
            durations = durations[:len(group_frames)]
            
            anim_label = Label(anim_panel)
            anim_label.pack()
            self.start_group_animation(anim_label, group_frames, durations)
            
            group_entries = []
            for idx, frame in enumerate(group_frames):
                frame.thumbnail((80, 80))
                img = ImageTk.PhotoImage(frame)
                lbl = Label(frames_panel, image=img)
                lbl.image = img
                lbl.grid(row=0, column=idx, padx=2)
                
                # Entry field for sprite value
                entry = Entry(frames_panel, width=5)
                if json_data and "sprites" in json_data:
                    group_id = str(group_idx + 1)
                    group_info = json_data["sprites"].get(group_id, {})
                    if not group_info.get("mirrored", False):
                        sprite_values = group_info.get("values", [])
                        if idx < len(sprite_values):
                            entry.insert(0, str(sprite_values[idx]))  # Fill with JSON value
                else:
                    entry.insert(0, "0")  # Default value
                entry.grid(row=1, column=idx, padx=2)
                group_entries.append(entry)
                
                # Show duration from XML
                Label(frames_panel, 
                    text=f"Dur: {durations[idx]}",
                    font=('Arial', 7)).grid(row=2, column=idx)
            
            self.current_sprites_entries.extend(group_entries)
            self.group_widgets[group_idx]["entries"] = group_entries
            
            # Hide inputs if the group is marked as "mirrored" in the JSON
            if json_data and "sprites" in json_data:
                group_id = str(group_idx + 1)
                group_info = json_data["sprites"].get(group_id, {})
                if group_info.get("mirrored", False):
                    for entry in group_entries:
                        entry.grid_remove()
            
            # >>> NEW CODE BLOCK [START] <<<
            # Automatically run AI identification if no JSON data was loaded for this animation
            if run_ai_automatically:
                # We only run it for non-mirrored groups, which is the default when no JSON is loaded
                self.identify_group_sprites(group_idx)
            # >>> NEW CODE BLOCK [END] <<<


    def identify_group_sprites(self, group_idx):
        """Automatically identify sprites for a group and update the inputs."""
        try:
            anim = self.anim_data[self.current_anim_index]
            frames_per_group = anim["frames_per_group"]
            
            # Get frames from the group
            start = group_idx * frames_per_group
            end = start + frames_per_group
            handler = SpriteSheetHandler(anim["image_path"])
            group_frames = handler.split_animation_frames(anim["frame_width"], anim["frame_height"])[start:end]
            
            # Get path to edited sprites
            edited_folder = os.path.join(self.anim_folder, os.path.basename(self.anim_folder) + "Edited")
            if not os.path.exists(edited_folder):
                # Don't show a popup, just print a warning to the console as this is an automatic action
                print(f"Warning: 'Edited' sprites folder not found. Cannot run automatic AI identification.")
                return
            
            # Perform matching
            matcher = SpriteMatcher(edited_folder)
            matches = matcher.match_group(group_frames)
            
            # Get sprite numbers and update inputs
            for idx, match in enumerate(matches):
                if match:  # If a match was found
                    # Extract the number from the sprite name (sprite_1.png -> 1)
                    sprite_number = int(match.split('_')[-1].split('.')[0])
                    
                    # Get the corresponding entry field
                    entry = self.group_widgets[group_idx]["entries"][idx]
                    
                    # Clear the field and insert the sprite number
                    entry.delete(0, "end")
                    entry.insert(0, str(sprite_number))
                    
        except Exception as e:
            # We check if the error is a FileNotFoundError for the edited folder and handle it silently
            if isinstance(e, FileNotFoundError) and "Edited sprites folder not found" in str(e):
                 print(f"Warning: 'Edited' sprites folder not found. Cannot run automatic AI identification.")
            else:
                messagebox.showerror("Error", f"Error during identification: {str(e)}")


    def update_linked_group(self, group_idx):
        """Update the linked group when the dropdown selection changes."""
        widgets = self.group_widgets.get(group_idx)
        if widgets and widgets.get("mirror_var") and widgets["mirror_var"].get():
            selected_group_name = widgets["dropdown_var"].get()
            if selected_group_name:
                selected_group = int(selected_group_name.split()[-1]) - 1
                self.linked_groups[group_idx] = selected_group

    def toggle_mirror_copy(self, group_idx):
        widgets = self.group_widgets[group_idx]
        if widgets["mirror_var"].get():
            # Show dropdown and hide inputs and "AI Identify Sprites" button
            widgets["dropdown"].pack()
            for entry in widgets["entries"]:
                entry.grid_remove()
            widgets["ai_button"].pack_forget()  # Hide the button
            
            # Update linked group with current selection
            self.update_linked_group(group_idx)
        else:
            # Hide dropdown and show inputs and "AI Identify Sprites" button
            widgets["dropdown"].pack_forget()
            for entry in widgets["entries"]:
                entry.grid()
            widgets["ai_button"].pack(side='left', padx=10)  # Show the button
            self.linked_groups.pop(group_idx, None)

    def clear_animations(self):
        for aid in self.after_ids:
            self.parent_frame.after_cancel(aid)
        self.after_ids.clear()

    def start_group_animation(self, label, frames, durations):
        current_frame = [0]
        
        def update():
            if not label.winfo_exists(): # Stop if the widget was destroyed
                return
            if current_frame[0] >= len(frames):
                current_frame[0] = 0
                
            frame = frames[current_frame[0]]
            frame.thumbnail((200, 200))
            img = ImageTk.PhotoImage(frame)
            label.config(image=img)
            label.image = img
            
            delay = durations[current_frame[0]] * 33
            current_frame[0] += 1
            self.after_ids.append(self.parent_frame.after(delay, update))
        
        update()

    def prev_animation(self):
        if len(self.anim_data) > 0:
            self.current_anim_index = (self.current_anim_index - 1) % len(self.anim_data)
            self.show_animation()

    def next_animation(self):
        if len(self.anim_data) > 0:
            self.current_anim_index = (self.current_anim_index + 1) % len(self.anim_data)
            self.show_animation()

    def view_sprites(self):
        """Open window with edited sprites"""
        edited_folder = os.path.join(self.anim_folder, os.path.basename(self.anim_folder) + "Edited")
        
        if not os.path.exists(edited_folder):
            messagebox.showwarning("Warning", "No edited sprites folder found")
            return
        
        # Get list of sprite files
        sprite_files = sorted(
            [f for f in os.listdir(edited_folder) if f.lower().endswith('.png')],
            key=lambda x: int(x.split('_')[-1].split('.')[0])  # Sort by number in the name
        )
        
        if not sprite_files:
            messagebox.showwarning("Warning", "No sprites found in edited folder")
            return
        
        # Calculate grid size
        num_sprites = len(sprite_files)
        grid_size = math.ceil(math.sqrt(num_sprites))  # Square root rounded up
        
        # Create popup window
        sprite_window = Toplevel(self.parent_frame)
        sprite_window.title(f"Sprites Gallery ({num_sprites} sprites)")
        sprite_window.geometry(f"{100 * grid_size + 50}x{100 * grid_size + 50}")
        
        # Canvas with scroll (in case the grid is too large)
        canvas = Canvas(sprite_window)
        scrollbar = Scrollbar(sprite_window, orient="vertical", command=canvas.yview)
        scroll_frame = Frame(canvas)
        
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")
        ))
        
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Show sprites in grid
        for idx, file in enumerate(sprite_files):
            try:
                # Get sprite number
                sprite_number = int(file.split('_')[-1].split('.')[0])
                
                # Calculate position in the grid
                row = (sprite_number - 1) // grid_size
                col = (sprite_number - 1) % grid_size
                
                # Load and display the image
                img_path = os.path.join(edited_folder, file)
                img = Image.open(img_path)
                img.thumbnail((100, 100))
                
                photo = ImageTk.PhotoImage(img)
                frame = Frame(scroll_frame)
                frame.grid(row=row, column=col, padx=5, pady=5)
                
                Label(frame, image=photo).pack()
                Label(frame, text=file, font=('Arial', 8)).pack()
                
                # Save reference to the image to avoid garbage collection
                frame.photo = photo
                
            except Exception as e:
                print(f"Error loading {file}: {str(e)}")

    def generate_json(self):
        try:
            group_names = [entry.get().strip() for entry in self.group_names]
            
            if any(not name for name in group_names):
                messagebox.showerror("Error", "All group names must be filled.")
                return

            if len(group_names) != len(set(group_names)):
                messagebox.showerror("Error", "Duplicate group names are not allowed.")
                return
            
            # Get current values of ALL sprites (only if they are not marked as "mirrored")
            sprites = []
            all_entries = [entry for group in self.group_widgets.values() for entry in group["entries"]]
            
            for entry in all_entries:
                if not self.is_group_mirrored(entry):
                    try:
                        sprites.append(int(entry.get()))
                    except (ValueError, TclError):
                        sprites.append(0)
                else:
                    sprites.append(0)  # Default value, it won't be used
            
            anim = self.anim_data[self.current_anim_index]
            frames_per_group = anim["frames_per_group"]
            
            # Create the sprites structure with the new format
            grouped_sprites = {}
            sprite_cursor = 0
            for group_idx in range(len(self.group_names)):
                group_name = self.group_names[group_idx].get().strip()
                
                # Determine if the group is "mirrored"
                mirrored = group_idx in self.linked_groups
                
                # Create the group entry
                group_entry = {
                    "name": group_name,
                    "mirrored": mirrored
                }
                
                if mirrored:
                    # If the group is "mirrored", save the ID of the group it's copying
                    source_group_idx = self.linked_groups[group_idx]
                    group_entry["copy"] = str(source_group_idx + 1)
                else:
                    # If it's not "mirrored", save the sprite values
                    num_entries = len(self.group_widgets[group_idx]["entries"])
                    end_cursor = sprite_cursor + num_entries
                    group_entry["values"] = sprites[sprite_cursor:end_cursor]
                    sprite_cursor = end_cursor
                
                # Add the group to the sprites dictionary
                grouped_sprites[str(group_idx + 1)] = group_entry  # Use index + 1 as ID
            
            # Create JSON structure
            json_data = {
                "index": self.current_anim_index,
                "name": anim["name"],
                "framewidth": anim["frame_width"],
                "frameheight": anim["frame_height"],
                "sprites": grouped_sprites,  # New sprites format
                "durations": anim["durations"]
            }
            
            # Save file
            folder_name = os.path.basename(self.anim_folder) + "AnimationData"
            output_folder = os.path.join(self.anim_folder, folder_name)
            os.makedirs(output_folder, exist_ok=True)
            
            filename = f"{anim['name']}-AnimData.json"
            output_path = os.path.join(output_folder, filename)
            
            with open(output_path, 'w') as f:
                json.dump(json_data, f, indent=4)
            
            messagebox.showinfo("Success", f"JSON saved in:\n{output_path}")
        
        except Exception as e:
            messagebox.showerror("Error", f"Error saving: {str(e)}")

    def is_group_mirrored(self, entry):
        """
        Determines if the group to which the input field belongs is marked as "mirrored".
        """
        for group_idx, widgets in self.group_widgets.items():
            if entry in widgets["entries"]:
                mirror_var = widgets.get("mirror_var")
                return mirror_var.get() if mirror_var else False
        return False

    def load_json_data(self, anim_name):
        """Load data from JSON file if it exists."""
        folder_name = os.path.basename(self.anim_folder) + "AnimationData"
        json_path = os.path.join(self.anim_folder, folder_name, f"{anim_name}-AnimData.json")
        
        if not os.path.exists(json_path):
            return None  # JSON file does not exist
        
        try:
            with open(json_path, 'r') as f:
                return json.load(f)  # Return JSON directly without conversion
            
        except Exception as e:
            print(f"Error loading JSON: {str(e)}")
            return None