import os
from tkinter import Toplevel, Label, simpledialog, messagebox
from PIL import Image, ImageTk
from sprite_sheet_handler import SpriteSheetHandler

class SpriteSplitter:
    def __init__(self, carpeta):
        self.carpeta = carpeta
        self.sprites_ancho = None
        self.sprites_alto = None
        self.ruta_imagen = None
        
    def seleccionar_imagen(self):
        """Seleccionar la imagen del spritesheet"""
        archivos_png = [f for f in os.listdir(self.carpeta) if f.lower().endswith('.png')]
        if not archivos_png:
            raise FileNotFoundError("No se encontraron archivos PNG en la carpeta")
        
        self.ruta_imagen = os.path.join(self.carpeta, archivos_png[0])
        return self.ruta_imagen

    def mostrar_imagen(self, ruta_imagen):
        """Mostrar la imagen del spritesheet en una ventana"""
        ventana = Toplevel()
        ventana.title("Spritesheet Original")
        
        img = Image.open(ruta_imagen)
        img.thumbnail((800, 800))  # Redimensionar para que quepa en la pantalla
        img_tk = ImageTk.PhotoImage(img)
        
        label = Label(ventana, image=img_tk)
        label.image = img_tk  # Mantener referencia para evitar garbage collection
        label.pack(padx=10, pady=10)
        
        return ventana

    def pedir_dimensiones(self, ventana):
        """Obtener dimensiones mediante diálogos"""
        self.sprites_ancho = simpledialog.askinteger("Entrada", "Número de sprites de ancho:", parent=ventana)
        self.sprites_alto = simpledialog.askinteger("Entrada", "Número de sprites de alto:", parent=ventana)
        
        if not self.sprites_ancho or not self.sprites_alto:
            raise ValueError("Debes introducir valores válidos para las dimensiones")

    def procesar_spritesheet(self):
        """Realizar todo el proceso de división y guardado"""
        handler = SpriteSheetHandler(self.ruta_imagen, remove_first_row_and_col=True)
        sprites, ancho, alto = handler.split_sprites(self.sprites_ancho, self.sprites_alto)
        
        # Crear y guardar en carpeta
        nombre_carpeta = os.path.basename(self.carpeta) + "Edited"
        carpeta_edited = os.path.join(self.carpeta, nombre_carpeta)
        os.makedirs(carpeta_edited, exist_ok=True)
        handler.save_sprites(sprites, carpeta_edited, nombre_carpeta)
        
        # Mostrar resultado
        handler.display_sprites(sprites, self.sprites_ancho, self.sprites_alto, ancho, alto)
        return carpeta_edited