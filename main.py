import os
from tkinter import Tk, filedialog
from sprite_sheet_handler import SpriteSheetHandler

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

                # Save the sprites to the output folder
                sprite_handler.save_sprites(sprites, carpeta_edited, nombre_carpeta_original)

                # Display the sprites in a grid
                sprite_handler.display_sprites(sprites, sprites_ancho, sprites_alto, ancho_sprite, alto_sprite)

            except ValueError:
                print("Error: Debes introducir números enteros para los sprites de ancho y alto.")
        else:
            print(f"No se encontraron archivos PNG en la carpeta seleccionada.")
    else:
        print("No se seleccionó ninguna carpeta.")

if __name__ == "__main__":
    seleccionar_carpeta()