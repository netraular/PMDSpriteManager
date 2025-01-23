from tkinter import Frame, Label, Button, Entry, Canvas, Scrollbar, messagebox
from PIL import Image, ImageTk
from sprite_sheet_handler import SpriteSheetHandler
import os

class SpritesheetViewer:
    def __init__(self, parent_frame, carpeta, return_to_main_callback):
        self.parent_frame = parent_frame
        self.carpeta = carpeta
        self.return_to_main = return_to_main_callback
        self.sprites = []
        self.ruta_imagen = None
        self.current_frame = parent_frame
        
        # Valores de los campos de entrada
        self.sprites_ancho = None
        self.sprites_alto = None
        
        # Elementos de UI
        self.control_frame = None
        self.input_frame = None
        self.result_frame = None
        self.canvas = None
        self.scrollbar = None
        
        # Botones adicionales
        self.guardar_button = None
        self.repetir_button = None
        
        self.initialize_ui()
        
    def initialize_ui(self):
        """Inicializa todos los componentes de la UI"""
        self.create_control_frame()
        self.show_input_view()
    
    def create_control_frame(self):
        """Crea el frame de controles superiores"""
        self.control_frame = Frame(self.parent_frame)
        self.control_frame.pack(fill='x', padx=10, pady=5)
        
        # Botón de menú principal (siempre visible)
        Button(self.control_frame, text="Menú Principal", 
             command=self.return_to_main).pack(side='left')

    def show_input_view(self):
        """Muestra la vista inicial con el formulario"""
        # Limpiar frames anteriores
        if self.input_frame:
            self.input_frame.destroy()
        if self.result_frame:
            self.result_frame.destroy()
        
        # Ocultar botones adicionales
        if self.guardar_button:
            self.guardar_button.pack_forget()
        if self.repetir_button:
            self.repetir_button.pack_forget()
            
        self.input_frame = Frame(self.parent_frame)
        self.input_frame.pack(pady=20)
        
        try:
            # Cargar y mostrar imagen
            self.ruta_imagen = self.seleccionar_imagen()
            img = Image.open(self.ruta_imagen)
            img.thumbnail((600, 400))
            self.img_tk = ImageTk.PhotoImage(img)
            Label(self.input_frame, image=self.img_tk).pack(pady=10)
            
            # Formulario
            form_frame = Frame(self.input_frame)
            form_frame.pack(pady=10)
            
            Label(form_frame, text="Sprites de ancho:").grid(row=0, column=0)
            self.ancho_entry = Entry(form_frame)
            self.ancho_entry.grid(row=0, column=1, padx=5)
            
            Label(form_frame, text="Sprites de alto:").grid(row=1, column=0)
            self.alto_entry = Entry(form_frame)
            self.alto_entry.grid(row=1, column=1, padx=5)
            
            Button(form_frame, text="Procesar", 
                 command=self.procesar_spritesheet).grid(row=2, columnspan=2, pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Error: {str(e)}")
            self.return_to_main()

    def show_result_view(self):
        """Muestra la vista de resultados con los sprites"""
        # Limpiar frame de entrada
        self.input_frame.destroy()
        
        # Frame de resultados
        self.result_frame = Frame(self.parent_frame)
        self.result_frame.pack(fill='both', expand=True)
        
        # Mostrar botones adicionales
        self.guardar_button = Button(self.control_frame, text="Guardar Sprites", 
                                   command=self.guardar_sprites)
        self.guardar_button.pack(side='left', padx=5)
        
        self.repetir_button = Button(self.control_frame, text="Repetir", 
                                   command=self.show_input_view)
        self.repetir_button.pack(side='left', padx=5)
        
        # Mostrar sprites con scroll
        self.canvas = Canvas(self.result_frame)
        self.scrollbar = Scrollbar(self.result_frame, orient="vertical", command=self.canvas.yview)
        scroll_frame = Frame(self.canvas)
        
        scroll_frame.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")
        ))
        
        self.canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Crear grid de sprites
        for i, sprite in enumerate(self.sprites):
            row = i // self.sprites_ancho
            col = i % self.sprites_ancho
            
            bg = Image.new('RGBA', sprite.size, 'lightgray')
            composite = Image.alpha_composite(bg, sprite)
            composite.thumbnail((100, 100))
            
            img = ImageTk.PhotoImage(composite)
            lbl = Label(scroll_frame, image=img)
            lbl.image = img
            lbl.grid(row=row, column=col, padx=2, pady=2)

    def procesar_spritesheet(self):
        """Procesa el spritesheet y muestra los resultados"""
        try:
            # Guardar valores de los campos de entrada antes de destruir los widgets
            self.sprites_ancho = int(self.ancho_entry.get())
            self.sprites_alto = int(self.alto_entry.get())
            
            # Procesar el spritesheet
            handler = SpriteSheetHandler(self.ruta_imagen, True)
            self.sprites, ancho, alto = handler.split_sprites(self.sprites_ancho, self.sprites_alto)
            
            # Mostrar la vista de resultados
            self.show_result_view()
            
        except ValueError:
            messagebox.showerror("Error", "Por favor ingresa valores numéricos válidos")
        except Exception as e:
            messagebox.showerror("Error", f"Error al procesar: {str(e)}")

    def guardar_sprites(self):
        """Guarda los sprites recortados"""
        if not self.sprites:
            messagebox.showwarning("Advertencia", "No hay sprites para guardar")
            return
            
        nombre_carpeta = os.path.basename(self.carpeta) + "Edited"
        carpeta_edited = os.path.join(self.carpeta, nombre_carpeta)
        os.makedirs(carpeta_edited, exist_ok=True)
        
        for idx, sprite in enumerate(self.sprites):
            sprite.save(os.path.join(carpeta_edited, f"sprite_{idx + 1}.png"))
        
        messagebox.showinfo("Éxito", f"Sprites guardados en:\n{carpeta_edited}")

    def seleccionar_imagen(self):
        """Selecciona la primera imagen PNG en la carpeta"""
        archivos_png = [f for f in os.listdir(self.carpeta) if f.lower().endswith('.png')]
        if not archivos_png:
            raise FileNotFoundError("No se encontraron archivos PNG en la carpeta")
        return os.path.join(self.carpeta, archivos_png[0])