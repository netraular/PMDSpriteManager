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
        print(f"Carpeta de sprites: {self.sprite_folder}")  # Debug
        self.anim_data = self.load_anim_data()
        self.current_anim_index = 0
        self.current_frame_index = 0
        self.animation_playing = False
        self.after_id = None
        
        # Configurar ventana principal
        self.root.title("Visor de Animaciones")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Crear ventana de animación en tiempo real
        self.anim_window = Toplevel(self.root)
        self.anim_window.title("Animación en Tiempo Real")
        self.anim_window.protocol("WM_DELETE_WINDOW", self.on_close)  # Vincular cierre de ventana
        
        self.anim_label = Label(self.anim_window)
        self.anim_label.pack()
        
        # Panel de control
        control_frame = Frame(self.root)
        control_frame.pack(pady=10)
        
        self.prev_button = Button(control_frame, text="Animación Anterior", command=self.prev_animation)
        self.prev_button.pack(side="left", padx=5)
        
        self.next_button = Button(control_frame, text="Siguiente Animación", command=self.next_animation)
        self.next_button.pack(side="left", padx=5)
        
        # Etiqueta para el nombre de la animación
        self.anim_name_label = Label(self.root, text="", font=('Arial', 12, 'bold'))
        self.anim_name_label.pack(pady=5)
        
        # Contenedor para los frames
        self.frames_container = Frame(self.root)
        self.frames_container.pack(pady=10)
        
        # Iniciar la primera animación
        self.show_animation()

    def load_anim_data(self):
        """Cargar y parsear el archivo AnimData.xml"""
        anim_data_path = os.path.join(self.sprite_folder, "AnimData.xml")
        print(f"Intentando cargar AnimData.xml desde: {anim_data_path}")  # Debug
        
        if not os.path.exists(anim_data_path):
            raise FileNotFoundError(f"No se encontró AnimData.xml en {self.sprite_folder}")

        tree = ET.parse(anim_data_path)
        root = tree.getroot()

        anims = []
        for anim in root.find("Anims"):
            name = anim.find("Name").text
            frame_width = int(anim.find("FrameWidth").text) if anim.find("FrameWidth") is not None else None
            frame_height = int(anim.find("FrameHeight").text) if anim.find("FrameHeight") is not None else None

            # Leer las duraciones de los frames
            durations = []
            durations_node = anim.find("Durations")
            if durations_node is not None:
                for duration in durations_node.findall("Duration"):
                    durations.append(int(duration.text))
            print(f"Animación '{name}' cargada con {len(durations)} duraciones.")  # Debug

            anims.append({
                "name": name,
                "frame_width": frame_width,
                "frame_height": frame_height,
                "durations": durations,
                "image_path": os.path.join(self.sprite_folder, f"{name}-Anim.png")
            })

        print(f"Total de animaciones cargadas: {len(anims)}")  # Debug
        return anims

    def clear_frames(self):
        """Limpiar los frames anteriores"""
        print("Limpiando frames anteriores...")  # Debug
        for widget in self.frames_container.winfo_children():
            widget.destroy()

    def show_animation(self):
        """Mostrar la animación actual"""
        print(f"Mostrando animación {self.current_anim_index}...")  # Debug
        self.clear_frames()
        
        if self.current_anim_index >= len(self.anim_data):
            print("No hay más animaciones para mostrar.")  # Debug
            return

        # Detener cualquier animación en curso
        if self.after_id:
            print("Deteniendo animación en curso...")  # Debug
            self.root.after_cancel(self.after_id)
            self.after_id = None

        anim = self.anim_data[self.current_anim_index]
        print(f"Animación actual: {anim['name']}")  # Debug
        self.anim_name_label.config(text=f"Animación: {anim['name']}")
        self.anim_window.title(f"Animación en Tiempo Real - {anim['name']}")

        if not os.path.exists(anim["image_path"]):
            print(f"Archivo no encontrado: {anim['image_path']}")  # Debug
            return

        # Cargar y dividir la animación
        print(f"Cargando imagen de animación: {anim['image_path']}")  # Debug
        handler = SpriteSheetHandler(anim["image_path"])
        self.frames = handler.split_animation_frames(anim["frame_width"], anim["frame_height"])
        print(f"Total de frames: {len(self.frames)}")  # Debug

        # Verificar y ajustar las duraciones
        if anim["durations"]:
            self.durations = anim["durations"]
            print(f"Duración de frames: {self.durations}")  # Debug
            # Si hay más frames que duraciones, se repite la última duración
            if len(self.durations) < len(self.frames):
                last_duration = self.durations[-1]
                self.durations.extend([last_duration] * (len(self.frames) - len(self.durations)))
                print(f"Duración ajustada: {self.durations}")  # Debug
        else:
            # Si no hay duraciones, se usa 1 frame por defecto
            self.durations = [1] * len(self.frames)
            print(f"No se encontraron duraciones. Usando valor predeterminado: {self.durations}")  # Debug
        
        # Mostrar los frames en una rejilla
        print("Mostrando frames en la cuadrícula...")  # Debug
        row = 0
        col = 0
        max_cols = 4
        
        for idx, frame in enumerate(self.frames):
            if col >= max_cols:
                row += 1
                col = 0
            
            frame.thumbnail((100, 100))
            img = ImageTk.PhotoImage(frame)
            
            frame_frame = Frame(self.frames_container, bd=2, relief="groove")
            frame_frame.grid(row=row, column=col, padx=5, pady=5)
            
            label = Label(frame_frame, image=img)
            label.image = img
            label.pack(padx=2, pady=2)
            
            Label(frame_frame, text=f"Frame {idx + 1}\n({self.durations[idx]} frames)", font=('Arial', 8)).pack()
            col += 1

        # Iniciar animación en tiempo real
        print("Iniciando animación en tiempo real...")  # Debug
        self.current_frame_index = 0
        self.update_animation()

    def update_animation(self):
        """Actualizar el frame de la animación en tiempo real"""
        if self.current_frame_index >= len(self.frames):
            print("Reiniciando animación...")  # Debug
            self.current_frame_index = 0

        frame = self.frames[self.current_frame_index]
        frame.thumbnail((300, 300))  # Tamaño para la ventana de animación
        
        img = ImageTk.PhotoImage(frame)
        self.anim_label.config(image=img)
        self.anim_label.image = img
        
        # Calcular tiempo de espera en ms (30 fps = 33.33 ms por frame)
        frame_duration = self.durations[self.current_frame_index]
        delay = int(frame_duration * (1000 / 30))
        
        self.current_frame_index += 1
        self.after_id = self.root.after(delay, self.update_animation)

    def next_animation(self):
        """Siguiente animación"""
        print("Cambiando a la siguiente animación...")  # Debug
        self.current_anim_index = (self.current_anim_index + 1) % len(self.anim_data)
        self.show_animation()

    def prev_animation(self):
        """Animación anterior"""
        print("Cambiando a la animación anterior...")  # Debug
        self.current_anim_index = (self.current_anim_index - 1) % len(self.anim_data)
        self.show_animation()

    def on_close(self):
        """Manejar el cierre de la ventana"""
        print("Cerrando ventana...")  # Debug
        if self.after_id:
            self.root.after_cancel(self.after_id)
        self.root.destroy()  # Cerrar la ventana principal
        self.anim_window.destroy()  # Cerrar la ventana de animación
        os._exit(0)  # Forzar la terminación del programa

