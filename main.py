import os
from tkinter import Tk, filedialog
from PIL import Image
import matplotlib.pyplot as plt

def seleccionar_carpeta():
    # Create a hidden Tkinter root window
    root = Tk()
    root.withdraw()

    # Open a dialog to select a folder
    carpeta_seleccionada = filedialog.askdirectory(title="Selecciona una carpeta")

    # Check if a folder was selected
    if carpeta_seleccionada:
        # Find all PNG files in the selected folder
        archivos_png = [archivo for archivo in os.listdir(carpeta_seleccionada) if archivo.lower().endswith('.png')]

        # Check if at least one PNG file was found
        if archivos_png:
            # Get the path of the first PNG file
            ruta_imagen = os.path.join(carpeta_seleccionada, archivos_png[0])
            # Open the image using Pillow
            imagen = Image.open(ruta_imagen)
            # Display the image
            imagen.show()

            # Get the dimensions of the image
            ancho_imagen, alto_imagen = imagen.size

            try:
                # Ask the user for the number of sprites horizontally and vertically
                sprites_ancho = int(input("Introduce el número de sprites de ancho: "))
                sprites_alto = int(input("Introduce el número de sprites de alto: "))

                # Calculate the dimensions of each sprite
                ancho_sprite = ancho_imagen // sprites_ancho
                alto_sprite = alto_imagen // sprites_alto

                # Print the dimensions of each sprite
                print(f"Dimensiones de cada sprite: {ancho_sprite}px (ancho) x {alto_sprite}px (alto)")

                # Create a new folder named "[OriginalFolderName]Edited" to save the sprites
                nombre_carpeta_original = os.path.basename(carpeta_seleccionada)
                carpeta_edited = os.path.join(carpeta_seleccionada, nombre_carpeta_original + "Edited")
                os.makedirs(carpeta_edited, exist_ok=True)

                # Call the function to display and save the sprites
                mostrar_sprites(imagen, sprites_ancho, sprites_alto, ancho_sprite, alto_sprite, carpeta_edited, nombre_carpeta_original)

            except ValueError:
                # Handle invalid input (non-integer values)
                print("Error: Debes introducir números enteros para los sprites de ancho y alto.")
        else:
            # No PNG files found in the selected folder
            print(f"No se encontraron archivos PNG en la carpeta seleccionada.")
    else:
        # No folder was selected
        print("No se seleccionó ninguna carpeta.")

def mostrar_sprites(imagen, sprites_ancho, sprites_alto, ancho_sprite, alto_sprite, carpeta_edited, nombre_carpeta_original):
    # Create a matplotlib figure to display the sprites in a grid
    fig, axes = plt.subplots(sprites_alto, sprites_ancho, figsize=(10, 10))
    fig.suptitle("Sprites con fondo gris claro", fontsize=16)

    # Loop through each sprite in the sprite sheet
    for i in range(sprites_alto):
        for j in range(sprites_ancho):
            # Calculate the cropping coordinates (removing 1 pixel from the first row and column)
            left = j * ancho_sprite + 1
            top = i * alto_sprite + 1
            right = left + ancho_sprite - 1
            bottom = top + alto_sprite - 1

            # Crop the sprite from the sprite sheet
            sprite = imagen.crop((left, top, right, bottom))

            # Save the sprite in the "Edited" folder with a unique name
            nombre_sprite = f"{nombre_carpeta_original}{i * sprites_ancho + j + 1}.png"
            ruta_sprite = os.path.join(carpeta_edited, nombre_sprite)
            sprite.save(ruta_sprite)

            # Get the current subplot for displaying the sprite
            ax = axes[i, j] if sprites_alto > 1 else axes[j]

            # Create a light gray background image
            fondo_gris = Image.new('RGBA', sprite.size, 'lightgray')
            # Display the light gray background first
            ax.imshow(fondo_gris, extent=[0, ancho_sprite, 0, alto_sprite], aspect='auto')

            # Display the sprite on top of the background
            ax.imshow(sprite, extent=[0, ancho_sprite, 0, alto_sprite], aspect='auto')

            # Ensure the sprite maintains its original dimensions (no distortion)
            ax.set_aspect('equal')  # Set aspect ratio to 'equal' for correct scaling
            ax.axis('off')  # Hide axes
            ax.set_title(f"Sprite {i * sprites_ancho + j}")  # Add a title to identify the sprite

    # Adjust the layout to prevent overlapping
    plt.tight_layout()
    # Display the figure
    plt.show()

if __name__ == "__main__":
    # Start the program by calling the folder selection function
    seleccionar_carpeta()