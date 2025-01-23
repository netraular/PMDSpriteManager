import os
from tkinter import Tk, filedialog, Frame, Label, Button, messagebox
from PIL import Image, ImageTk
from sprite_sheet_handler import SpriteSheetHandler
from animation_viewer import AnimationViewer
from spritesheet_viewer import SpritesheetViewer

class MainApplication:
    def __init__(self, root):
        self.root = root
        self.root.title("Sprite Sheet Tool")
        self.root.geometry("800x600")
        self.current_frame = None
        self.folder = None
        self.spritesheet_viewer = None
        self.animation_viewer = None
        
        self.show_folder_selection()

    def clear_frame(self):
        if self.current_frame:
            self.current_frame.destroy()
        self.current_frame = Frame(self.root)
        self.current_frame.pack(fill='both', expand=True)

    def show_folder_selection(self):
        self.clear_frame()
        Label(self.current_frame, 
             text="Select the folder with the spritesheet image\n and the subfolder with the animations",
             font=('Arial', 14)).pack(pady=50)
        Button(self.current_frame, text="Select Folder", 
              command=self.select_folder, font=('Arial', 12)).pack()

    def select_folder(self):
        folder = filedialog.askdirectory(title="Select a folder")
        if folder:
            self.folder = folder
            self.show_main_menu()

    def show_main_menu(self):
        self.clear_frame()
        Label(self.current_frame, text=f"Selected folder:\n{self.folder}", 
             font=('Arial', 12)).pack(pady=20)
        
        Button(self.current_frame, text="Split Spritesheet", 
              command=self.show_sprite_splitter, width=20).pack(pady=10)
        Button(self.current_frame, text="View Animations", 
              command=self.show_animation_viewer, width=20).pack(pady=10)

    def show_sprite_splitter(self):
        self.clear_frame()
        self.spritesheet_viewer = SpritesheetViewer(
            self.current_frame, 
            self.folder, 
            self.show_main_menu
        )

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

        try:
            self.animation_viewer = AnimationViewer(self.current_frame, self.folder)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load animations: {str(e)}")
            self.show_main_menu()

if __name__ == "__main__":
    root = Tk()
    app = MainApplication(root)
    root.mainloop()