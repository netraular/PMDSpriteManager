import os
import json
from tkinter import Frame, Label, Canvas, Scrollbar, Entry, messagebox, Toplevel, BooleanVar, Checkbutton, OptionMenu, StringVar
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
        self.group_widgets = {}  # Almacenar widgets de cada grupo
        self.linked_groups = {}  # Almacenar relaciones entre grupos {grupo_actual: grupo_origen}
        
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
        self.group_widgets = {}  # Resetear widgets de grupos
        self.linked_groups = {}  # Resetear relaciones entre grupos
        
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
            
            # Frame para controles de "mirror & copy"
            control_frame = Frame(group_frame)
            control_frame.pack(side='right', padx=10)
            
            # Checkbox "mirror & copy"
            mirror_var = BooleanVar()
            Checkbutton(
                control_frame, 
                text="mirror & copy", 
                variable=mirror_var,
                command=lambda idx=group_idx: self.toggle_mirror_copy(idx)
            ).pack()
            
            # Dropdown de grupos (inicialmente oculto)
            group_names = [f"Group {i+1}" for i in range(total_groups) if i != group_idx]
            dropdown_var = StringVar()
            dropdown_var.set("Group 1")  # Establecer un valor predeterminado
            dropdown = OptionMenu(control_frame, dropdown_var, *group_names)
            dropdown.pack_forget()
            
            # Guardar referencias
            self.group_widgets[group_idx] = {
                "mirror_var": mirror_var,
                "dropdown": dropdown,
                "dropdown_var": dropdown_var,
                "entries": [],
                "frame": None
            }
            
            # Añadir seguimiento a cambios en el dropdown
            dropdown_var.trace_add("write", lambda *args, idx=group_idx: self.update_linked_group(idx))
            
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
            self.group_widgets[group_idx]["entries"] = group_entries

    def update_linked_group(self, group_idx):
        """Actualiza el grupo vinculado cuando cambia la selección del dropdown."""
        if self.group_widgets[group_idx]["mirror_var"].get():
            selected_group_name = self.group_widgets[group_idx]["dropdown_var"].get()
            selected_group = int(selected_group_name.split()[-1]) - 1
            self.linked_groups[group_idx] = selected_group

    def toggle_mirror_copy(self, group_idx):
        widgets = self.group_widgets[group_idx]
        if widgets["mirror_var"].get():
            # Mostrar dropdown y ocultar inputs
            widgets["dropdown"].pack()
            for entry in widgets["entries"]:
                entry.grid_remove()
            
            # Actualizar grupo vinculado con la selección actual
            self.update_linked_group(group_idx)
        else:
            # Ocultar dropdown y mostrar inputs
            widgets["dropdown"].pack_forget()
            for entry in widgets["entries"]:
                entry.grid()
            self.linked_groups.pop(group_idx, None)

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
            group_names = [entry.get().strip() for entry in self.group_names]
            
            if len(group_names) != len(set(group_names)):
                messagebox.showerror("Error", "Nombres de grupo duplicados.")
                return
            
            # Obtener valores actuales de TODOS los sprites (incluyendo grupos vinculados)
            sprites = []
            for entry in self.current_sprites_entries:
                sprites.append(int(entry.get()))
            
            anim = self.anim_data[self.current_anim_index]
            frames_per_group = anim["frames_per_group"]
            
            # Aplicar relaciones de grupos vinculados
            for target_group, source_group in self.linked_groups.items():
                start_source = source_group * frames_per_group
                end_source = start_source + frames_per_group
                source_values = sprites[start_source:end_source]
                
                start_target = target_group * frames_per_group
                end_target = start_target + frames_per_group
                sprites[start_target:end_target] = source_values  # Sobrescribir con valores del grupo fuente
            
            # Crear la estructura de sprites con el nuevo formato
            grouped_sprites = []
            for group_idx, group_name in enumerate(group_names):
                start = group_idx * frames_per_group
                end = start + frames_per_group
                group_values = sprites[start:end]
                
                # Determinar si el grupo está "mirrored"
                mirrored = group_idx in self.linked_groups
                
                # Añadir el grupo al array de sprites
                grouped_sprites.append({
                    "name": group_name,
                    "mirrored": mirrored,
                    "values": group_values
                })
            
            # Crear estructura JSON
            json_data = {
                "index": self.current_anim_index,
                "name": anim["name"],
                "framewidth": anim["frame_width"],
                "frameheight": anim["frame_height"],
                "sprites": grouped_sprites,  # Nuevo formato de sprites
                "durations": anim["durations"]
            }
            
            # Guardar archivo
            folder_name = os.path.basename(self.anim_folder) + "AnimationData"
            output_folder = os.path.join(self.anim_folder, folder_name)
            os.makedirs(output_folder, exist_ok=True)
            
            filename = f"{anim['name']}-AnimData.json"
            output_path = os.path.join(output_folder, filename)
            
            with open(output_path, 'w') as f:
                json.dump(json_data, f, indent=4)
            
            messagebox.showinfo("Éxito", f"JSON guardado en:\n{output_path}")
        
        except ValueError as e:
            messagebox.showerror("Error", f"Valores inválidos: {str(e)}")
        except Exception as e:
            messagebox.showerror("Error", f"Error al guardar: {str(e)}")

    def load_json_data(self, anim_name):
        """Cargar datos del archivo JSON si existe."""
        folder_name = os.path.basename(self.anim_folder) + "AnimationData"
        json_path = os.path.join(self.anim_folder, folder_name, f"{anim_name}-AnimData.json")
        
        if not os.path.exists(json_path):
            return None  # No existe el archivo JSON
        
        try:
            with open(json_path, 'r') as f:
                json_data = json.load(f)
            
            # Verificar si el JSON tiene el nuevo formato
            if "sprites" in json_data and isinstance(json_data["sprites"], list):
                # Crear una estructura compatible con el código existente
                group_data = []
                for group in json_data["sprites"]:
                    group_name = group.get("name", f"grupo{len(group_data) + 1}")
                    sprite_values = group.get("values", [])
                    group_data.append({group_name: sprite_values})
                
                # Devolver los datos en el formato esperado
                return {
                    "sprites": group_data,
                    "durations": json_data.get("durations", [])
                }
            else:
                # Si el JSON no tiene el nuevo formato, devolver None
                return None
        
        except Exception as e:
            print(f"Error loading JSON: {str(e)}")
            return None