import os
from tkinter import Tk, filedialog, Frame, Label, Button, messagebox
from PIL import Image, ImageTk
from sprite_sheet_handler import SpriteSheetHandler
from animation_viewer import AnimationViewer
from spritesheet_viewer import SpritesheetViewer  # Importación actualizada

class MainApplication:
    def __init__(self, root):
        self.root = root
        self.root.title("Sprite Sheet Tool")
        self.root.geometry("800x600")
        self.current_frame = None
        self.carpeta = None
        self.spritesheet_viewer = None
        self.animation_viewer = None
        
        self.show_folder_selection()

    def clear_frame(self):
        """Limpia el frame actual"""
        if self.current_frame:
            self.current_frame.destroy()
        self.current_frame = Frame(self.root)
        self.current_frame.pack(fill='both', expand=True)

    def show_folder_selection(self):
        """Muestra la pantalla de selección de carpeta"""
        self.clear_frame()
        Label(self.current_frame, 
             text="Selecciona la carpeta con la imagen del spritesheet\n y la subcarpeta con las animaciones",
             font=('Arial', 14)).pack(pady=50)
        Button(self.current_frame, text="Seleccionar Carpeta", 
              command=self.seleccionar_carpeta, font=('Arial', 12)).pack()

    def seleccionar_carpeta(self):
        """Permite al usuario seleccionar una carpeta"""
        carpeta = filedialog.askdirectory(title="Selecciona una carpeta")
        if carpeta:
            self.carpeta = carpeta
            self.show_main_menu()

    def show_main_menu(self):
        """Muestra el menú principal"""
        self.clear_frame()
        Label(self.current_frame, text=f"Carpeta seleccionada:\n{self.carpeta}", 
             font=('Arial', 12)).pack(pady=20)
        
        Button(self.current_frame, text="Dividir Spritesheet", 
              command=self.show_sprite_splitter, width=20).pack(pady=10)
        Button(self.current_frame, text="Ver Animaciones", 
              command=self.show_animation_viewer, width=20).pack(pady=10)

    def show_sprite_splitter(self):
        """Muestra la vista de división de sprites"""
        self.clear_frame()
        self.spritesheet_viewer = SpritesheetViewer(
            self.current_frame, 
            self.carpeta, 
            self.show_main_menu
        )

    def show_animation_viewer(self):
        """Muestra la vista de animaciones"""
        self.clear_frame()
        
        # Botones superiores
        control_frame = Frame(self.current_frame)
        control_frame.pack(fill='x', padx=10, pady=5)
        Button(control_frame, text="Menú Principal", 
              command=self.show_main_menu).pack(side='left')
        Button(control_frame, text="Anterior", 
              command=lambda: self.animation_viewer.prev_animation()).pack(side='left', padx=5)
        Button(control_frame, text="Siguiente", 
              command=lambda: self.animation_viewer.next_animation()).pack(side='left', padx=5)

        try:
            self.animation_viewer = AnimationViewer(self.current_frame, self.carpeta)
        except Exception as e:
            messagebox.showerror("Error", f"No se pueden cargar animaciones: {str(e)}")
            self.show_main_menu()

if __name__ == "__main__":
    root = Tk()
    app = MainApplication(root)
    root.mainloop()