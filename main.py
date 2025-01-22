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
        self.after_ids = []
        
        # Configurar ventana principal
        self.root.title("Visor de Animaciones")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Ventana de animación en tiempo real
        self.anim_window = Toplevel(self.root)
        self.anim_window.title("Animación en Tiempo Real")
        self.anim_window.protocol("WM_DELETE_WINDOW", self.on_close)
        self.anim_container = Frame(self.anim_window)
        self.anim_container.pack(padx=10, pady=10)
        
        # Panel de control
        control_frame = Frame(self.root)
        control_frame.pack(pady=10)
        Button(control_frame, text="Anterior", command=self.prev_animation).pack(side="left", padx=5)
        Button(control_frame, text="Siguiente", command=self.next_animation).pack(side="left", padx=5)
        
        # Contenedores
        self.frames_container = Frame(self.root)
        self.frames_container.pack(pady=10)
        
        self.show_animation()

    def load_anim_data(self):
        """Cargar animaciones agrupando por nombre base"""
        anim_data_path = os.path.join(self.sprite_folder, "AnimData.xml")
        if not os.path.exists(anim_data_path):
            raise FileNotFoundError(f"Archivo XML no encontrado en: {self.sprite_folder}")

        tree = ET.parse(anim_data_path)
        root = tree.getroot()
        animaciones = []

        for anim in root.find("Anims"):
            base_name = anim.find("Name").text
            frame_width = int(anim.find("FrameWidth").text)
            frame_height = int(anim.find("FrameHeight").text)
            durations = [int(d.text) for d in anim.findall("Durations/Duration")]
            
            image_path = os.path.join(self.sprite_folder, f"{base_name}-Anim.png")
            if not os.path.exists(image_path):
                continue

            with Image.open(image_path) as img:
                img_width, img_height = img.size
                total_groups = img_height // frame_height
                frames_per_group = img_width // frame_width

            grupos = []
            for group_num in range(total_groups):
                grupos.append({
                    "group_num": group_num + 1,
                    "frame_height": frame_height,
                    "frame_width": frame_width,
                    "durations": durations.copy(),
                    "frames_per_group": frames_per_group,
                    "image_path": image_path
                })

            animaciones.append({
                "base_name": base_name,
                "grupos": grupos,
                "total_groups": total_groups
            })

        return animaciones

    def mostrar_todos_grupos(self):
        """Mostrar todos los grupos y frames de la animación actual"""
        for widget in self.frames_container.winfo_children():
            widget.destroy()

        anim_actual = self.anim_data[self.current_anim_index]
        
        main_frame = Frame(self.frames_container)
        main_frame.pack()
        
        Label(main_frame, text=f"Animación: {anim_actual['base_name']}", 
             font=('Arial', 14, 'bold')).grid(row=0, column=0, columnspan=4, pady=10)

        row_offset = 1
        for grupo_idx, grupo in enumerate(anim_actual['grupos']):
            handler = SpriteSheetHandler(grupo["image_path"])
            all_frames = handler.split_animation_frames(grupo["frame_width"], grupo["frame_height"])
            
            # Calcular el rango de frames para este grupo
            start = grupo["group_num"] - 1  # Ajustar índice a base 0
            start *= grupo["frames_per_group"]
            end = start + grupo["frames_per_group"]
            
            # Asegurarse de no exceder el número de frames
            if end > len(all_frames):
                end = len(all_frames)
            
            frames_grupo = all_frames[start:end]
            
            # Ajustar duraciones
            duraciones = grupo["durations"]
            if len(duraciones) < len(frames_grupo):
                duraciones += [duraciones[-1]] * (len(frames_grupo) - len(duraciones))

            # Marco para el grupo
            group_frame = Frame(main_frame, bd=2, relief="groove")
            group_frame.grid(row=row_offset + grupo_idx, column=0, columnspan=4, pady=5, sticky="w")
            
            Label(group_frame, text=f"Grupo {grupo['group_num']}", 
                 font=('Arial', 10, 'bold')).pack(anchor="w")
            
            # Frames del grupo
            frame_subframe = Frame(group_frame)
            frame_subframe.pack()
            
            for idx, frame in enumerate(frames_grupo):
                frame.thumbnail((80, 80))
                img = ImageTk.PhotoImage(frame)
                
                lbl = Label(frame_subframe, image=img)
                lbl.image = img
                lbl.grid(row=0, column=idx, padx=2)
                Label(frame_subframe, text=f"Frame {idx+1}\n({duraciones[idx]} frames)", 
                     font=('Arial', 7)).grid(row=1, column=idx, padx=2)

    def animar_grupos(self):
        """Mostrar todas las animaciones de grupos en tiempo real"""
        for widget in self.anim_container.winfo_children():
            widget.destroy()

        anim_actual = self.anim_data[self.current_anim_index]
        
        for grupo_idx, grupo in enumerate(anim_actual['grupos']):
            handler = SpriteSheetHandler(grupo["image_path"])
            all_frames = handler.split_animation_frames(grupo["frame_width"], grupo["frame_height"])
            
            # Calcular el rango de frames para este grupo
            start = grupo["group_num"] - 1  # Ajustar índice a base 0
            start *= grupo["frames_per_group"]
            end = start + grupo["frames_per_group"]
            
            # Asegurarse de no exceder el número de frames
            if end > len(all_frames):
                end = len(all_frames)
            
            frames_grupo = all_frames[start:end]
            
            # Configurar animación por grupo
            group_frame = Frame(self.anim_container)
            group_frame.grid(row=grupo_idx, column=0, pady=5, sticky="w")
            
            Label(group_frame, text=f"Grupo {grupo['group_num']}:", 
                 font=('Arial', 10)).pack(side="left")
            
            lbl = Label(group_frame)
            lbl.pack(side="left")
            
            # Iniciar animación
            self.iniciar_animacion_grupo(lbl, frames_grupo, grupo["durations"])

    def iniciar_animacion_grupo(self, label, frames, durations):
        """Manejar la animación de un grupo individual"""
        current_frame = [0]
        
        def update():
            if current_frame[0] >= len(frames):
                current_frame[0] = 0
                
            frame = frames[current_frame[0]]
            frame.thumbnail((150, 150))
            img = ImageTk.PhotoImage(frame)
            label.config(image=img)
            label.image = img
            
            delay = int(durations[current_frame[0]] * (1000 / 30))
            current_frame[0] += 1
            self.after_ids.append(self.root.after(delay, update))
        
        update()

    def show_animation(self):
        if self.current_anim_index >= len(self.anim_data):
            return

        # Detener animaciones previas
        for aid in self.after_ids:
            self.root.after_cancel(aid)
        self.after_ids.clear()

        self.mostrar_todos_grupos()
        self.animar_grupos()

    def next_animation(self):
        self.current_anim_index = (self.current_anim_index + 1) % len(self.anim_data)
        self.show_animation()

    def prev_animation(self):
        self.current_anim_index = (self.current_anim_index - 1) % len(self.anim_data)
        self.show_animation()

    def on_close(self):
        for aid in self.after_ids:
            self.root.after_cancel(aid)
        self.root.destroy()
        self.anim_window.destroy()
        os._exit(0)

