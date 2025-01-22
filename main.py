import os
from tkinter import Tk, filedialog, Toplevel, Frame, Label, Button, messagebox
from sprite_splitter import SpriteSplitter
from animation_viewer import AnimationViewer

class IntermediateScreen:
    def __init__(self, master, carpeta):
        self.master = master
        self.carpeta = carpeta
        self.configurar_interfaz()

    def configurar_interfaz(self):
        """Configurar elementos visuales de la pantalla"""
        self.master.title("Selección de Acción")
        main_frame = Frame(self.master, padx=20, pady=20)
        main_frame.pack()
        
        Label(main_frame, text=f"Carpeta seleccionada:\n{self.carpeta}", 
             font=('Arial', 12)).pack(pady=10)
        
        Button(main_frame, text="Dividir Spritesheet", 
              command=self.iniciar_division_sprites, width=20).pack(pady=5)
        Button(main_frame, text="Ver Animaciones", 
              command=self.iniciar_visor_animaciones, width=20).pack(pady=5)

    def iniciar_division_sprites(self):
        """Manejar el proceso de división de sprites"""
        try:
            splitter = SpriteSplitter(self.carpeta)
            ruta_imagen = splitter.seleccionar_imagen()
            ventana_imagen = splitter.mostrar_imagen(ruta_imagen)
            
            # Pedir dimensiones después de mostrar la imagen
            splitter.pedir_dimensiones(ventana_imagen)
            carpeta_edited = splitter.procesar_spritesheet()
            
            # Mostrar mensaje de éxito
            messagebox.showinfo("Éxito", f"Sprites guardados en:\n{carpeta_edited}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al procesar sprites:\n{str(e)}")

    def iniciar_visor_animaciones(self):
        """Iniciar el visor de animaciones"""
        try:
            if not os.path.exists(os.path.join(self.carpeta, "sprite", "AnimData.xml")):
                raise FileNotFoundError("Estructura de animaciones no encontrada")
            
            anim_root = Toplevel()
            AnimationViewer(anim_root, self.carpeta)
            self.master.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"No se puede iniciar el visor:\n{str(e)}")

def seleccionar_carpeta():
    root = Tk()
    root.withdraw()
    carpeta = filedialog.askdirectory(title="Selecciona una carpeta")
    
    if carpeta:
        top = Toplevel()
        IntermediateScreen(top, carpeta)
        root.mainloop()
    else:
        print("No se seleccionó ninguna carpeta")

if __name__ == "__main__":
    seleccionar_carpeta()