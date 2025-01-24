from tkinter import Frame, Label, Button, Entry, Canvas, Scrollbar, messagebox, filedialog
from PIL import Image, ImageTk, ImageOps
from sprite_sheet_handler import SpriteSheetHandler
import os
import json
import math

class AnimationCreator:
    def __init__(self, parent_frame, return_to_main_callback):
        self.parent_frame = parent_frame
        self.return_to_main = return_to_main_callback
        self.current_frame = parent_frame
        self.sprites = []
        self.sprite_folder = None
        self.json_data = None
        self.after_ids = []
        
        # Frame superior para el botón "Main Menu"
        self.top_frame = Frame(self.parent_frame)
        self.top_frame.pack(fill='x', padx=10, pady=5)
        
        # Botón "Main Menu"
        Button(self.top_frame, text="Main Menu", 
            command=self.return_to_main).pack(side='left')
        
        # Frame principal para las vistas (Step 1, Step 2, Animation Preview)
        self.main_frame = Frame(self.parent_frame)
        self.main_frame.pack(fill='both', expand=True)
        
        self.setup_ui()
        
    def setup_ui(self):
        """Configurar la interfaz paso a paso"""
        self.clear_frame()
        
        # Controles superiores
        self.control_frame = Frame(self.main_frame)
        self.control_frame.pack(fill='x', padx=10, pady=5)
        Button(self.control_frame, text="Main Menu", 
             command=self.return_to_main).pack(side='left')
        
        # Pantalla inicial
        self.show_upload_sheet_view()

    def show_upload_sheet_view(self):
        """Mostrar el Step 1: Subir spritesheet y configurar sprites"""
        self.clear_frame()
        
        # Crear el frame para el Step 1
        self.upload_frame = Frame(self.main_frame)
        self.upload_frame.pack(pady=20)
        
        Label(self.upload_frame, text="Step 1: Upload Spritesheet", 
            font=('Arial', 14)).pack(pady=10)
        
        Button(self.upload_frame, text="Select Image", 
            command=self.load_spritesheet).pack(pady=10)
        
        # Campos para dimensiones
        form_frame = Frame(self.upload_frame)
        form_frame.pack(pady=10)
        
        Label(form_frame, text="Sprites Width:").grid(row=0, column=0)
        self.width_entry = Entry(form_frame)
        self.width_entry.grid(row=0, column=1, padx=5)
        
        Label(form_frame, text="Sprites Height:").grid(row=1, column=0)
        self.height_entry = Entry(form_frame)
        self.height_entry.grid(row=1, column=1, padx=5)
        
        # Nuevo campo para el número de sprites a guardar
        Label(form_frame, text="Number of Sprites to Save:").grid(row=2, column=0)
        self.sprite_number_entry = Entry(form_frame)
        self.sprite_number_entry.grid(row=2, column=1, padx=5)
        
        Button(form_frame, text="Generate Sprites", 
            command=self.process_spritesheet).grid(row=3, columnspan=2, pady=10)

    def process_spritesheet(self):
        """Procesar el spritesheet y generar sprites individuales"""
        try:
            # Obtener los valores del formulario
            sprites_width = int(self.width_entry.get())
            sprites_height = int(self.height_entry.get())
            sprite_number = int(self.sprite_number_entry.get())
            
            # Guardar los valores de ancho y alto
            self.saved_width = sprites_width
            self.saved_height = sprites_height
            
            # Verificar que el número de sprites sea válido
            total_sprites = sprites_width * sprites_height
            if sprite_number > total_sprites:
                messagebox.showerror("Error", f"Cannot save {sprite_number} sprites. "
                                        f"The spritesheet only contains {total_sprites} sprites.")
                return
            
            # Ruta de la carpeta TempSprites
            self.sprite_folder = os.path.join(os.path.dirname(self.image_path), "TempSprites")
            
            # Verificar si la carpeta TempSprites ya existe y contiene archivos
            if os.path.exists(self.sprite_folder) and os.listdir(self.sprite_folder):
                # Preguntar al usuario si desea borrar los archivos existentes
                response = messagebox.askyesno(
                    "Confirmación",
                    "La carpeta TempSprites ya contiene archivos. ¿Desea borrarlos y continuar?"
                )
                if not response:  # Si el usuario elige "No" o cierra la ventana
                    return  # Mantener la vista del formulario en el Step 1
            
            # Crear la carpeta TempSprites (si no existe) y borrar archivos si el usuario lo confirmó
            os.makedirs(self.sprite_folder, exist_ok=True)
            if os.path.exists(self.sprite_folder):
                for file in os.listdir(self.sprite_folder):
                    file_path = os.path.join(self.sprite_folder, file)
                    try:
                        if os.path.isfile(file_path):
                            os.unlink(file_path)  # Borrar el archivo
                    except Exception as e:
                        print(f"Error al borrar {file_path}: {e}")
            
            # Procesar el spritesheet
            handler = SpriteSheetHandler(self.image_path, remove_first_row_and_col=True)
            self.sprites, self.sprite_width, self.sprite_height = handler.split_sprites(
                sprites_width, sprites_height
            )
            
            # Limitar el número de sprites
            self.sprites = self.sprites[:sprite_number]
            
            # Guardar sprites temporalmente
            for idx, sprite in enumerate(self.sprites):
                sprite.save(os.path.join(self.sprite_folder, f"sprite_{idx + 1}.png"))
            
            # Mostrar siguiente paso
            self.show_json_upload_view()
            
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numeric values")
        except Exception as e:
            messagebox.showerror("Error", f"Processing error: {str(e)}")

    def show_json_upload_view(self):
        """Mostrar el Step 2: Subir JSON de animaciones y mostrar sprites generados"""
        self.clear_frame()
        
        # Crear el frame para el Step 2
        self.json_frame = Frame(self.main_frame)
        self.json_frame.pack(pady=20, fill='both', expand=True)
        
        # Botones superiores
        button_frame = Frame(self.json_frame)
        button_frame.pack(fill='x', pady=10)
        
        Button(button_frame, text="Back", 
            command=self.show_upload_sheet_view).pack(side='left', padx=5)
        Button(button_frame, text="Select JSON File", 
            command=self.load_json).pack(side='left', padx=5)
        Button(button_frame, text="Download Sprites", 
            command=self.download_sprites).pack(side='left', padx=5)
        
        # Mostrar los sprites generados
        self.show_generated_sprites()

    def show_generated_sprites(self):
        """Mostrar los sprites generados en una cuadrícula con el mismo ancho y alto del formulario"""
        if not self.sprite_folder or not hasattr(self, 'sprite_width') or not hasattr(self, 'sprite_height'):
            return  # No hay sprites generados o no se han calculado las dimensiones
        
        # Obtener la lista de archivos de sprites
        sprite_files = sorted(
            [f for f in os.listdir(self.sprite_folder) if f.lower().endswith('.png')],
            key=lambda x: int(x.split('_')[-1].split('.')[0])  # Ordenar por número
        )
        
        # Crear un frame para los sprites
        sprite_display_frame = Frame(self.main_frame)
        sprite_display_frame.pack(fill='both', expand=True, pady=10)
        
        # Obtener el número de columnas (ancho introducido en el formulario)
        num_columns = self.saved_width  # Usar el valor guardado
        row, col = 0, 0
        
        for sprite_file in sprite_files:
            sprite_path = os.path.join(self.sprite_folder, sprite_file)
            sprite = Image.open(sprite_path)
            
            # Redimensionar el sprite para la vista previa (manteniendo la relación de aspecto)
            sprite.thumbnail((self.sprite_width, self.sprite_height))
            img_tk = ImageTk.PhotoImage(sprite)
            
            # Crear un frame para cada sprite
            sprite_frame = Frame(sprite_display_frame)
            sprite_frame.grid(row=row, column=col, padx=5, pady=5)
            
            # Mostrar la imagen del sprite
            label = Label(sprite_frame, image=img_tk)
            label.image = img_tk  # Guardar referencia para evitar garbage collection
            label.pack()
            
            # Mostrar el nombre del sprite debajo de la imagen
            Label(sprite_frame, text=sprite_file, font=('Arial', 8)).pack()
            
            # Actualizar la posición en la cuadrícula
            col += 1
            if col >= num_columns:
                col = 0
                row += 1

    def load_spritesheet(self):
        """Cargar imagen spritesheet"""
        file_path = filedialog.askopenfilename(
            title="Select Spritesheet",
            filetypes=(("PNG files", "*.png"), ("All files", "*.*"))
        )
        if file_path:
            self.image_path = file_path
            self.display_image_preview()

    def display_image_preview(self):
        """Mostrar vista previa de la imagen"""
        img = Image.open(self.image_path)
        img.thumbnail((400, 300))
        self.img_tk = ImageTk.PhotoImage(img)
        Label(self.upload_frame, image=self.img_tk).pack(pady=10)

    def load_json(self):
        """Cargar archivo JSON de animaciones"""
        file_path = filedialog.askopenfilename(
            title="Select Animation JSON",
            filetypes=(("JSON files", "*.json"), ("All files", "*.*"))
        )
        if file_path:
            with open(file_path, 'r') as f:
                self.json_data = json.load(f)
            self.show_animation_preview()

    def download_sprites(self):
        """Descargar sprites generados"""
        if not self.sprite_folder:
            messagebox.showwarning("Warning", "Generate sprites first")
            return
            
        output_folder = filedialog.askdirectory(title="Select Download Folder")
        if output_folder:
            for file in os.listdir(self.sprite_folder):
                src = os.path.join(self.sprite_folder, file)
                dst = os.path.join(output_folder, file)
                with open(src, 'rb') as f_src, open(dst, 'wb') as f_dst:
                    f_dst.write(f_src.read())
            messagebox.showinfo("Success", f"Sprites saved in:\n{output_folder}")

    def show_animation_preview(self):
        """Mostrar la vista de previsualización de animaciones"""
        self.clear_frame()
        
        # Crear el frame para la vista de previsualización
        self.animation_frame = Frame(self.main_frame)
        self.animation_frame.pack(fill='both', expand=True)
        
        # Configurar canvas con scroll
        self.canvas = Canvas(self.animation_frame)
        self.scrollbar = Scrollbar(self.animation_frame, orient="vertical", command=self.canvas.yview)
        self.scroll_frame = Frame(self.canvas)
        
        self.scroll_frame.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")
        ))
        
        self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Botón para volver al Step 2
        back_button = Button(self.scroll_frame, text="Back", 
                        command=self.show_json_upload_view)
        back_button.pack(pady=10)
        
        # Mostrar animaciones
        Label(self.scroll_frame, text="Animation Preview", 
            font=('Arial', 16)).pack(pady=10)
        
        for group_id, group_data in self.json_data["sprites"].items():
            self.create_group_preview(group_id, group_data)

    def create_group_preview(self, group_id, group_data):
        """Crear vista previa para un grupo de animación"""
        group_frame = Frame(self.scroll_frame, bd=2, relief="groove")
        group_frame.pack(fill="x", padx=5, pady=5)
        
        # Encabezado del grupo
        header_frame = Frame(group_frame)
        header_frame.pack(fill="x", pady=5)
        
        group_name = group_data.get("name", f"Group {group_id}")
        Label(header_frame, text=group_name, 
            font=('Arial', 12, 'bold')).pack(side='left')
        
        if group_data.get("mirrored", False):
            Label(header_frame, text="(Mirrored)", 
                fg="blue").pack(side='left', padx=10)
        
        # Contenido de la animación
        content_frame = Frame(group_frame)
        content_frame.pack(fill="x")
        
        # Obtener frames del grupo
        frames = self.get_group_frames(group_data)
        durations = self.json_data["durations"]
        
        # Panel de animación
        anim_panel = Frame(content_frame)
        anim_panel.pack(side="left", padx=10)
        
        anim_label = Label(anim_panel)
        anim_label.pack()
        self.start_animation(anim_label, frames, durations)
        
        # Panel de sprites
        sprite_panel = Frame(content_frame)
        sprite_panel.pack(side="right", fill="x", expand=True)
        
        for idx, frame in enumerate(frames):
            frame.thumbnail((80, 80))
            img = ImageTk.PhotoImage(frame)
            lbl = Label(sprite_panel, image=img)
            lbl.image = img
            lbl.grid(row=0, column=idx, padx=2)
            
            Label(sprite_panel, text=f"Dur: {durations[idx]}", 
                font=('Arial', 7)).grid(row=1, column=idx)

    def get_group_frames(self, group_data):
        """Obtener los frames para el grupo, aplicando mirror si es necesario"""
        if group_data.get("mirrored", False):
            source_group = self.json_data["sprites"][group_data["copy"]]
            frames = self.get_group_frames(source_group)
            return [ImageOps.mirror(frame) for frame in frames]
        else:
            sprite_numbers = group_data["values"]
            return [self.load_sprite(num) for num in sprite_numbers]

    def load_sprite(self, sprite_num):
        """Cargar sprite desde archivo generado"""
        sprite_path = os.path.join(self.sprite_folder, f"sprite_{sprite_num}.png")
        return Image.open(sprite_path)

    def start_animation(self, label, frames, durations):
        """Iniciar animación en tiempo real"""
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
            
    def clear_frame(self):
        """Limpiar el frame actual y detener animaciones"""
        # Detener todas las animaciones
        for aid in self.after_ids:
            self.parent_frame.after_cancel(aid)
        self.after_ids.clear()
        
        # Destruir todos los widgets del frame principal (excepto el top_frame)
        for widget in self.main_frame.winfo_children():
            widget.destroy()