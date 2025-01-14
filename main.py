import os
from tkinter import Tk, filedialog
from PIL import Image
import matplotlib.pyplot as plt

def seleccionar_carpeta():
    # Crear una ventana de Tkinter oculta
    root = Tk()
    root.withdraw()

    # Abrir el diálogo para seleccionar una carpeta
    carpeta_seleccionada = filedialog.askdirectory(title="Selecciona una carpeta")

    # Verificar si se seleccionó una carpeta
    if carpeta_seleccionada:
        # Buscar archivos PNG en la carpeta seleccionada
        archivos_png = [archivo for archivo in os.listdir(carpeta_seleccionada) if archivo.lower().endswith('.png')]

        # Verificar si se encontró al menos un archivo PNG
        if archivos_png:
            # Tomar el primer archivo PNG encontrado
            ruta_imagen = os.path.join(carpeta_seleccionada, archivos_png[0])

            # Abrir la imagen usando Pillow
            imagen = Image.open(ruta_imagen)
            imagen.show()  # Mostrar la imagen

            # Obtener las dimensiones de la imagen
            ancho_imagen, alto_imagen = imagen.size

            # Preguntar al usuario cuántos sprites hay de ancho y de alto
            try:
                sprites_ancho = int(input("Introduce el número de sprites de ancho: "))
                sprites_alto = int(input("Introduce el número de sprites de alto: "))

                # Calcular el ancho y alto de cada sprite
                ancho_sprite = ancho_imagen // sprites_ancho
                alto_sprite = alto_imagen // sprites_alto

                # Mostrar las dimensiones de cada sprite
                print(f"Dimensiones ajustadas de cada sprite: {ancho_sprite}px (ancho) x {alto_sprite}px (alto)")

                # Dividir la imagen en sprites y mostrarlos con fondo gris claro
                mostrar_sprites(imagen, sprites_ancho, sprites_alto, ancho_sprite, alto_sprite)

            except ValueError:
                print("Error: Debes introducir números enteros para los sprites de ancho y alto.")
        else:
            print(f"No se encontraron archivos PNG en la carpeta seleccionada.")
    else:
        print("No se seleccionó ninguna carpeta.")

def mostrar_sprites(imagen, sprites_ancho, sprites_alto, ancho_sprite, alto_sprite):
    # Crear una figura de matplotlib para mostrar los sprites
    fig, axes = plt.subplots(sprites_alto, sprites_ancho, figsize=(10, 10))
    fig.suptitle("Sprites con fondo gris claro", fontsize=16)

    # Recorrer cada sprite
    for i in range(sprites_alto):
        for j in range(sprites_ancho):
            # Calcular las coordenadas de recorte ajustadas
            left = j * ancho_sprite + 1  # Mover 1 píxel hacia la derecha
            top = i * alto_sprite + 1  # Mover 1 píxel hacia abajo
            right = left + ancho_sprite - 1
            bottom = top + alto_sprite - 1

            # Recortar el sprite
            sprite = imagen.crop((left, top, right, bottom))

            # Crear un fondo gris claro
            fondo = Image.new("RGBA", (ancho_sprite - 1, alto_sprite - 1), (211, 211, 211, 255))  # Gris claro
            fondo.paste(sprite, (0, 0), sprite)  # Combinar el sprite con el fondo gris

            # Mostrar el sprite con el fondo en la cuadrícula
            ax = axes[i, j] if sprites_alto > 1 else axes[j]
            ax.imshow(fondo)  # Dibujar el sprite con fondo combinado
            ax.axis('off')  # Ocultar ejes
            ax.set_title(f"Sprite {i * sprites_ancho + j}")  # Identificador numérico

    # Ajustar el espacio entre subplots
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    seleccionar_carpeta()