def seleccionar_carpeta():
    root = Tk()
    root.withdraw()
    carpeta = filedialog.askdirectory(title="Selecciona una carpeta")

    if carpeta:
        try:
            # Buscar todos los archivos PNG en la carpeta seleccionada
            archivos_png = [archivo for archivo in os.listdir(carpeta) if archivo.lower().endswith('.png')]

            if archivos_png:
                # Obtener la ruta del primer archivo PNG
                ruta_imagen = os.path.join(carpeta, archivos_png[0])

                # Abrir y mostrar la imagen original
                imagen_original = Image.open(ruta_imagen)
                imagen_original.show()  # Mostrar la imagen original

                # Preguntar al usuario por el número de sprites horizontal y vertical
                sprites_ancho = int(input("Introduce el número de sprites de ancho: "))
                sprites_alto = int(input("Introduce el número de sprites de alto: "))

                # Inicializar el SpriteSheetHandler con la ruta de la imagen y remove_first_row_and_col=True
                sprite_handler = SpriteSheetHandler(ruta_imagen, remove_first_row_and_col=True)

                # Dividir el sprite sheet en sprites individuales
                sprites, ancho_sprite, alto_sprite = sprite_handler.split_sprites(sprites_ancho, sprites_alto)

                # Crear una nueva carpeta para guardar los sprites
                nombre_carpeta_original = os.path.basename(carpeta)
                carpeta_edited = os.path.join(carpeta, nombre_carpeta_original + "Edited")
                os.makedirs(carpeta_edited, exist_ok=True)

                # Guardar los sprites en la carpeta de salida
                sprite_handler.save_sprites(sprites, carpeta_edited, nombre_carpeta_original)

                # Mostrar los sprites en una cuadrícula
                sprite_handler.display_sprites(sprites, sprites_ancho, sprites_alto, ancho_sprite, alto_sprite)

                # Abrir el archivo AnimData.xml y mostrar las animaciones
                anim_viewer_root = Toplevel()
                anim_viewer = AnimationViewer(anim_viewer_root, carpeta)
                anim_viewer_root.mainloop()

        except ValueError:
            print("Error: Debes introducir números enteros para los sprites de ancho y alto.")
        except FileNotFoundError as e:
            print(e)
        except Exception as e:
            print(f"Error inesperado: {e}")
    else:
        print("No se seleccionó ninguna carpeta.")

if __name__ == "__main__":
    seleccionar_carpeta()