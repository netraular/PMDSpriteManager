# rpg_tile_previewer.py

import os
import json
from tkinter import Frame, Label, Button, Canvas, messagebox, OptionMenu, StringVar, Scrollbar, filedialog
from PIL import Image, ImageTk
from ui_components.animation_player import AnimationPlayer
from ui_components import rpg_tile_renderer


class RPGTilePreviewer:
    """
    A previewer for RPG tile-based sprite animations.
    Displays sprites on a 3x3 grid of 32x32px tiles with pivot point visualization.
    The first frame of each direction is anchored at the bottom center of the middle tile.
    Allows exporting JSON data for each animation.
    """
    
    def __init__(self, parent_frame, parent_folder, return_to_main_callback, 
                 update_breadcrumbs_callback=None, base_path=None):
        self.parent_frame = parent_frame
        self.output_folder_1x = os.path.join(parent_folder, "output")
        self.output_folder_2x = os.path.join(parent_folder, "output x2")
        self.parent_folder = parent_folder
        self.return_to_main = return_to_main_callback
        self.update_breadcrumbs = update_breadcrumbs_callback
        self.base_path = base_path if base_path is not None else []
        
        self.main_frame = Frame(self.parent_frame)
        self.main_frame.pack(fill='both', expand=True)
        
        self.player = None
        self.current_anim_data = None
        self.current_sprite_map = None
        self.current_rpg_json = None

        self.selected_char_var = StringVar()
        self.selected_anim_var = StringVar()
        self.trace_id = None

        self.setup_ui()

    def setup_ui(self):
        if self.update_breadcrumbs:
            path = self.base_path + [("RPG Tile Preview", self.setup_ui)]
            self.update_breadcrumbs(path)

        self.clear_frame()
        
        if not os.path.exists(self.output_folder_1x) and not os.path.exists(self.output_folder_2x):
            messagebox.showerror("Error", 
                "Neither 'output' nor 'output x2' folders exist.\n"
                "Please run an export task first.")
            self.return_to_main()
            return
        
        self._setup_main_ui()

    def _setup_main_ui(self):
        # Top control bar
        top_control_frame = Frame(self.main_frame)
        top_control_frame.pack(fill='x', padx=10, pady=5)
        
        Button(top_control_frame, text="Back to Tasks", 
               command=self.return_to_main).pack(side='left', padx=(0, 20))

        # Character selector
        Label(top_control_frame, text="Character:").pack(side='left', padx=(10, 5))
        
        # Prefer output folder (1x) over output x2
        search_folder = self.output_folder_1x if os.path.exists(self.output_folder_1x) else self.output_folder_2x
        characters = sorted([d for d in os.listdir(search_folder) 
                           if os.path.isdir(os.path.join(search_folder, d))])
        
        if not characters:
            Label(self.main_frame, text="No characters found in 'output' or 'output x2' folder.", 
                  fg="red").pack(pady=50)
            return
        
        self.char_dropdown = OptionMenu(top_control_frame, self.selected_char_var, 
                                        *characters, command=self._on_character_selected)
        self.char_dropdown.pack(side='left')

        # Animation selector
        Label(top_control_frame, text="Animation:").pack(side='left', padx=(20, 5))
        self.trace_id = self.selected_anim_var.trace_add("write", self._on_animation_selected)
        self.anim_dropdown = OptionMenu(top_control_frame, self.selected_anim_var, "None")
        self.anim_dropdown.pack(side='left')

        # Export buttons
        export_frame = Frame(top_control_frame)
        export_frame.pack(side='right', padx=10)
        
        Button(export_frame, text="Export JSON", 
               command=self._export_json, bg="lightblue").pack(side='left', padx=2)
        Button(export_frame, text="Export All JSONs", 
               command=self._export_all_jsons, bg="lightgreen").pack(side='left', padx=2)

        # Info label
        info_frame = Frame(self.main_frame, bg="#f0f0f0")
        info_frame.pack(fill='x', padx=10, pady=5)
        
        info_text = (
            "RPG Tile Grid: 3x3 tiles (32x32px each = 96x96px canvas) | "
            "Red cross = Sprite pivot (bottom center) | "
            "Green triangle = Tile anchor (bottom center of middle tile) | "
            "Blue box = Sprite bounds | "
            "First frame's pivot is aligned to tile anchor"
        )
        Label(info_frame, text=info_text, bg="#f0f0f0", font=('Arial', 9), wraplength=1200).pack(pady=3)

        # Main content area with preview and JSON
        content_container = Frame(self.main_frame)
        content_container.pack(fill='both', expand=True, pady=10)
        content_container.grid_columnconfigure(0, weight=1)
        content_container.grid_columnconfigure(1, weight=1)

        # Preview frame (left side)
        preview_frame = Frame(content_container, bd=2, relief="groove")
        preview_frame.grid(row=0, column=0, padx=10, pady=5, sticky="nsew")
        
        Label(preview_frame, text="1x Scale (32px tiles)", font=('Arial', 12, 'bold')).pack(pady=5)
        
        preview_label = Label(preview_frame, bg="#e0e0e0")
        preview_label.pack(expand=True, pady=10)
        
        text_label = Label(preview_frame, justify="left", font=('Courier', 9))
        text_label.pack(pady=(5, 5))
        
        self.player = AnimationPlayer(self.main_frame, preview_label, text_label)
        
        # Animation control frame
        control_frame = Frame(preview_frame)
        control_frame.pack(pady=(5, 10))
        
        self.frame_counter_label = Label(control_frame, text="0 / 0", width=8)
        self.play_pause_button = Button(control_frame, text="Pause", width=6)
        
        Button(control_frame, text="<", width=3, command=self._prev_frame).pack(side='left')
        self.play_pause_button.config(command=self._toggle_play_pause)
        self.play_pause_button.pack(side='left', padx=2)
        Button(control_frame, text=">", width=3, command=self._next_frame).pack(side='left')
        self.frame_counter_label.pack(side='left', padx=5)

        # JSON Preview area (right side)
        json_frame = Frame(content_container, bd=2, relief="groove")
        json_frame.grid(row=0, column=1, padx=10, pady=5, sticky="nsew")
        
        Label(json_frame, text="RPG JSON Preview", font=('Arial', 11, 'bold')).pack(pady=5)
        
        # Scrollable text area for JSON
        json_scroll_frame = Frame(json_frame)
        json_scroll_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        json_canvas = Canvas(json_scroll_frame)
        json_scrollbar = Scrollbar(json_scroll_frame, orient="vertical", command=json_canvas.yview)
        self.json_inner_frame = Frame(json_canvas)
        
        self.json_inner_frame.bind("<Configure>", 
            lambda e: json_canvas.configure(scrollregion=json_canvas.bbox("all")))
        
        json_canvas.create_window((0, 0), window=self.json_inner_frame, anchor="nw")
        json_canvas.configure(yscrollcommand=json_scrollbar.set)
        
        json_canvas.pack(side="left", fill="both", expand=True)
        json_scrollbar.pack(side="right", fill="y")
        
        self.json_text = Label(self.json_inner_frame, text="Select an animation to view JSON", 
                               justify="left", anchor="nw", font=('Courier', 8))
        self.json_text.pack(fill='both', expand=True)

        # Initialize with first character
        self.selected_char_var.set(characters[0])
        self._on_character_selected(characters[0])
        
        # Start frame counter updater
        self._start_frame_counter_updater()

    def _on_character_selected(self, char_name):
        if self.trace_id:
            self.selected_anim_var.trace_remove("write", self.trace_id)
        
        char_path_1x = os.path.join(self.output_folder_1x, char_name)
        char_path_2x = os.path.join(self.output_folder_2x, char_name)
        
        anim_names = set()
        # Prefer 1x output, fall back to 2x
        if os.path.exists(char_path_1x):
            files = [f.replace("-AnimData.json", "") for f in os.listdir(char_path_1x) 
                    if f.lower().endswith('-animdata.json')]
            anim_names.update(files)
        elif os.path.exists(char_path_2x):
            files = [f.replace("-AnimData.json", "") for f in os.listdir(char_path_2x) 
                    if f.lower().endswith('-animdata.json')]
            anim_names.update(files)

        sorted_anim_names = sorted(list(anim_names))

        menu = self.anim_dropdown["menu"]
        menu.delete(0, "end")

        if sorted_anim_names:
            for name in sorted_anim_names:
                menu.add_command(label=name, 
                               command=lambda value=name: self.selected_anim_var.set(value))
            self.selected_anim_var.set(sorted_anim_names[0])
        else:
            self.selected_anim_var.set("None")
            self.clear_animation()

        self.trace_id = self.selected_anim_var.trace_add("write", self._on_animation_selected)
        if not sorted_anim_names:
            self._load_and_display_animation()

    def _on_animation_selected(self, *args):
        self._load_and_display_animation()

    def _load_and_display_animation(self):
        self.clear_animation()
        
        char_name = self.selected_char_var.get()
        anim_name = self.selected_anim_var.get()

        if not char_name or not anim_name or anim_name == "None":
            return

        anim_filename = f"{anim_name}-AnimData.json"

        try:
            # Try 1x first, then 2x
            if os.path.exists(self.output_folder_1x):
                anim_data, sprites, shadow = self._load_animation_data(
                    self.output_folder_1x, char_name, anim_filename)
                scale_factor = 1
            else:
                anim_data, sprites, shadow = self._load_animation_data(
                    self.output_folder_2x, char_name, anim_filename)
                scale_factor = 1  # Still use 1x tile size for display
            
            if anim_data:
                self.current_anim_data = anim_data
                self.current_sprite_map = sprites
                
                preview_data = rpg_tile_renderer.generate_rpg_tile_preview_data(
                    anim_data, sprites, shadow, scale_factor=scale_factor)
                self.player.set_animation(**{k: v for k, v in preview_data.items() 
                                            if k != 'rpg_metadata'})
                self.player.play()
                self.play_pause_button.config(text="Pause")
                self._update_frame_counter()
                
                # Generate RPG JSON
                self.current_rpg_json = rpg_tile_renderer.generate_rpg_json_for_animation(
                    anim_data, sprites, scale_factor=scale_factor)
                
                # Update JSON preview
                self._update_json_preview()
            else:
                self.current_anim_data = None
                self.current_sprite_map = None
                self.current_rpg_json = None
                self.player.set_animation([], [], text_data=[])
                self.player.image_label.config(text="No data found", fg="grey")
                self.json_text.config(text="No JSON data available")
                self.frame_counter_label.config(text="0 / 0")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to start preview: {e}")
            import traceback
            traceback.print_exc()

    def _load_animation_data(self, base_folder, character_name, anim_filename):
        """Load animation data from JSON file."""
        json_path = os.path.join(base_folder, character_name, anim_filename)
        if not os.path.exists(json_path):
            return None, None, None
        
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        sprite_folder = os.path.join(base_folder, character_name, data['name'])
        sprite_map = rpg_tile_renderer.load_sprites_from_json(data, sprite_folder)
        
        shadow_sprite = None
        shadow_path = os.path.join(base_folder, character_name, "sprite_shadow.png")
        if os.path.exists(shadow_path):
            try:
                shadow_sprite = Image.open(shadow_path).convert('RGBA')
            except Exception as e:
                print(f"Warning: Could not load shadow sprite at {shadow_path}: {e}")

        return data, sprite_map, shadow_sprite

    def _update_json_preview(self):
        """Update the JSON preview text area."""
        if self.current_rpg_json:
            # Show a formatted summary of the JSON
            json_data = self.current_rpg_json
            
            lines = [
                f"Animation: {json_data['name']}",
                f"Tile Size: {json_data['tile_size']}px",
                f"Canvas: {json_data['canvas_size']}x{json_data['canvas_size']}px",
                f"Tile Anchor: {json_data['tile_anchor']}",
                f"Durations: {json_data['durations']}",
                "",
                f"Directions ({len(json_data['directions'])}):"
            ]
            
            for dir_name, dir_data in json_data['directions'].items():
                frame_count = len(dir_data['frames'])
                anchor = dir_data.get('anchor_offset', [0, 0])
                lines.append(
                    f"  {dir_name}:"
                )
                lines.append(
                    f"    Frames: {frame_count}, Anchor offset: {anchor}"
                )
                
                # Show first frame details
                if dir_data['frames']:
                    first_frame = dir_data['frames'][0]
                    lines.append(
                        f"    First frame: sprite_{first_frame['sprite_id']} "
                        f"({first_frame['sprite_width']}x{first_frame['sprite_height']})"
                    )
            
            lines.append("")
            lines.append(f"Unique Sprites ({len(json_data['sprite_assets'])}):")
            
            for sprite_id, sprite_info in sorted(json_data['sprite_assets'].items()):
                lines.append(
                    f"  {sprite_id}: {sprite_info['width']}x{sprite_info['height']}, "
                    f"pivot: {sprite_info['pivot']}"
                )
            
            self.json_text.config(text="\n".join(lines))
        else:
            self.json_text.config(text="No JSON data available")

    def _export_json(self):
        """Export RPG JSON for the current animation."""
        char_name = self.selected_char_var.get()
        anim_name = self.selected_anim_var.get()
        
        if not self.current_rpg_json:
            messagebox.showwarning("Warning", "No JSON data available for export.")
            return
        
        # Suggest filename
        default_filename = f"{char_name}_{anim_name}_rpg.json"
        
        filepath = filedialog.asksaveasfilename(
            title="Save RPG JSON",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=default_filename
        )
        
        if filepath:
            try:
                with open(filepath, 'w') as f:
                    json.dump(self.current_rpg_json, f, indent=2)
                messagebox.showinfo("Success", f"JSON exported successfully to:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export JSON: {e}")

    def _export_all_jsons(self):
        """Export RPG JSONs for all animations of the current character."""
        char_name = self.selected_char_var.get()
        
        if not char_name:
            messagebox.showwarning("Warning", "Please select a character first.")
            return
        
        # Ask for output directory
        output_dir = filedialog.askdirectory(
            title=f"Select output folder for {char_name} RPG JSONs"
        )
        
        if not output_dir:
            return
        
        # Prefer output (1x) folder
        if os.path.exists(self.output_folder_1x):
            char_path = os.path.join(self.output_folder_1x, char_name)
            scale_factor = 1
        else:
            char_path = os.path.join(self.output_folder_2x, char_name)
            scale_factor = 1
        
        if not os.path.exists(char_path):
            messagebox.showerror("Error", "No output folder found for this character.")
            return
        
        anim_files = [f for f in os.listdir(char_path) if f.endswith('-AnimData.json')]
        
        if not anim_files:
            messagebox.showwarning("Warning", "No animation data found for this character.")
            return
        
        exported_count = 0
        errors = []
        
        for anim_file in anim_files:
            try:
                anim_name = anim_file.replace("-AnimData.json", "")
                
                # Use the correct base folder
                if os.path.exists(self.output_folder_1x):
                    base_folder = self.output_folder_1x
                else:
                    base_folder = self.output_folder_2x
                
                # Load animation data
                anim_data, sprite_map, _ = self._load_animation_data(
                    base_folder, char_name, anim_file)
                
                if anim_data and sprite_map:
                    # Generate RPG JSON
                    rpg_json = rpg_tile_renderer.generate_rpg_json_for_animation(
                        anim_data, sprite_map, scale_factor=scale_factor)
                    
                    # Save to file
                    output_path = os.path.join(output_dir, f"{anim_name}_rpg.json")
                    with open(output_path, 'w') as f:
                        json.dump(rpg_json, f, indent=2)
                    
                    exported_count += 1
            except Exception as e:
                errors.append(f"{anim_name}: {str(e)}")
        
        # Show results
        result_msg = f"Exported {exported_count} RPG JSONs to:\n{output_dir}"
        if errors:
            result_msg += f"\n\nErrors ({len(errors)}):\n" + "\n".join(errors[:5])
            if len(errors) > 5:
                result_msg += f"\n... and {len(errors) - 5} more"
        
        messagebox.showinfo("Export Complete", result_msg)

    def _toggle_play_pause(self):
        """Toggle between play and pause states."""
        if not self.player:
            return
        
        if self.player.is_playing:
            self.player.pause()
            self.play_pause_button.config(text="Play")
        else:
            self.player.play()
            self.play_pause_button.config(text="Pause")

    def _prev_frame(self):
        """Go to the previous frame and pause."""
        if not self.player or not self.player.frames:
            return
        
        self.player.pause()
        self.play_pause_button.config(text="Play")
        new_index = (self.player.current_frame_index - 1) % len(self.player.frames)
        self.player.go_to_frame(new_index)
        self._update_frame_counter()

    def _next_frame(self):
        """Go to the next frame and pause."""
        if not self.player or not self.player.frames:
            return
        
        self.player.pause()
        self.play_pause_button.config(text="Play")
        new_index = (self.player.current_frame_index + 1) % len(self.player.frames)
        self.player.go_to_frame(new_index)
        self._update_frame_counter()

    def _update_frame_counter(self):
        """Update the frame counter label."""
        if self.player and self.player.frames:
            current = self.player.current_frame_index + 1
            total = len(self.player.frames)
            self.frame_counter_label.config(text=f"{current} / {total}")

    def _start_frame_counter_updater(self):
        """Start the periodic frame counter updater."""
        def update():
            if hasattr(self, 'main_frame') and self.main_frame.winfo_exists():
                self._update_frame_counter()
                self.main_frame.after(100, update)
        update()

    def clear_animation(self):
        """Stop the animation player."""
        if self.player:
            self.player.stop()

    def clear_frame(self):
        """Clear all widgets and stop animations."""
        self.clear_animation()
        if self.trace_id:
            try:
                self.selected_anim_var.trace_remove("write", self.trace_id)
            except Exception:
                pass
        for widget in self.main_frame.winfo_children():
            widget.destroy()
