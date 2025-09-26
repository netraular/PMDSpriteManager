# isometric_animation_previewer.py

import os
import json
from tkinter import Frame, Label, Button, Canvas, messagebox, OptionMenu, StringVar, Entry
from PIL import Image, ImageTk, ImageDraw
from ui_components.animation_player import AnimationPlayer
from ui_components import isometric_renderer

class IsometricAnimationPreviewer:
    def __init__(self, parent_frame, parent_folder, return_to_main_callback, update_breadcrumbs_callback=None, base_path=None):
        self.parent_frame = parent_frame
        self.output_folder_1x = os.path.join(parent_folder, "output")
        self.output_folder_2x = os.path.join(parent_folder, "output x2")
        self.return_to_main = return_to_main_callback
        self.update_breadcrumbs = update_breadcrumbs_callback
        self.base_path = base_path if base_path is not None else []
        
        self.main_frame = Frame(self.parent_frame)
        self.main_frame.pack(fill='both', expand=True)
        
        self.player_1x = None
        self.player_2x = None

        self.selected_char_var = StringVar()
        self.selected_anim_var = StringVar()
        self.trace_id = None 

        self.setup_ui()

    def setup_ui(self):
        if self.update_breadcrumbs:
            path = self.base_path + [("Isometric Preview", self.setup_ui)]
            self.update_breadcrumbs(path)

        self.clear_frame()
        if not os.path.exists(self.output_folder_1x) and not os.path.exists(self.output_folder_2x):
            messagebox.showerror("Error", "Neither 'output' nor 'output x2' folders exist.\nPlease run an export task first.")
            self.return_to_main()
            return
        
        self._setup_main_ui()

    def _setup_main_ui(self):
        top_control_frame = Frame(self.main_frame); top_control_frame.pack(fill='x', padx=10, pady=5)
        Button(top_control_frame, text="Back to Tasks", command=self.return_to_main).pack(side='left', padx=(0, 20))

        Label(top_control_frame, text="Character:").pack(side='left', padx=(10, 5))
        
        search_folder = self.output_folder_1x if os.path.exists(self.output_folder_1x) else self.output_folder_2x
        characters = sorted([d for d in os.listdir(search_folder) if os.path.isdir(os.path.join(search_folder, d))])
        
        if not characters:
            Label(self.main_frame, text="No characters found in 'output' or 'output x2' folder.", fg="red").pack(pady=50)
            return
        
        self.char_dropdown = OptionMenu(top_control_frame, self.selected_char_var, *characters, command=self._on_character_selected)
        self.char_dropdown.pack(side='left')

        Label(top_control_frame, text="Animation:").pack(side='left', padx=(20, 5))
        self.trace_id = self.selected_anim_var.trace_add("write", self._on_animation_selected)
        self.anim_dropdown = OptionMenu(top_control_frame, self.selected_anim_var, "None")
        self.anim_dropdown.pack(side='left')

        preview_container = Frame(self.main_frame); preview_container.pack(fill='both', expand=True, pady=10)
        preview_container.grid_columnconfigure(0, weight=1); preview_container.grid_columnconfigure(1, weight=1)

        # Setup 1x Player
        frame_1x = Frame(preview_container); frame_1x.grid(row=0, column=0, padx=10, sticky="nsew")
        Label(frame_1x, text="1x Scale (output)", font=('Arial', 12, 'bold')).pack()
        label_1x = Label(frame_1x); label_1x.pack(expand=True)
        text_1x = Label(frame_1x, justify="left"); text_1x.pack(pady=(5,0))
        self.player_1x = AnimationPlayer(self.main_frame, label_1x, text_1x)
        
        # Setup 2x Player
        frame_2x = Frame(preview_container); frame_2x.grid(row=0, column=1, padx=10, sticky="nsew")
        Label(frame_2x, text="2x Scale (output x2)", font=('Arial', 12, 'bold')).pack()
        label_2x = Label(frame_2x); label_2x.pack(expand=True)
        text_2x = Label(frame_2x, justify="left"); text_2x.pack(pady=(5,0))
        self.player_2x = AnimationPlayer(self.main_frame, label_2x, text_2x)

        self.selected_char_var.set(characters[0])
        self._on_character_selected(characters[0])

    def _on_character_selected(self, char_name):
        if self.trace_id:
            self.selected_anim_var.trace_remove("write", self.trace_id)
        
        char_path_1x = os.path.join(self.output_folder_1x, char_name)
        char_path_2x = os.path.join(self.output_folder_2x, char_name)
        
        anim_names = set()
        if os.path.exists(char_path_1x):
            files = [f.replace("-AnimData.json", "") for f in os.listdir(char_path_1x) if f.lower().endswith('-animdata.json')]
            anim_names.update(files)
        if os.path.exists(char_path_2x):
            files = [f.replace("-AnimData.json", "") for f in os.listdir(char_path_2x) if f.lower().endswith('-animdata.json')]
            anim_names.update(files)

        sorted_anim_names = sorted(list(anim_names))

        menu = self.anim_dropdown["menu"]
        menu.delete(0, "end")

        if sorted_anim_names:
            for name in sorted_anim_names:
                menu.add_command(label=name, command=lambda value=name: self.selected_anim_var.set(value))
            self.selected_anim_var.set(sorted_anim_names[0])
        else:
            self.selected_anim_var.set("None")
            self.clear_animations()

        self.trace_id = self.selected_anim_var.trace_add("write", self._on_animation_selected)
        if not sorted_anim_names:
             self._load_and_display_animation()

    def _on_animation_selected(self, *args):
        self._load_and_display_animation()

    def _load_and_display_animation(self):
        self.clear_animations()
        
        char_name = self.selected_char_var.get()
        anim_name = self.selected_anim_var.get()

        if not char_name or not anim_name or anim_name == "None":
            return

        anim_filename = f"{anim_name}-AnimData.json"

        try:
            # Load and display 1x animation
            anim_data_1x, sprites_1x, shadow_1x = self._load_animation_data(self.output_folder_1x, char_name, anim_filename)
            if anim_data_1x:
                preview_data = isometric_renderer.generate_isometric_preview_data(anim_data_1x, sprites_1x, shadow_1x, is_2x=False)
                self.player_1x.set_animation(**preview_data)
                self.player_1x.play()
            else:
                self.player_1x.set_animation([], [], text_data=[])
                self.player_1x.image_label.config(text="No 1x data found", fg="grey")

            # Load and display 2x animation
            anim_data_2x, sprites_2x, shadow_2x = self._load_animation_data(self.output_folder_2x, char_name, anim_filename)
            if anim_data_2x:
                preview_data = isometric_renderer.generate_isometric_preview_data(anim_data_2x, sprites_2x, shadow_2x, is_2x=True)
                self.player_2x.set_animation(**preview_data)
                self.player_2x.play()
            else:
                self.player_2x.set_animation([], [], text_data=[])
                self.player_2x.image_label.config(text="No 2x data found", fg="grey")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to start preview: {e}")

    def _load_animation_data(self, base_folder, character_name, anim_filename):
        json_path = os.path.join(base_folder, character_name, anim_filename)
        if not os.path.exists(json_path): return None, None, None
        
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        sprite_folder = os.path.join(base_folder, character_name, data['name'])
        sprite_map = isometric_renderer.load_sprites_from_json(data, sprite_folder)
        
        shadow_sprite = None
        shadow_path = os.path.join(base_folder, character_name, "sprite_base.png")
        if os.path.exists(shadow_path):
            try:
                shadow_sprite = Image.open(shadow_path).convert('RGBA')
            except Exception as e:
                print(f"Warning: Could not load shadow sprite at {shadow_path}: {e}")

        return data, sprite_map, shadow_sprite

    def clear_animations(self):
        if self.player_1x: self.player_1x.stop()
        if self.player_2x: self.player_2x.stop()

    def clear_frame(self):
        self.clear_animations()
        if self.trace_id:
            try:
                self.selected_anim_var.trace_remove("write", self.trace_id)
            except Exception:
                pass
        for widget in self.main_frame.winfo_children():
            widget.destroy()