def seleccionar_carpeta():
    """
    Abre un diálogo para seleccionar una carpeta y procesar el sprite sheet.
    """
    root = Tk()
    root.withdraw()

    # Abrir un diálogo para seleccionar una carpeta
    carpeta_seleccionada = filedialog.askdirectory(title="Selecciona una carpeta")
    print(f"Carpeta seleccionada: {carpeta_seleccionada}")  # Debug

    if carpeta_seleccionada:
        # Buscar todos los archivos PNG en la carpeta seleccionada
        archivos_png = [archivo for archivo in os.listdir(carpeta_seleccionada) if archivo.lower().endswith('.png')]
        print(f"Archivos PNG encontrados: {archivos_png}")  # Debug

        if archivos_png:
            # Obtener la ruta del primer archivo PNG
            ruta_imagen = os.path.join(carpeta_seleccionada, archivos_png[0])
            print(f"Ruta de la imagen seleccionada: {ruta_imagen}")  # Debug

            # Abrir y mostrar la imagen original
            imagen_original = Image.open(ruta_imagen)
            imagen_original.show()  # Mostrar la imagen original

            # Preguntar al usuario por el número de sprites horizontal y vertical
            try:
                sprites_ancho = int(input("Introduce el número de sprites de ancho: "))
                sprites_alto = int(input("Introduce el número de sprites de alto: "))
                print(f"Sprites de ancho: {sprites_ancho}, Sprites de alto: {sprites_alto}")  # Debug

                # Inicializar el SpriteSheetHandler con la ruta de la imagen y remove_first_row_and_col=True
                sprite_handler = SpriteSheetHandler(ruta_imagen, remove_first_row_and_col=True)

                # Dividir el sprite sheet en sprites individuales
                sprites, ancho_sprite, alto_sprite = sprite_handler.split_sprites(sprites_ancho, sprites_alto)
                print(f"Sprites divididos: {len(sprites)}")  # Debug

                # Crear una nueva carpeta para guardar los sprites
                nombre_carpeta_original = os.path.basename(carpeta_seleccionada)
                carpeta_edited = os.path.join(carpeta_seleccionada, nombre_carpeta_original + "Edited")
                os.makedirs(carpeta_edited, exist_ok=True)
                print(f"Carpeta de salida creada: {carpeta_edited}")  # Debug

                # Guardar los sprites en la carpeta de salida
                sprite_handler.save_sprites(sprites, carpeta_edited, nombre_carpeta_original)
                print("Sprites guardados correctamente.")  # Debug

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