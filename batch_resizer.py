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
        self.parent_folder = None
        self.project_folders = []
        self.current_folder_index = 0

        # UI elements
        self.main_frame = Frame(self.parent_frame)
        self.main_frame.pack(fill='both', expand=True)

        self.setup_initial_view()

    def setup_initial_view(self):
        """Shows the initial view to select a parent folder."""
        self.clear_frame()
        
        top_frame = Frame(self.main_frame)
        top_frame.pack(fill='x', padx=10, pady=5)
        Button(top_frame, text="Main Menu", command=self.return_to_main).pack(side='left')

        content_frame = Frame(self.main_frame)
        content_frame.pack(pady=50)

        Label(content_frame, 
              text="Select a parent folder containing project subfolders.",
              font=('Arial', 14)).pack(pady=20)
        
        Button(content_frame, text="Select Parent Folder", 
               command=self.select_parent_folder, font=('Arial', 12)).pack()

    def select_parent_folder(self):
        """Opens the dialog to select the parent folder of projects."""
        folder = filedialog.askdirectory(title="Select Parent Folder with Projects")
        if not folder:
            return

        self.parent_folder = folder
        
        # Find all immediate subdirectories
        self.project_folders = sorted([
            d for d in os.listdir(folder) 
            if os.path.isdir(os.path.join(folder, d))
        ])

        if not self.project_folders:
            messagebox.showwarning("No Folders Found", 
                                   "No project subfolders were found in the selected directory.")
            return

        self.current_folder_index = 0
        self.show_processing_view()

    def show_processing_view(self):
        """Shows the processing view for the current project folder."""
        self.clear_frame()

        if self.current_folder_index >= len(self.project_folders):
            messagebox.showinfo("Complete", "All project folders have been processed.")
            self.return_to_main()
            return

        current_folder_name = self.project_folders[self.current_folder_index]
        self.current_project_path = os.path.join(self.parent_folder, current_folder_name)
        
        # Find the first PNG spritesheet in the folder
        try:
            png_files = [f for f in os.listdir(self.current_project_path) if f.lower().endswith('.png')]
            if not png_files:
                raise FileNotFoundError("No PNG files found in this folder.")
            self.current_spritesheet_path = os.path.join(self.current_project_path, png_files[0])
        except Exception as e:
            messagebox.showerror("Error", f"Could not find a spritesheet in '{current_folder_name}': {e}. Skipping folder.")
            self.process_next_folder()
            return

        # --- Top Control Frame ---
        control_frame = Frame(self.main_frame)
        control_frame.pack(fill='x', padx=10, pady=5)
        Button(control_frame, text="Main Menu", command=self.return_to_main).pack(side='left')
        Button(control_frame, text="Skip Folder", command=self.process_next_folder).pack(side='left', padx=5)

        # --- Content Frame ---
        content_frame = Frame(self.main_frame)
        content_frame.pack(fill='both', expand=True, padx=20, pady=10)

        # Progress label
        progress_text = (f"Processing {self.current_folder_index + 1} of {len(self.project_folders)}: "
                         f"{current_folder_name}")
        Label(content_frame, text=progress_text, font=('Arial', 10, 'bold')).pack(pady=5)
        
        # Image preview
        try:
            img = Image.open(self.current_spritesheet_path)
            img.thumbnail((500, 400))
            self.img_tk = ImageTk.PhotoImage(img)
            Label(content_frame, image=self.img_tk).pack(pady=10)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load image {os.path.basename(self.current_spritesheet_path)}: {e}")
            self.process_next_folder() # Skip to the next one
            return

        # Form for user input
        form_frame = Frame(content_frame)
        form_frame.pack(pady=10)

        Label(form_frame, text="Size (width/height):").grid(row=0, column=0, padx=5)
        self.size_entry = Entry(form_frame, width=10)
        self.size_entry.grid(row=0, column=1, padx=5)
        self.size_entry.focus_set()

        self.size_entry.bind("<Return>", self.process_current_folder)

        Button(form_frame, text="Process and Next", 
               command=self.process_current_folder).grid(row=1, columnspan=2, pady=10)

    def process_current_folder(self, event=None):
        """Processes the current spritesheet and moves to the next folder."""
        try:
            size = int(self.size_entry.get())
            if size <= 0:
                raise ValueError("Size must be a positive number.")
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid positive number for the size.")
            return

        try:
            output_folder = os.path.join(self.current_project_path, "Sprites")
            
            if os.path.exists(output_folder) and os.listdir(output_folder):
                folder_name = os.path.basename(self.current_project_path)
                msg = f"The 'Sprites' folder in '{folder_name}' already contains files. Do you want to delete them and continue?"
                if not messagebox.askyesno("Confirmation", msg):
                    self.process_next_folder() # Skip if user cancels
                    return
            
            os.makedirs(output_folder, exist_ok=True)
            for file in os.listdir(output_folder):
                os.unlink(os.path.join(output_folder, file))

            handler = SpriteSheetHandler(self.current_spritesheet_path, remove_first_row=True, remove_first_col=False)
            sprites, _, _ = handler.split_sprites(size, size)

            if not sprites:
                raise Exception("Splitting the spritesheet yielded no sprites.")

            for idx, sprite in enumerate(sprites):
                output_path = os.path.join(output_folder, f"sprite_{idx + 1}.png")
                sprite.save(output_path)
        
        except Exception as e:
            messagebox.showerror("Processing Error", f"An error occurred while processing the spritesheet: {e}")
        
        # Move to the next folder regardless of the outcome
        self.process_next_folder()

    def process_next_folder(self):
        """Increments the index and shows the next processing view."""
        self.current_folder_index += 1
        self.show_processing_view()

    def clear_frame(self):
        """Clears the main frame to draw the new view."""
        for widget in self.main_frame.winfo_children():
            widget.destroy()