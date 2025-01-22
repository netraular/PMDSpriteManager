import os
from tkinter import Tk, filedialog, Button, Label, Toplevel, Frame
from PIL import Image, ImageTk
import xml.etree.ElementTree as ET
from sprite_sheet_handler import SpriteSheetHandler

class AnimationViewer:
    def __init__(self, root, anim_folder):
        self.root = root
        self.anim_folder = anim_folder
        self.sprite_folder = os.path.join(anim_folder, "sprite")
        self.anim_data = self.load_anim_data()
        self.current_anim_index = 0
        
        # Configurar ventana
        self.root.title("Visor de Animaciones")
        
        # Configurar el protocolo de cierre para terminar el programa
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Panel de control
        control_frame = Frame(root)
        control_frame.pack(pady=10)
        
        self.prev_button = Button(control_frame, text="Animación Anterior", command=self.prev_animation)
        self.prev_button.pack(side="left", padx=5)
        
        self.next_button = Button(control_frame, text="Siguiente Animación", command=self.next_animation)
        self.next_button.pack(side="left", padx=5)
        
        # Etiqueta para el nombre de la animación
        self.anim_name_label = Label(root, text="", font=('Arial', 12, 'bold'))
        self.anim_name_label.pack(pady=5)
        
        # Contenedor para los frames
        self.frames_container = Frame(root)
        self.frames_container.pack(pady=10)
        
        # Mostrar primera animación
        self.show_animation()

    def load_anim_data(self):
        """Cargar y parsear el archivo AnimData.xml"""
        anim_data_path = os.path.join(self.sprite_folder, "AnimData.xml")
        
        if not os.path.exists(anim_data_path):
            raise FileNotFoundError(f"No se encontró AnimData.xml en {self.sprite_folder}")

        tree = ET.parse(anim_data_path)
        root = tree.getroot()

        anims = []
        for anim in root.find("Anims"):
            name = anim.find("Name").text
            frame_width = int(anim.find("FrameWidth").text) if anim.find("FrameWidth") is not None else None
            frame_height = int(anim.find("FrameHeight").text) if anim.find("FrameHeight") is not None else None

            anims.append({
                "name": name,
                "frame_width": frame_width,
                "frame_height": frame_height,
                "image_path": os.path.join(self.sprite_folder, f"{name}-Anim.png")
            })

        return anims

    def clear_frames(self):
        """Limpiar los frames anteriores"""
        for widget in self.frames_container.winfo_children():
            widget.destroy()

    def show_animation(self):
        """Mostrar la animación actual"""
        self.clear_frames()
        
        if self.current_anim_index >= len(self.anim_data):
            return

        anim = self.anim_data[self.current_anim_index]
        self.anim_name_label.config(text=f"Animación: {anim['name']}")

        if not os.path.exists(anim["image_path"]):
            print(f"Archivo no encontrado: {anim['image_path']}")
            return

        # Cargar y dividir la animación
        handler = SpriteSheetHandler(anim["image_path"])
        frames = handler.split_animation_frames(anim["frame_width"], anim["frame_height"])

        # Mostrar los frames en una rejilla
        row = 0
        col = 0
        max_cols = 4  # Máximo de columnas antes de nueva fila
        
        for idx, frame in enumerate(frames):
            if col >= max_cols:
                row += 1
                col = 0
            
            frame.thumbnail((100, 100))  # Redimensionar para previsualización
            img = ImageTk.PhotoImage(frame)
            
            frame_frame = Frame(self.frames_container, bd=2, relief="groove")
            frame_frame.grid(row=row, column=col, padx=5, pady=5)
            
            label = Label(frame_frame, image=img)
            label.image = img  # Mantener referencia
            label.pack(padx=2, pady=2)
            
            Label(frame_frame, text=f"Frame {idx + 1}", font=('Arial', 8)).pack()
            
            col += 1

    def next_animation(self):
        """Siguiente animación"""
        self.current_anim_index += 1
        if self.current_anim_index >= len(self.anim_data):
            self.current_anim_index = 0
        self.show_animation()

    def prev_animation(self):
        """Animación anterior"""
        self.current_anim_index -= 1
        if self.current_anim_index < 0:
            self.current_anim_index = len(self.anim_data) - 1
        self.show_animation()

    def on_close(self):
        """Manejar el cierre de la ventana"""
        self.root.destroy()  # Cerrar la ventana
        self.root.quit()     # Salir del bucle principal

def seleccionar_carpeta():
    """
    Abre un diálogo para seleccionar una carpeta y procesar el sprite sheet.
    """
    root = Tk()
    root.withdraw()

    # Abrir un diálogo para seleccionar una carpeta
    carpeta_seleccionada = filedialog.askdirectory(title="Selecciona una carpeta")

    if carpeta_seleccionada:
        # Buscar todos los archivos PNG en la carpeta seleccionada
        archivos_png = [archivo for archivo in os.listdir(carpeta_seleccionada) if archivo.lower().endswith('.png')]

        if archivos_png:
            # Obtener la ruta del primer archivo PNG
            ruta_imagen = os.path.join(carpeta_seleccionada, archivos_png[0])

            # Abrir y mostrar la imagen original
            imagen_original = Image.open(ruta_imagen)
            imagen_original.show()  # Mostrar la imagen original

            # Preguntar al usuario por el número de sprites horizontal y vertical
            try:
                sprites_ancho = int(input("Introduce el número de sprites de ancho: "))
                sprites_alto = int(input("Introduce el número de sprites de alto: "))

                # Inicializar el SpriteSheetHandler con la ruta de la imagen y remove_first_row_and_col=True
                sprite_handler = SpriteSheetHandler(ruta_imagen, remove_first_row_and_col=True)

                # Dividir el sprite sheet en sprites individuales
                sprites, ancho_sprite, alto_sprite = sprite_handler.split_sprites(sprites_ancho, sprites_alto)

                # Crear una nueva carpeta para guardar los sprites
                nombre_carpeta_original = os.path.basename(carpeta_seleccionada)
                carpeta_edited = os.path.join(carpeta_seleccionada, nombre_carpeta_original + "Edited")
                os.makedirs(carpeta_edited, exist_ok=True)

                # Guardar los sprites en la carpeta de salida
                sprite_handler.save_sprites(sprites, carpeta_edited, nombre_carpeta_original)

                # Mostrar los sprites en una cuadrícula
                sprite_handler.display_sprites(sprites, sprites_ancho, sprites_alto, ancho_sprite, alto_sprite)

                # Abrir el archivo AnimData.xml y mostrar las animaciones
                anim_viewer_root = Toplevel()
                anim_viewer = AnimationViewer(anim_viewer_root, carpeta_seleccionada)
                anim_viewer_root.mainloop()

            except ValueError:
                print("Error: Debes introducir números enteros para los sprites de ancho y alto.")
            except FileNotFoundError as e:
                print(e)
            except Exception as e:
                print(f"Error inesperado: {e}")
        else:
            print(f"No se encontraron archivos PNG en la carpeta seleccionada.")
    else:
        print("No se seleccionó ninguna carpeta.")

if __name__ == "__main__":
    seleccionar_carpeta()