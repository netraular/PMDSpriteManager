# main.py (updated version)

import os
from tkinter import Tk, filedialog, Frame, Label, Button, messagebox
from PIL import Image, ImageTk
from sprite_sheet_handler import SpriteSheetHandler
from animation_viewer import AnimationViewer
from animation_creator import AnimationCreator
from batch_resizer import BatchResizer

class MainApplication:
    def __init__(self, root):
        self.root = root
        self.root.title("Sprite Sheet Tool")
        self.root.geometry("800x600")
        self.current_frame = None
        self.folder = None
        self.animation_viewer = None
        self.animation_creator = None
        self.batch_resizer = None
        
        self.show_folder_selection()

    def clear_frame(self):
        if self.current_frame:
            self.current_frame.destroy()
        self.current_frame = Frame(self.root)
        self.current_frame.pack(fill='both', expand=True)

    def show_folder_selection(self):
        """
        Displays the initial screen with the two main workflow choices.
        """
        self.clear_frame()
        
        Label(self.current_frame, 
             text="Welcome to the PMD Sprite Manager",
             font=('Arial', 16, 'bold')).pack(pady=(50, 10))
             
        Label(self.current_frame, 
             text="Please choose your workflow:",
             font=('Arial', 12)).pack(pady=(10, 30))
        
        # --- Workflow 1: Pokemon Project ---
        Button(self.current_frame, 
               text="Select Pokemon Folder", 
               command=self.select_project_folder, 
               font=('Arial', 12),
               width=25,
               height=2).pack(pady=10)
        
        # --- Workflow 2: Batch Utility ---
        Button(self.current_frame, 
               text="Batch Resize Sprites", 
               command=self.launch_batch_resizer, 
               font=('Arial', 12),
               width=25,
               height=2).pack(pady=10)

    def select_project_folder(self):
        """
        Handles the selection of a Pokémon project folder and proceeds to the main menu.
        """
        folder = filedialog.askdirectory(title="Select a Pokémon Project Folder")
        if folder:
            self.folder = folder
            self.show_main_menu()

    def show_main_menu(self):
        """
        Displays the main menu for a selected Pokémon project folder.
        """
        self.clear_frame()
        Label(self.current_frame, text=f"Selected folder:\n{self.folder}", 
             font=('Arial', 12)).pack(pady=20)
        
        Button(self.current_frame, text="Process Spritesheet", 
              command=self.show_animation_creator, width=25).pack(pady=10)
        Button(self.current_frame, text="View Animations", 
              command=self.show_animation_viewer, width=25).pack(pady=10)
        Button(self.current_frame, text="Preview Animation JSON",
              command=self.show_json_previewer, width=25).pack(pady=10)
        
        # Add a button to go back to the initial selection screen
        Button(self.current_frame, text="Back to Workflow Selection", 
              command=self.show_folder_selection).pack(pady=20)


    def show_animation_viewer(self):
        self.clear_frame()
        
        control_frame = Frame(self.current_frame)
        control_frame.pack(fill='x', padx=10, pady=5)
        Button(control_frame, text="Main Menu", 
            command=self.show_main_menu).pack(side='left')
        Button(control_frame, text="Previous", 
            command=lambda: self.animation_viewer.prev_animation()).pack(side='left', padx=5)
        Button(control_frame, text="Next", 
            command=lambda: self.animation_viewer.next_animation()).pack(side='left', padx=5)
        Button(control_frame, text="Generate JSON", 
            command=lambda: self.animation_viewer.generate_json()).pack(side='left', padx=5)
        Button(control_frame, text="View Sprites", 
            command=lambda: self.animation_viewer.view_sprites()).pack(side='left', padx=5)
        Button(control_frame, text="Save All Animations", 
            command=lambda: self.animation_viewer.save_all_animations(), bg="lightblue").pack(side='left', padx=5)

        try:
            self.animation_viewer = AnimationViewer(self.current_frame, self.folder)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load animations: {str(e)}")
            self.show_main_menu()

    def show_animation_creator(self):
        self.clear_frame()
        self.animation_creator = AnimationCreator(
            self.current_frame,
            self.folder,
            self.show_main_menu
        )

    def show_json_previewer(self):
        """
        Launches the AnimationCreator directly into the JSON preview mode.
        """
        self.clear_frame()
        sprites_folder = os.path.join(self.folder, "Sprites")
        if not os.path.exists(sprites_folder) or not os.listdir(sprites_folder):
            messagebox.showerror("Error", "The 'Sprites' folder is missing or empty.\nPlease process a spritesheet first.")
            self.show_main_menu()
            return
            
        self.animation_creator = AnimationCreator(
            self.current_frame,
            self.folder,
            self.show_main_menu,
            start_directly_at_json_upload=True
        )

    def launch_batch_resizer(self):
        """
        Clears the frame and launches the BatchResizer module directly.
        The callback is set to return to the initial folder selection screen.
        """
        self.clear_frame()
        self.batch_resizer = BatchResizer(
            self.current_frame,
            self.show_folder_selection
        )

if __name__ == "__main__":
    root = Tk()
    app = MainApplication(root)
    root.mainloop()