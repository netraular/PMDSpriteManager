import os
from tkinter import Tk, filedialog, Frame, Label, Button, messagebox, Entry, Canvas, Scrollbar
from PIL import Image, ImageTk
from sprite_sheet_handler import SpriteSheetHandler  # Importación añadida
from sprite_splitter import SpriteSplitter
from animation_viewer import AnimationViewer

class MainApplication:
    def __init__(self, root):
        self.root = root
        self.root.title("Sprite Sheet Tool")
        self.root.geometry("800x600")
        self.current_frame = None
        self.carpeta = None
        self.sprites = []
        
        self.show_folder_selection()

    def clear_frame(self):
        if self.current_frame:
            self.current_frame.destroy()
        self.current_frame = Frame(self.root)
        self.current_frame.pack(fill='both', expand=True)

    def show_folder_selection(self):
        self.clear_frame()
        Label(self.current_frame, 
             text="Selecciona la carpeta con la imagen del spritesheet\n y la subcarpeta con las animaciones",
             font=('Arial', 14)).pack(pady=50)
        Button(self.current_frame, text="Seleccionar Carpeta", 
              command=self.seleccionar_carpeta, font=('Arial', 12)).pack()

    def seleccionar_carpeta(self):
        carpeta = filedialog.askdirectory(title="Selecciona una carpeta")
        if carpeta:
            self.carpeta = carpeta
            self.show_main_menu()

    def show_main_menu(self):
        self.clear_frame()
        Label(self.current_frame, text=f"Carpeta seleccionada:\n{self.carpeta}", 
             font=('Arial', 12)).pack(pady=20)
        
        Button(self.current_frame, text="Dividir Spritesheet", 
              command=self.show_sprite_splitter, width=20).pack(pady=10)
        Button(self.current_frame, text="Ver Animaciones", 
              command=self.show_animation_viewer, width=20).pack(pady=10)

    def show_sprite_splitter(self):
        self.clear_frame()
        
        # Botones superiores
        control_frame = Frame(self.current_frame)
        control_frame.pack(fill='x', padx=10, pady=5)
        Button(control_frame, text="Menú Principal", 
              command=self.show_main_menu).pack(side='left')
        Button(control_frame, text="Guardar Sprites", 
              command=self.guardar_sprites).pack(side='right')

        try:
            self.splitter = SpriteSplitter(self.carpeta)
            self.ruta_imagen = self.splitter.seleccionar_imagen()
            
            # Mostrar imagen
            img = Image.open(self.ruta_imagen)
            img.thumbnail((600, 400))
            self.img_tk = ImageTk.PhotoImage(img)
            Label(self.current_frame, image=self.img_tk).pack(pady=10)
            
            # Inputs de dimensiones
            input_frame = Frame(self.current_frame)
            input_frame.pack(pady=10)
            
            Label(input_frame, text="Sprites de ancho:").grid(row=0, column=0)
            self.ancho_entry = Entry(input_frame)
            self.ancho_entry.grid(row=0, column=1, padx=5)
            
            Label(input_frame, text="Sprites de alto:").grid(row=1, column=0)
            self.alto_entry = Entry(input_frame)
            self.alto_entry.grid(row=1, column=1, padx=5)
            
            Button(input_frame, text="Procesar", 
                  command=self.procesar_spritesheet).grid(row=2, columnspan=2, pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Error: {str(e)}")
            self.show_main_menu()

    def procesar_spritesheet(self):
        try:
            sprites_ancho = int(self.ancho_entry.get())
            sprites_alto = int(self.alto_entry.get())
            
            handler = SpriteSheetHandler(self.ruta_imagen, True)
            self.sprites, ancho, alto = handler.split_sprites(sprites_ancho, sprites_alto)
            
            # Mostrar sprites con scroll
            canvas = Canvas(self.current_frame)
            scrollbar = Scrollbar(self.current_frame, orient="vertical", command=canvas.yview)
            scroll_frame = Frame(canvas)
            
            scroll_frame.bind("<Configure>", lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            ))
            
            canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            # Crear grid de sprites
            for i, sprite in enumerate(self.sprites):
                row = i // sprites_ancho
                col = i % sprites_ancho
                
                # Crear fondo gris
                bg = Image.new('RGBA', sprite.size, 'lightgray')
                composite = Image.alpha_composite(bg, sprite)
                composite.thumbnail((100, 100))
                
                img = ImageTk.PhotoImage(composite)
                lbl = Label(scroll_frame, image=img)
                lbl.image = img
                lbl.grid(row=row, column=col, padx=2, pady=2)

        except Exception as e:
            messagebox.showerror("Error", f"Error al procesar: {str(e)}")

    def guardar_sprites(self):
        if not self.sprites:
            messagebox.showwarning("Advertencia", "No hay sprites para guardar")
            return
            
        nombre_carpeta = os.path.basename(self.carpeta) + "Edited"
        carpeta_edited = os.path.join(self.carpeta, nombre_carpeta)
        
        # Crear la carpeta si no existe
        os.makedirs(carpeta_edited, exist_ok=True)
        
        # Guardar cada sprite
        for idx, sprite in enumerate(self.sprites):
            sprite.save(os.path.join(carpeta_edited, f"sprite_{idx + 1}.png"))
        
        messagebox.showinfo("Éxito", f"Sprites guardados en:\n{carpeta_edited}")

    def show_animation_viewer(self):
        self.clear_frame()
        
        # Botones superiores
        control_frame = Frame(self.current_frame)
        control_frame.pack(fill='x', padx=10, pady=5)
        Button(control_frame, text="Menú Principal", 
              command=self.show_main_menu).pack(side='left')
        Button(control_frame, text="Anterior", 
              command=lambda: self.anim_viewer.prev_animation()).pack(side='left', padx=5)
        Button(control_frame, text="Siguiente", 
              command=lambda: self.anim_viewer.next_animation()).pack(side='left', padx=5)

        try:
            self.anim_viewer = AnimationViewer(self.current_frame, self.carpeta)
        except Exception as e:
            messagebox.showerror("Error", f"No se pueden cargar animaciones: {str(e)}")
            self.show_main_menu()

if __name__ == "__main__":
    root = Tk()
    app = MainApplication(root)
    root.mainloop()