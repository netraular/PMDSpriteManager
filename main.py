import os
from tkinter import Tk, filedialog
from PIL import Image
import matplotlib.pyplot as plt

def seleccionar_carpeta():
    root = Tk()
    root.withdraw()

    carpeta_seleccionada = filedialog.askdirectory(title="Selecciona una carpeta")

    if carpeta_seleccionada:
        archivos_png = [archivo for archivo in os.listdir(carpeta_seleccionada) if archivo.lower().endswith('.png')]

        if archivos_png:
            ruta_imagen = os.path.join(carpeta_seleccionada, archivos_png[0])
            imagen = Image.open(ruta_imagen)
            imagen.show()

            ancho_imagen, alto_imagen = imagen.size

            try:
                sprites_ancho = int(input("Introduce el número de sprites de ancho: "))
                sprites_alto = int(input("Introduce el número de sprites de alto: "))

                ancho_sprite = ancho_imagen // sprites_ancho
                alto_sprite = alto_imagen // sprites_alto

                print(f"Dimensiones de cada sprite: {ancho_sprite}px (ancho) x {alto_sprite}px (alto)")

                nombre_carpeta_original = os.path.basename(carpeta_seleccionada)
                carpeta_edited = os.path.join(carpeta_seleccionada, nombre_carpeta_original + "Edited")
                os.makedirs(carpeta_edited, exist_ok=True)

                mostrar_sprites(imagen, sprites_ancho, sprites_alto, ancho_sprite, alto_sprite, carpeta_edited, nombre_carpeta_original)

            except ValueError:
                print("Error: Debes introducir números enteros para los sprites de ancho y alto.")
        else:
            print(f"No se encontraron archivos PNG en la carpeta seleccionada.")
    else:
        print("No se seleccionó ninguna carpeta.")

def mostrar_sprites(imagen, sprites_ancho, sprites_alto, ancho_sprite, alto_sprite, carpeta_edited, nombre_carpeta_original):
    fig, axes = plt.subplots(sprites_alto, sprites_ancho, figsize=(10, 10))
    fig.suptitle("Sprites con fondo gris claro", fontsize=16)

    for i in range(sprites_alto):
        for j in range(sprites_ancho):
            left = j * ancho_sprite + 1
            top = i * alto_sprite + 1
            right = left + ancho_sprite - 1
            bottom = top + alto_sprite - 1

            sprite = imagen.crop((left, top, right, bottom))
            nombre_sprite = f"{nombre_carpeta_original}{i * sprites_ancho + j + 1}.png"
            ruta_sprite = os.path.join(carpeta_edited, nombre_sprite)
            sprite.save(ruta_sprite)

            ax = axes[i, j] if sprites_alto > 1 else axes[j]

            # Dibujar el fondo gris claro primero
            fondo_gris = Image.new('RGBA', sprite.size, 'lightgray')
            ax.imshow(fondo_gris, extent=[0, ancho_sprite, 0, alto_sprite], aspect='auto')

            # Dibujar el sprite encima del fondo
            ax.imshow(sprite, extent=[0, ancho_sprite, 0, alto_sprite], aspect='auto')

            # Asegurar que los sprites mantengan sus dimensiones originales
            ax.set_aspect('equal')  # Mantener la relación de aspecto correcta
            ax.axis('off')  # Ocultar ejes
            ax.set_title(f"Sprite {i * sprites_ancho + j}")

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    seleccionar_carpeta()