from tkinter import messagebox
import os
from PIL import Image
from sprite_sheet_handler import SpriteSheetHandler

class SpriteSplitter:
    def __init__(self, carpeta):
        self.carpeta = carpeta
        self.sprites_ancho = None
        self.sprites_alto = None
        self.ruta_imagen = None
        
    def seleccionar_imagen(self):
        archivos_png = [f for f in os.listdir(self.carpeta) if f.lower().endswith('.png')]
        if not archivos_png:
            raise FileNotFoundError("No se encontraron archivos PNG en la carpeta")
        
        self.ruta_imagen = os.path.join(self.carpeta, archivos_png[0])
        return self.ruta_imagen