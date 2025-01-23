import os
import json
from tkinter import Frame, Label, Canvas, Scrollbar, Entry, messagebox, Toplevel
from PIL import Image, ImageTk
import xml.etree.ElementTree as ET
from sprite_sheet_handler import SpriteSheetHandler
import math

class AnimationViewer:
    def __init__(self, parent_frame, anim_folder):
        self.parent_frame = parent_frame
        self.anim_folder = anim_folder
        self.sprite_folder = os.path.join(anim_folder, "sprite")
        self.anim_data = self.load_anim_data()
        self.current_anim_index = 0
        self.after_ids = []
        self.current_sprites_entries = []  # Almacenar inputs de sprites
        
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
        for anim in tree.getroot().find("Anims"):
            anim_data = {
                "name": anim.find("Name").text,
                "frame_width": int(anim.find("FrameWidth").text),
                "frame_height": int(anim.find("FrameHeight").text),
                "durations": [int(d.text) for d in anim.findall("Durations/Duration")],
                "image_path": os.path.join(self.sprite_folder, f"{anim.find('Name').text}-Anim.png")
            }
            
            with Image.open(anim_data["image_path"]) as img:
                anim_data["total_groups"] = img.height // anim_data["frame_height"]
                anim_data["frames_per_group"] = img.width // anim_data["frame_width"]
            
            animations.append(anim_data)
        return animations

    def show_animation(self):
        self.clear_animations()
        self.current_sprites_entries = []  # Resetear inputs
        self.group_names = []  # Almacenar nombres de los grupos
        
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        
        anim = self.anim_data[self.current_anim_index]
        handler = SpriteSheetHandler(anim["image_path"])
        all_frames = handler.split_animation_frames(anim["frame_width"], anim["frame_height"])
        
        total_groups = anim["total_groups"]
        frames_per_group = anim["frames_per_group"]
        
        # Cargar datos del JSON si existe
        json_data = self.load_json_data(anim["name"])
        group_data = json_data["sprites"] if json_data else None
        
        main_title = Label(self.scroll_frame, 
                        text=f"Animation: {anim['name']}",
                        font=('Arial', 14, 'bold'))
        main_title.pack(pady=10)
        
        for group_idx in range(total_groups):
            group_frame = Frame(self.scroll_frame, bd=2, relief="groove")
            group_frame.pack(fill="x", padx=5, pady=5)
            
            # Grupo header con campo de entrada para el nombre
            header_frame = Frame(group_frame)
            header_frame.pack(fill="x", pady=5)
            
            Label(header_frame, 
                text=f"Group {group_idx + 1}", 
                font=('Arial', 12, 'bold')).pack(side='left')
            
            # Campo de entrada para el nombre del grupo
            group_name_entry = Entry(header_frame, width=20)
            if group_data and group_idx < len(group_data):
                group_name = list(group_data[group_idx].keys())[0]  # Obtener nombre del grupo desde JSON
                group_name_entry.insert(0, group_name)
            else:
                group_name_entry.insert(0, f"grupo{group_idx + 1}")  # Nombre por defecto
            group_name_entry.pack(side='left', padx=10)
            self.group_names.append(group_name_entry)  # Guardar referencia
            
            content_frame = Frame(group_frame)
            content_frame.pack(fill="x")
            
            anim_panel = Frame(content_frame)
            anim_panel.pack(side="left", padx=10)
            
            frames_panel = Frame(content_frame)
            frames_panel.pack(side="right", fill="x", expand=True)
            
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
                
                # Campo de entrada para el valor del sprite
                entry = Entry(frames_panel, width=5)
                if group_data and group_idx < len(group_data):
                    sprite_values = list(group_data[group_idx].values())[0]  # Obtener valores del grupo desde JSON
                    if idx < len(sprite_values):
                        entry.insert(0, str(sprite_values[idx]))  # Rellenar con valor del JSON
                else:
                    entry.insert(0, "0")  # Valor por defecto
                entry.grid(row=1, column=idx, padx=2)
                group_entries.append(entry)
                
                # Mostrar duración del XML
                Label(frames_panel, 
                    text=f"Dur: {durations[idx]}",
                    font=('Arial', 7)).grid(row=2, column=idx)
            
            self.current_sprites_entries.extend(group_entries)

    def clear_animations(self):
        for aid in self.after_ids:
            self.parent_frame.after_cancel(aid)
        self.after_ids.clear()

    def start_group_animation(self, label, frames, durations):
        current_frame = [0]
        
        def update():
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
        self.current_anim_index = (self.current_anim_index - 1) % len(self.anim_data)
        self.show_animation()

    def next_animation(self):
        self.current_anim_index = (self.current_anim_index + 1) % len(self.anim_data)
        self.show_animation()

    def generate_json(self):
        try:
            # Obtener los nombres de los grupos
            group_names = [entry.get().strip() for entry in self.group_names]
            
            # Validar que no haya nombres duplicados
            if len(group_names) != len(set(group_names)):
                messagebox.showerror("Error", "Hay grupos con nombres duplicados. Por favor, corrige los nombres.")
                return
            
            # Obtener los valores de los inputs de sprites
            sprites = []
            for entry in self.current_sprites_entries:
                value = entry.get()
                if not value.strip():
                    raise ValueError("Empty value found")
                sprites.append(int(value))
            
            # Obtener la animación actual
            anim = self.anim_data[self.current_anim_index]
            
            # Calcular el número de frames por grupo
            frames_per_group = anim["frames_per_group"]
            
            # Agrupar los valores de sprites según el grupo y asignar nombres
            grouped_sprites = []
            for group_idx, group_name in enumerate(group_names):
                start = group_idx * frames_per_group
                end = start + frames_per_group
                group = sprites[start:end]
                grouped_sprites.append({group_name: group})  # Guardar como diccionario
            
            # Crear estructura JSON
            json_data = {
                "index": self.current_anim_index,
                "name": anim["name"],
                "framewidth": anim["frame_width"],
                "frameheight": anim["frame_height"],
                "sprites": grouped_sprites,  # Sprites agrupados por nombre de grupo
                "durations": anim["durations"]
            }
            
            # Crear carpeta de salida si no existe
            folder_name = os.path.basename(self.anim_folder) + "AnimationData"
            output_folder = os.path.join(self.anim_folder, folder_name)
            os.makedirs(output_folder, exist_ok=True)
            
            # Guardar archivo JSON
            filename = f"{anim['name']}-AnimData.json"
            output_path = os.path.join(output_folder, filename)
            
            with open(output_path, 'w') as f:
                json.dump(json_data, f, indent=4)
            
            messagebox.showinfo("Success", f"JSON saved at:\n{output_path}")
        
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid input: {str(e)}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate JSON: {str(e)}")
    
    def view_sprites(self):
        """Abrir ventana con sprites editados"""
        edited_folder = os.path.join(self.anim_folder, os.path.basename(self.anim_folder) + "Edited")
        
        if not os.path.exists(edited_folder):
            messagebox.showwarning("Warning", "No edited sprites folder found")
            return
        
        # Obtener lista de archivos de sprites
        sprite_files = sorted(
            [f for f in os.listdir(edited_folder) if f.lower().endswith('.png')],
            key=lambda x: int(x.split('_')[-1].split('.')[0])  # Ordenar por número en el nombre
        )
        
        if not sprite_files:
            messagebox.showwarning("Warning", "No sprites found in edited folder")
            return
        
        # Calcular tamaño de la cuadrícula
        num_sprites = len(sprite_files)
        grid_size = math.ceil(math.sqrt(num_sprites))  # Raíz cuadrada redondeada hacia arriba
        
        # Crear ventana emergente
        sprite_window = Toplevel(self.parent_frame)
        sprite_window.title(f"Sprites Gallery ({num_sprites} sprites)")
        sprite_window.geometry(f"{100 * grid_size + 50}x{100 * grid_size + 50}")
        
        # Canvas con scroll (por si la cuadrícula es muy grande)
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
        
        # Mostrar sprites en cuadrícula
        for idx, file in enumerate(sprite_files):
            try:
                # Obtener número del sprite
                sprite_number = int(file.split('_')[-1].split('.')[0])
                
                # Calcular posición en la cuadrícula
                row = (sprite_number - 1) // grid_size
                col = (sprite_number - 1) % grid_size
                
                # Cargar y mostrar la imagen
                img_path = os.path.join(edited_folder, file)
                img = Image.open(img_path)
                img.thumbnail((100, 100))
                
                photo = ImageTk.PhotoImage(img)
                frame = Frame(scroll_frame)
                frame.grid(row=row, column=col, padx=5, pady=5)
                
                Label(frame, image=photo).pack()
                Label(frame, text=file, font=('Arial', 8)).pack()
                
                # Guardar referencia a la imagen para evitar garbage collection
                frame.photo = photo
                
            except Exception as e:
                print(f"Error loading {file}: {str(e)}")

    def load_json_data(self, anim_name):
        """Cargar datos del archivo JSON si existe."""
        folder_name = os.path.basename(self.anim_folder) + "AnimationData"
        json_path = os.path.join(self.anim_folder, folder_name, f"{anim_name}-AnimData.json")
        
        if not os.path.exists(json_path):
            return None  # No existe el archivo JSON
        
        try:
            with open(json_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading JSON: {str(e)}")
            return None