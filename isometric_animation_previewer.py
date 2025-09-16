# isometric_animation_previewer.py

import os
import json
from tkinter import Frame, Label, Button, Canvas, messagebox, OptionMenu, StringVar

from PIL import Image, ImageTk, ImageDraw

class IsometricAnimationPreviewer:
    def __init__(self, parent_frame, parent_folder, return_to_main_callback):
        self.parent_frame = parent_frame
        self.output_folder_1x = os.path.join(parent_folder, "output")
        self.output_folder_2x = os.path.join(parent_folder, "output x2")
        self.return_to_main = return_to_main_callback
        
        self.main_frame = Frame(self.parent_frame)
        self.main_frame.pack(fill='both', expand=True)
        
        self.after_ids = []
        self.is_paused = False

        # --- Variables para los menús desplegables ---
        self.selected_char_var = StringVar()
        self.selected_anim_var = StringVar()
        
        # --- INICIALIZAR trace_id AQUÍ ---
        self.trace_id = None 

        self.setup_ui()

    def setup_ui(self):
        self.clear_frame()
        if not os.path.exists(self.output_folder_1x) or not os.path.exists(self.output_folder_2x):
            messagebox.showerror("Error", "Las carpetas 'output' y 'output x2' deben existir.\nPor favor, ejecute las tareas de exportación primero.")
            self.return_to_main()
            return
        
        self._setup_main_ui()

    def _setup_main_ui(self):
        # --- Frame de Controles Superiores ---
        control_frame = Frame(self.main_frame); control_frame.pack(fill='x', padx=10, pady=5)
        Button(control_frame, text="Back to Tasks", command=self.return_to_main).pack(side='left', padx=(0, 20))

        # --- Menú de Personajes ---
        Label(control_frame, text="Character:").pack(side='left', padx=(10, 5))
        characters = sorted([d for d in os.listdir(self.output_folder_1x) if os.path.isdir(os.path.join(self.output_folder_1x, d))])
        if not characters:
            Label(self.main_frame, text="No characters found in 'output' folder.", fg="red").pack(pady=50)
            return
        
        self.char_dropdown = OptionMenu(control_frame, self.selected_char_var, *characters, command=self._on_character_selected)
        self.char_dropdown.pack(side='left')

        # --- Menú de Animaciones ---
        Label(control_frame, text="Animation:").pack(side='left', padx=(20, 5))
        # El trace se añade aquí una sola vez y se gestiona su estado.
        self.trace_id = self.selected_anim_var.trace_add("write", self._on_animation_selected)
        self.anim_dropdown = OptionMenu(control_frame, self.selected_anim_var, "None")
        self.anim_dropdown.pack(side='left')

        # --- Botón de Pausa/Reanudar ---
        self.pause_button = Button(control_frame, text="Pause", command=self.toggle_pause)
        self.pause_button.pack(side='left', padx=20)

        # --- Contenedor de Previsualización ---
        preview_container = Frame(self.main_frame); preview_container.pack(fill='both', expand=True, pady=10)
        preview_container.grid_columnconfigure(0, weight=1); preview_container.grid_columnconfigure(1, weight=1)

        # --- Preview 1x ---
        frame_1x = Frame(preview_container); frame_1x.grid(row=0, column=0, padx=10, sticky="nsew")
        Label(frame_1x, text="1x Scale (output)", font=('Arial', 12, 'bold')).pack()
        self.label_1x = Label(frame_1x); self.label_1x.pack(expand=True)
        
        # --- Preview 2x ---
        frame_2x = Frame(preview_container); frame_2x.grid(row=0, column=1, padx=10, sticky="nsew")
        Label(frame_2x, text="2x Scale (output x2)", font=('Arial', 12, 'bold')).pack()
        self.label_2x = Label(frame_2x); self.label_2x.pack(expand=True)

        # --- Carga Inicial ---
        self.selected_char_var.set(characters[0])
        self._on_character_selected(characters[0])

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.pause_button.config(text="Resume")
        else:
            self.pause_button.config(text="Pause")

    def _on_character_selected(self, char_name):
        """Callback que se ejecuta al cambiar de personaje. Actualiza la lista de animaciones."""
        # Desvincular temporalmente el trace para evitar que se dispare al cambiar la lista
        if self.trace_id:
            self.selected_anim_var.trace_remove("write", self.trace_id)

        char_path = os.path.join(self.output_folder_1x, char_name)
        anim_files = sorted([f for f in os.listdir(char_path) if f.lower().endswith('-animdata.json')])
        anim_names = [f.replace("-AnimData.json", "") for f in anim_files]

        menu = self.anim_dropdown["menu"]
        menu.delete(0, "end")

        if anim_names:
            for name in anim_names:
                # Usar una función lambda para establecer el valor, que luego será detectado por el trace
                menu.add_command(label=name, command=lambda value=name: self.selected_anim_var.set(value))
            self.selected_anim_var.set(anim_names[0]) # Esto disparará el trace_add de abajo
        else:
            self.selected_anim_var.set("None")
            self.clear_animations()

        # Volver a vincular el trace. La animación se cargará a través de este callback.
        self.trace_id = self.selected_anim_var.trace_add("write", self._on_animation_selected)
        # Si se estableció un nuevo valor, el trace ya se habrá disparado. Si no, llamamos manualmente.
        if not anim_names:
             self._load_and_display_animation()


    def _on_animation_selected(self, *args):
        """Callback que se ejecuta al cambiar de animación. Recarga la previsualización."""
        self._load_and_display_animation()

    def _load_and_display_animation(self):
        """Función principal que carga los datos y lanza las animaciones."""
        self.clear_animations()
        self.is_paused = False
        self.pause_button.config(text="Pause")

        char_name = self.selected_char_var.get()
        anim_name = self.selected_anim_var.get()

        if not char_name or not anim_name or anim_name == "None":
            return

        anim_filename = f"{anim_name}-AnimData.json"

        try:
            anim_data_1x, sprites_1x = self._load_animation_data(self.output_folder_1x, char_name, anim_filename)
            anim_data_2x, sprites_2x = self._load_animation_data(self.output_folder_2x, char_name, anim_filename)
            
            tile_constants = {'WIDTH': 64, 'HEIGHT': 32, 'WIDTH_HALF': 32, 'HEIGHT_HALF': 16}

            if anim_data_1x:
                self._start_animation_loop(self.label_1x, anim_data_1x, tile_constants, sprites_1x)
            else:
                self.label_1x.config(image='', text="Failed to load 1x data", fg="red")

            if anim_data_2x:
                self._start_animation_loop(self.label_2x, anim_data_2x, tile_constants, sprites_2x)
            else:
                self.label_2x.config(image='', text="Failed to load 2x data", fg="red")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to start preview: {e}")

    def _load_animation_data(self, base_folder, character_name, anim_filename):
        """Carga el JSON y los sprites asociados, devolviendo ambos."""
        json_path = os.path.join(base_folder, character_name, anim_filename)
        if not os.path.exists(json_path): return None, None
        
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        sprite_folder = os.path.join(base_folder, character_name, "Sprites")
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
        return data, loaded_sprites

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

    def _start_animation_loop(self, label, anim_data, tile_consts, sprite_map):
        all_frames = []
        for group_id in sorted(anim_data['sprites'].keys(), key=int):
            all_frames.extend(anim_data['sprites'][group_id]['frames'])
        
        if not all_frames:
            label.config(image='', text="No frames in animation", fg="red")
            return

        canvas_width = tile_consts['WIDTH'] * 4
        canvas_height = tile_consts['HEIGHT'] * 4
        grid_origin = (canvas_width / 2 - tile_consts['WIDTH_HALF'], canvas_height / 2 - tile_consts['HEIGHT'])

        current_frame_idx = [0]
        
        def update():
            if not label.winfo_exists(): return
            
            if self.is_paused:
                self.after_ids.append(self.parent_frame.after(100, update))
                return

            frame_info = all_frames[current_frame_idx[0] % len(all_frames)]
            
            canvas = Image.new('RGBA', (canvas_width, canvas_height), (255, 255, 255, 0))
            self._draw_iso_grid(canvas, grid_origin, tile_consts)
            
            sprite_id = frame_info.get('id', '0')
            sprite_img = sprite_map.get(sprite_id)

            if sprite_img:
                offset_x, offset_y = frame_info.get('offset', [0, 0])
                frame_w, frame_h = anim_data['framewidth'], anim_data['frameheight']
                sprite_w, sprite_h = sprite_img.size

                center_tile_top = self._grid_to_screen(1, 1, grid_origin, tile_consts['WIDTH_HALF'], tile_consts['HEIGHT_HALF'])
                center_tile_center_x = center_tile_top[0] + tile_consts['WIDTH_HALF']
                center_tile_center_y = center_tile_top[1] + tile_consts['HEIGHT_HALF']
                
                container_x = center_tile_center_x - (frame_w / 2)
                container_y = center_tile_center_y - (frame_h / 2) - 10
                
                paste_x_in_frame = offset_x - (sprite_w / 2)
                paste_y_in_frame = offset_y - (sprite_h / 2)
                
                final_paste_x = container_x + paste_x_in_frame
                final_paste_y = container_y + paste_y_in_frame
                
                canvas.paste(sprite_img, (int(final_paste_x), int(final_paste_y)), sprite_img)

            img_tk = ImageTk.PhotoImage(canvas)
            label.config(image=img_tk)
            label.image = img_tk
            
            duration_idx = current_frame_idx[0] % len(anim_data['durations'])
            delay = anim_data['durations'][duration_idx] * 33
            
            current_frame_idx[0] += 1
            self.after_ids.append(self.parent_frame.after(delay, update))
        
        update()

    def clear_animations(self):
        """Detiene solo los bucles de animación sin destruir la UI."""
        for aid in self.after_ids: self.parent_frame.after_cancel(aid)
        self.after_ids.clear()
        if hasattr(self, 'label_1x'): self.label_1x.config(image='')
        if hasattr(self, 'label_2x'): self.label_2x.config(image='')

    def clear_frame(self):
        """Limpia todo el frame, incluyendo bucles y widgets."""
        self.clear_animations()
        if self.trace_id:
            try:
                self.selected_anim_var.trace_remove("write", self.trace_id)
            except Exception:
                pass
        for widget in self.main_frame.winfo_children(): widget.destroy()