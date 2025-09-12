# batch_resizer.py

import os
from tkinter import Frame, Label, Button, Entry, Canvas, Scrollbar, messagebox, filedialog
from PIL import Image, ImageTk
from sprite_sheet_handler import SpriteSheetHandler

class BatchResizer:
    def __init__(self, parent_frame, return_to_main_callback):
        self.parent_frame = parent_frame
        self.return_to_main = return_to_main_callback
        
        # State variables
        self.input_folder = None
        self.output_folder = None
        self.image_files = []
        self.current_image_index = 0

        # UI elements
        self.main_frame = Frame(self.parent_frame)
        self.main_frame.pack(fill='both', expand=True)

        self.setup_initial_view()

    def setup_initial_view(self):
        """Muestra la vista inicial para seleccionar una carpeta."""
        self.clear_frame()
        
        top_frame = Frame(self.main_frame)
        top_frame.pack(fill='x', padx=10, pady=5)
        Button(top_frame, text="Main Menu", command=self.return_to_main).pack(side='left')

        content_frame = Frame(self.main_frame)
        content_frame.pack(pady=50)

        Label(content_frame, 
              text="Select a folder containing spritesheets to process in batch.",
              font=('Arial', 14)).pack(pady=20)
        
        Button(content_frame, text="Select Folder", 
               command=self.select_folder, font=('Arial', 12)).pack()

    def select_folder(self):
        """Abre el diálogo para seleccionar la carpeta de entrada."""
        folder = filedialog.askdirectory(title="Select Folder with Spritesheets")
        if not folder:
            return

        self.input_folder = folder
        self.output_folder = os.path.join(folder, "output")
        os.makedirs(self.output_folder, exist_ok=True)

        # Filtrar solo los archivos con el formato esperado
        self.image_files = sorted([
            f for f in os.listdir(folder) 
            if f.lower().endswith('.png') and f.startswith('sprite_recolor-')
        ])

        if not self.image_files:
            messagebox.showwarning("No Files Found", 
                                   "No images matching 'sprite_recolor-*.png' were found in the selected folder.")
            return

        self.current_image_index = 0
        self.show_processing_view()

    def show_processing_view(self):
        """Muestra la vista de procesamiento para la imagen actual."""
        self.clear_frame()

        if self.current_image_index >= len(self.image_files):
            messagebox.showinfo("Complete", "All spritesheets have been processed successfully.")
            self.return_to_main()
            return

        current_file = self.image_files[self.current_image_index]
        self.current_image_path = os.path.join(self.input_folder, current_file)

        # --- Top Control Frame ---
        control_frame = Frame(self.main_frame)
        control_frame.pack(fill='x', padx=10, pady=5)
        Button(control_frame, text="Main Menu", command=self.return_to_main).pack(side='left')

        # --- Content Frame ---
        content_frame = Frame(self.main_frame)
        content_frame.pack(fill='both', expand=True, padx=20, pady=10)

        # Progress label
        progress_text = (f"Processing {self.current_image_index + 1} of {len(self.image_files)}: "
                         f"{current_file}")
        Label(content_frame, text=progress_text, font=('Arial', 10, 'bold')).pack(pady=5)
        
        # Image preview
        try:
            img = Image.open(self.current_image_path)
            img.thumbnail((500, 400))
            self.img_tk = ImageTk.PhotoImage(img)
            Label(content_frame, image=self.img_tk).pack(pady=10)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load image {current_file}: {e}")
            self.process_next_image() # Skip to the next one
            return

        # Form for user input
        form_frame = Frame(content_frame)
        form_frame.pack(pady=10)

        Label(form_frame, text="Sprites (width/height):").grid(row=0, column=0, padx=5)
        self.size_entry = Entry(form_frame, width=10)
        self.size_entry.grid(row=0, column=1, padx=5)
        self.size_entry.focus_set()

        self.size_entry.bind("<Return>", self.process_current_image)

        Button(form_frame, text="Process and Next", 
               command=self.process_current_image).grid(row=1, columnspan=2, pady=10)

    def process_current_image(self, event=None):
        """Procesa el spritesheet actual y pasa al siguiente."""
        try:
            size = int(self.size_entry.get())
            if size <= 0:
                raise ValueError("Size must be a positive number.")
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid positive number for the size.")
            return

        try:
            # Procesar el spritesheet
            handler = SpriteSheetHandler(self.current_image_path, remove_first_row=True, remove_first_col=False)
            sprites, _, _ = handler.split_sprites(size, size)

            if not sprites:
                raise Exception("Splitting the spritesheet yielded no sprites.")

            # Extraer el ID del nombre del archivo original
            # "sprite_recolor-0043-0000-0001.png" -> "0043"
            basename = os.path.basename(self.current_image_path)
            parts = basename.split('-')
            
            if len(parts) > 1:
                sprite_id = parts[1]
                
                # Crear la carpeta de salida específica para este spritesheet usando su ID
                sprite_output_folder = os.path.join(self.output_folder, sprite_id)
                os.makedirs(sprite_output_folder, exist_ok=True)
                
                # Iterar sobre TODOS los sprites generados
                for idx, sprite in enumerate(sprites):
                    # Convertir el sprite a modo 'P' (paleta) de 8 bits
                    sprite_8bit = sprite.convert('P', palette=Image.ADAPTIVE, colors=256)
                    
                    # Definir el nombre del archivo para cada sprite individual
                    output_filename = f"sprite_{idx + 1}.png"
                    output_path = os.path.join(sprite_output_folder, output_filename)
                    
                    # Guardar el sprite convertido
                    sprite_8bit.save(output_path)
            else:
                messagebox.showwarning("Filename Error", 
                                       f"Could not extract ID from filename: {basename}. Skipping save.")

        except Exception as e:
            messagebox.showerror("Processing Error", f"An error occurred while processing the image: {e}")
        
        # Pasar a la siguiente imagen independientemente del resultado
        self.process_next_image()

    def process_next_image(self):
        """Incrementa el índice y muestra la siguiente vista de procesamiento."""
        self.current_image_index += 1
        self.show_processing_view()

    def clear_frame(self):
        """Limpia el frame principal para dibujar la nueva vista."""
        for widget in self.main_frame.winfo_children():
            widget.destroy()