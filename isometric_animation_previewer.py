# isometric_animation_previewer.py

import os
import json
from tkinter import Frame, Label, Button, Canvas, messagebox, OptionMenu, StringVar, Entry

from PIL import Image, ImageTk, ImageDraw

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
        
        self.after_ids = []

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

        frame_1x = Frame(preview_container); frame_1x.grid(row=0, column=0, padx=10, sticky="nsew")
        Label(frame_1x, text="1x Scale (output)", font=('Arial', 12, 'bold')).pack()
        self.label_1x = Label(frame_1x); self.label_1x.pack(expand=True)
        
        frame_2x = Frame(preview_container); frame_2x.grid(row=0, column=1, padx=10, sticky="nsew")
        Label(frame_2x, text="2x Scale (output x2)", font=('Arial', 12, 'bold')).pack()
        self.label_2x = Label(frame_2x); self.label_2x.pack(expand=True)

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
            anim_data_1x, sprites_1x, shadow_1x = self._load_animation_data(self.output_folder_1x, char_name, anim_filename)
            anim_data_2x, sprites_2x, shadow_2x = self._load_animation_data(self.output_folder_2x, char_name, anim_filename)
            
            tile_constants_1x = {'WIDTH': 32, 'HEIGHT': 16, 'WIDTH_HALF': 16, 'HEIGHT_HALF': 8}
            tile_constants_2x = {'WIDTH': 64, 'HEIGHT': 32, 'WIDTH_HALF': 32, 'HEIGHT_HALF': 16}

            if anim_data_1x:
                self._start_animation_loop(self.label_1x, anim_data_1x, tile_constants_1x, sprites_1x, shadow_1x)
            else:
                self.label_1x.config(image='', text="No 1x data found", fg="grey")

            if anim_data_2x:
                self._start_animation_loop(self.label_2x, anim_data_2x, tile_constants_2x, sprites_2x, shadow_2x)
            else:
                self.label_2x.config(image='', text="No 2x data found", fg="grey")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to start preview: {e}")

    def _load_animation_data(self, base_folder, character_name, anim_filename):
        json_path = os.path.join(base_folder, character_name, anim_filename)
        if not os.path.exists(json_path): return None, None, None
        
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        sprite_folder = os.path.join(base_folder, character_name, data['name'])
        loaded_sprites = {}

        for group in data.get('sprites', {}).values():
            for frame in group.get('frames', []):
                sprite_id = frame.get('id', '0')
                if sprite_id != '0' and sprite_id not in loaded_sprites:
                    sprite_path = os.path.join(sprite_folder, f"sprite_{sprite_id}.png")
                    try:
                        loaded_sprites[sprite_id] = Image.open(sprite_path).convert('RGBA')
                    except FileNotFoundError:
                        print(f"Warning: Sprite not found at {sprite_path}")
                        loaded_sprites[sprite_id] = None
        
        shadow_sprite = None
        shadow_path = os.path.join(base_folder, character_name, "sprite_base.png")
        if os.path.exists(shadow_path):
            try:
                shadow_sprite = Image.open(shadow_path).convert('RGBA')
            except Exception as e:
                print(f"Warning: Could not load shadow sprite at {shadow_path}: {e}")

        return data, loaded_sprites, shadow_sprite

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

    def _start_animation_loop(self, label, anim_data, tile_consts, sprite_map, shadow_sprite):
        all_frames_with_context = []
        for group_id in sorted(anim_data['sprites'].keys(), key=int):
            group_data = anim_data['sprites'][group_id]
            for frame_info in group_data['frames']:
                all_frames_with_context.append({
                    "frame_info": frame_info,
                })
        
        if not all_frames_with_context:
            label.config(image='', text="No frames in animation", fg="red")
            return

        canvas_width = tile_consts['WIDTH'] * 5
        canvas_height = tile_consts['HEIGHT'] * 5
        
        current_frame_idx = [0]
        
        def update():
            if not label.winfo_exists(): return
            
            context = all_frames_with_context[current_frame_idx[0] % len(all_frames_with_context)]
            frame_info = context["frame_info"]
            
            canvas = Image.new('RGBA', (canvas_width, canvas_height), (0, 0, 0, 0))
            
            world_anchor_x = canvas_width // 2
            world_anchor_y = canvas_height // 2

            grid_origin_x = world_anchor_x - tile_consts['WIDTH_HALF']
            grid_origin_y = world_anchor_y - (tile_consts['HEIGHT_HALF'] * 3)
            
            self._draw_iso_grid(canvas, (grid_origin_x, grid_origin_y), tile_consts)
            
            if shadow_sprite:
                shadow_paste_x = world_anchor_x - shadow_sprite.width // 2
                shadow_paste_y = world_anchor_y - shadow_sprite.height // 2
                canvas.paste(shadow_sprite, (shadow_paste_x, shadow_paste_y), shadow_sprite)

            sprite_id = frame_info.get('id', '0')
            sprite_img = sprite_map.get(sprite_id)
            render_offset = frame_info.get('render_offset')

            if sprite_img and render_offset and len(render_offset) == 2:
                render_x, render_y = render_offset
                paste_pos = (world_anchor_x + render_x, world_anchor_y + render_y)
                canvas.paste(sprite_img, paste_pos, sprite_img)

            img_tk = ImageTk.PhotoImage(canvas)
            label.config(image=img_tk)
            label.image = img_tk
            
            duration_idx = current_frame_idx[0] % len(anim_data['durations'])
            delay = anim_data['durations'][duration_idx] * 33
            
            current_frame_idx[0] += 1
            self.after_ids.append(self.parent_frame.after(delay, update))
        
        update()

    def clear_animations(self):
        for aid in self.after_ids: self.parent_frame.after_cancel(aid)
        self.after_ids.clear()
        if hasattr(self, 'label_1x'): self.label_1x.config(image='')
        if hasattr(self, 'label_2x'): self.label_2x.config(image='')

    def clear_frame(self):
        self.clear_animations()
        if self.trace_id:
            try:
                self.selected_anim_var.trace_remove("write", self.trace_id)
            except Exception:
                pass
        for widget in self.main_frame.winfo_children():
            widget.destroy()