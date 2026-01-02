# main.py

import os
from tkinter import Tk, filedialog, Frame, Label, Button, messagebox
from PIL import Image, ImageTk
from core.sprite_sheet_handler import SpriteSheetHandler
from individual.animation_viewer import AnimationViewer
from individual.animation_creator import AnimationCreator
from batch.batch_resizer import BatchResizer
from individual.spritesheet_assembler import SpritesheetAssembler
from individual.assembled_animation_previewer import AssembledAnimationPreviewer

class MainApplication:
    def __init__(self, root):
        self.root = root
        self.root.title("Sprite Sheet Tool")
        self.root.geometry("1920x1080")
        
        self.breadcrumb_frame = Frame(self.root, bd=1, relief="sunken")
        self.breadcrumb_frame.pack(fill='x', side='top', ipady=2)

        self.content_area = Frame(self.root)
        self.content_area.pack(fill='both', expand=True)

        self.current_frame = None
        self.folder = None
        self.animation_viewer = None
        self.animation_creator = None
        self.batch_resizer = None
        self.animation_assembler = None
        self.assembled_previewer = None
        
        self.show_folder_selection()

    def update_breadcrumbs(self, path):
        for widget in self.breadcrumb_frame.winfo_children():
            widget.destroy()

        for i, (text, command) in enumerate(path):
            if i < len(path) - 1:
                btn = Button(self.breadcrumb_frame, text=text, command=command, relief="flat", fg="blue", cursor="hand2", bd=0, highlightthickness=0)
                btn.pack(side='left', padx=(2,0))
                Label(self.breadcrumb_frame, text=" > ").pack(side='left')
            else:
                Label(self.breadcrumb_frame, text=text, font=('Arial', 10, 'bold')).pack(side='left', padx=(2,0))

    def clear_frame(self):
        if self.current_frame: self.current_frame.destroy()
        self.current_frame = Frame(self.content_area)
        self.current_frame.pack(fill='both', expand=True)

    def show_folder_selection(self):
        self.clear_frame()
        self.update_breadcrumbs([("Workflow Selection", self.show_folder_selection)])
        Label(self.current_frame, text="Welcome to the PMD Sprite Manager", font=('Arial', 16, 'bold')).pack(pady=(50, 10))
        Label(self.current_frame, text="Please choose your workflow:", font=('Arial', 12)).pack(pady=(10, 30))
        Button(self.current_frame, text="Manage individual character", command=self.select_project_folder, font=('Arial', 12), width=25, height=2).pack(pady=10)
        Button(self.current_frame, text="Batch Process Spritesheets", command=self.launch_batch_resizer, font=('Arial', 12), width=25, height=2).pack(pady=10)

    def select_project_folder(self):
        folder = filedialog.askdirectory(title="Select a Pokémon Project Folder")
        if folder:
            self.folder = folder
            self.show_main_menu()

    def show_main_menu(self):
        self.clear_frame()
        path = [
            ("Workflow Selection", self.show_folder_selection),
            (f"Character: {os.path.basename(self.folder)}", self.show_main_menu)
        ]
        self.update_breadcrumbs(path)
        Label(self.current_frame, text=f"Selected folder:\n{self.folder}", font=('Arial', 12)).pack(pady=20)
        Button(self.current_frame, text="Process Spritesheet", command=self.show_animation_creator, width=25).pack(pady=10)
        Button(self.current_frame, text="Edit Animations", command=self.show_animation_viewer, width=25).pack(pady=10)
        Button(self.current_frame, text="All Animations Preview", command=self.show_json_previewer, width=25).pack(pady=10)
        Button(self.current_frame, text="Assemble Spritesheets", command=self.show_spritesheet_assembler, width=25).pack(pady=10)
        Button(self.current_frame, text="Preview Assembled Animations", command=self.show_assembled_previewer, width=25, bg="lightyellow").pack(pady=10)
        Button(self.current_frame, text="Back to Workflow Selection", command=self.show_folder_selection).pack(pady=20)

    def show_animation_viewer(self):
        self.clear_frame()
        path = [
            ("Workflow Selection", self.show_folder_selection),
            (f"Character: {os.path.basename(self.folder)}", self.show_main_menu),
            ("Edit Animations", self.show_animation_viewer)
        ]
        self.update_breadcrumbs(path)

        control_frame = Frame(self.current_frame); control_frame.pack(fill='x', padx=10, pady=5)
        Button(control_frame, text="Main Menu", command=self.show_main_menu).pack(side='left')
        Button(control_frame, text="Generate JSON", command=lambda: self.animation_viewer.generate_json()).pack(side='left', padx=5)
        Button(control_frame, text="View Sprites", command=lambda: self.animation_viewer.view_sprites()).pack(side='left', padx=5)
        Button(control_frame, text="Save All Animations", command=lambda: self.animation_viewer.save_all_animations(), bg="lightblue").pack(side='left', padx=5)
        try:
            self.animation_viewer = AnimationViewer(self.current_frame, self.folder)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load animations: {str(e)}")
            self.show_main_menu()

    def show_animation_creator(self):
        self.clear_frame()
        base_path = [
            ("Workflow Selection", self.show_folder_selection),
            (f"Character: {os.path.basename(self.folder)}", self.show_main_menu)
        ]
        self.animation_creator = AnimationCreator(self.current_frame, self.folder, self.show_main_menu, self.update_breadcrumbs, base_path)

    def show_json_previewer(self):
        self.clear_frame()
        optimized_folder = os.path.join(self.folder, "AnimationData")
        if not os.path.exists(optimized_folder):
            messagebox.showerror("Error", "The 'AnimationData' folder is missing.\nPlease generate animations first.")
            self.show_main_menu()
            return
        
        base_path = [
            ("Workflow Selection", self.show_folder_selection),
            (f"Character: {os.path.basename(self.folder)}", self.show_main_menu)
        ]
        self.animation_creator = AnimationCreator(
            self.current_frame,
            self.folder,
            self.show_main_menu,
            update_breadcrumbs_callback=self.update_breadcrumbs,
            base_path=base_path,
            start_in_preview_mode=True
        )

    def show_spritesheet_assembler(self):
        self.clear_frame()
        base_path = [
            ("Workflow Selection", self.show_folder_selection),
            (f"Character: {os.path.basename(self.folder)}", self.show_main_menu)
        ]
        self.animation_assembler = SpritesheetAssembler(self.current_frame, self.folder, self.show_main_menu, self.update_breadcrumbs, base_path)

    def show_assembled_previewer(self):
        self.clear_frame()
        base_path = [
            ("Workflow Selection", self.show_folder_selection),
            (f"Character: {os.path.basename(self.folder)}", self.show_main_menu)
        ]
        self.assembled_previewer = AssembledAnimationPreviewer(self.current_frame, self.folder, self.show_main_menu, self.update_breadcrumbs, base_path)

    def launch_batch_resizer(self):
        self.clear_frame()
        base_path = [("Workflow Selection", self.show_folder_selection)]
        self.batch_resizer = BatchResizer(self.current_frame, self.show_folder_selection, self.update_breadcrumbs, base_path)

if __name__ == "__main__":
    root = Tk()
    app = MainApplication(root)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\nApplication closed by user.")
        root.destroy()