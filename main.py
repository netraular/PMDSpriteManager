import os
from tkinter import Tk, filedialog, Button, Label
from PIL import Image, ImageTk
import xml.etree.ElementTree as ET
from sprite_sheet_handler import SpriteSheetHandler

class AnimationViewer:
    def __init__(self, root, anim_folder):
        self.root = root
        self.anim_folder = anim_folder
        self.anim_data = self.load_anim_data()
        self.current_anim_index = 0
        self.current_frame_index = 0
        self.frames = []
        self.frame_images = []  # Almacenar referencias a las imágenes

        # Create UI elements
        self.frame_label = Label(root)
        self.frame_label.pack()

        self.next_button = Button(root, text="Siguiente Animación", command=self.next_animation)
        self.next_button.pack()

        # Start displaying animations
        self.show_animation()

    def load_anim_data(self):
        """
        Load and parse the AnimData.xml file from the 'sprite' subfolder.
        """
        sprite_folder = os.path.join(self.anim_folder, "sprite")
        if not os.path.exists(sprite_folder):
            raise FileNotFoundError(f"No se encontró la subcarpeta 'sprite' en {self.anim_folder}")

        anim_data_path = os.path.join(sprite_folder, "AnimData.xml")
        print(f"Intentando abrir el archivo: {anim_data_path}")  # Debug: Mostrar la ruta del archivo

        if not os.path.exists(anim_data_path):
            raise FileNotFoundError(f"No se encontró el archivo AnimData.xml en {sprite_folder}")

        tree = ET.parse(anim_data_path)
        root = tree.getroot()

        anims = []
        for anim in root.find("Anims"):
            name = anim.find("Name").text
            frame_width = anim.find("FrameWidth")
            frame_height = anim.find("FrameHeight")

            # Handle missing FrameWidth or FrameHeight
            frame_width_value = int(frame_width.text) if frame_width is not None else None
            frame_height_value = int(frame_height.text) if frame_height is not None else None

            anims.append({
                "name": name,
                "frame_width": frame_width_value,
                "frame_height": frame_height_value,
                "image_path": os.path.join(sprite_folder, f"{name}-Anim.png")
            })

        # Mostrar los datos de las animaciones por terminal
        print("Datos de las animaciones cargados:")
        for anim in anims:
            print(f"Nombre: {anim['name']}, FrameWidth: {anim['frame_width']}, FrameHeight: {anim['frame_height']}")

        return anims

    def show_animation(self):
        """
        Show the current animation frames.
        """
        if self.current_anim_index >= len(self.anim_data):
            print("No hay más animaciones para mostrar.")
            return

        anim = self.anim_data[self.current_anim_index]
        image_path = anim["image_path"]

        if not os.path.exists(image_path):
            print(f"No se encontró la imagen de animación: {image_path}")
            self.next_animation()
            return

        # Load the animation image using SpriteSheetHandler
        sprite_handler = SpriteSheetHandler(image_path)
        self.frames = sprite_handler.split_animation_frames(anim["frame_width"], anim["frame_height"])

        # Clear previous frame images
        self.frame_images.clear()

        # Display the first frame
        self.current_frame_index = 0
        self.show_frame()

    def show_frame(self):
        """
        Display the current frame.
        """
        if self.current_frame_index >= len(self.frames):
            self.next_animation()
            return

        frame = self.frames[self.current_frame_index]
        frame_image = ImageTk.PhotoImage(frame)

        # Almacenar la referencia a la imagen actual
        self.frame_images.append(frame_image)

        # Mostrar la imagen en el Label
        self.frame_label.config(image=frame_image)
        self.frame_label.image = frame_image  # Mantener una referencia para evitar garbage collection

        # Schedule the next frame
        self.current_frame_index += 1
        self.root.after(100, self.show_frame)  # Cambiar de frame cada 100 ms

    def next_animation(self):
        """
        Move to the next animation.
        """
        self.current_anim_index += 1
        if self.current_anim_index < len(self.anim_data):
            self.show_animation()
        else:
            print("Todas las animaciones han sido mostradas.")

def seleccionar_carpeta():
    """
    Open a dialog to select a folder and process the sprite sheet.
    """
    root = Tk()
    root.withdraw()

    # Open a dialog to select a folder
    carpeta_seleccionada = filedialog.askdirectory(title="Selecciona una carpeta")

    if carpeta_seleccionada:
        # Find all PNG files in the selected folder
        archivos_png = [archivo for archivo in os.listdir(carpeta_seleccionada) if archivo.lower().endswith('.png')]

        if archivos_png:
            # Get the path of the first PNG file
            ruta_imagen = os.path.join(carpeta_seleccionada, archivos_png[0])

            # Open and display the original image
            from PIL import Image
            imagen_original = Image.open(ruta_imagen)
            imagen_original.show()  # Show the original image

            # Ask the user for the number of sprites horizontally and vertically
            try:
                sprites_ancho = int(input("Introduce el número de sprites de ancho: "))
                sprites_alto = int(input("Introduce el número de sprites de alto: "))

                # Initialize the SpriteSheetHandler with the image path and remove_first_row_and_col=True
                sprite_handler = SpriteSheetHandler(ruta_imagen, remove_first_row_and_col=True)

                # Split the sprite sheet into individual sprites
                sprites, ancho_sprite, alto_sprite = sprite_handler.split_sprites(sprites_ancho, sprites_alto)

                # Create a new folder to save the sprites
                nombre_carpeta_original = os.path.basename(carpeta_seleccionada)
                carpeta_edited = os.path.join(carpeta_seleccionada, nombre_carpeta_original + "Edited")
                os.makedirs(carpeta_edited, exist_ok=True)

                # Save the sprites to the output folder
                sprite_handler.save_sprites(sprites, carpeta_edited, nombre_carpeta_original)

                # Display the sprites in a grid
                sprite_handler.display_sprites(sprites, sprites_ancho, sprites_alto, ancho_sprite, alto_sprite)

                # Open the AnimData.xml file and display animations
                anim_folder = carpeta_seleccionada  # Use the selected folder
                anim_viewer_root = Tk()
                anim_viewer = AnimationViewer(anim_viewer_root, anim_folder)
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