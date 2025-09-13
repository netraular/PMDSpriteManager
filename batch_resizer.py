# batch_resizer.py

import os
from tkinter import Frame, Label, Button, Entry, messagebox, filedialog, Canvas, Scrollbar
from PIL import Image, ImageTk
from sprite_sheet_handler import SpriteSheetHandler
from animation_data_handler import AnimationDataHandler
from animation_creator import AnimationCreator
import threading
import queue

class BatchResizer:
    def __init__(self, parent_frame, return_to_main_callback):
        self.parent_frame = parent_frame
        self.return_to_main = return_to_main_callback
        
        self.parent_folder = None
        self.project_folders = []
        self.current_folder_index = 0
        self.cancel_operation = False
        self.animation_creator = None
        self.sprite_previews = [] # To hold image references

        self.main_frame = Frame(self.parent_frame)
        self.main_frame.pack(fill='both', expand=True)
        self.status_label = None
        self.action_button = None

        self.setup_initial_view()

    def setup_initial_view(self):
        self.clear_frame()
        top_frame = Frame(self.main_frame); top_frame.pack(fill='x', padx=10, pady=5)
        Button(top_frame, text="Main Menu", command=self.return_to_main).pack(side='left')
        content_frame = Frame(self.main_frame); content_frame.pack(pady=50)
        Label(content_frame, text="Select a parent folder containing project subfolders.", font=('Arial', 14)).pack(pady=20)
        Button(content_frame, text="Select Parent Folder", command=self.select_parent_folder, font=('Arial', 12)).pack()

    def select_parent_folder(self):
        folder = filedialog.askdirectory(title="Select Parent Folder with Projects")
        if not folder: return
        self.parent_folder = folder
        self.project_folders = sorted([d for d in os.listdir(folder) if os.path.isdir(os.path.join(folder, d))])
        if not self.project_folders:
            messagebox.showwarning("No Folders Found", "No project subfolders were found."); return
        self.show_task_selection_view()

    def show_task_selection_view(self):
        self.clear_frame()
        self.cancel_operation = False
        top_frame = Frame(self.main_frame); top_frame.pack(fill='x', padx=10, pady=5)
        Button(top_frame, text="Main Menu", command=self.return_to_main).pack(side='left')
        content_frame = Frame(self.main_frame); content_frame.pack(pady=50)
        Label(content_frame, text=f"Folder: {os.path.basename(self.parent_folder)}", font=('Arial', 10)).pack(pady=(0, 10))
        Label(content_frame, text=f"Found {len(self.project_folders)} project subfolders.", font=('Arial', 10)).pack(pady=(0, 20))
        Label(content_frame, text="Choose a batch operation to perform:", font=('Arial', 14)).pack(pady=20)
        Button(content_frame, text="Generate Sprites", command=self.start_sprite_generation, font=('Arial', 12), width=30).pack(pady=10)
        Button(content_frame, text="Generate Optimized Animations", command=self.start_animation_generation, font=('Arial', 12), width=30).pack(pady=10)
        Button(content_frame, text="Preview Optimized Animations", command=self.show_pokemon_selection_view, font=('Arial', 12), width=30).pack(pady=10)

    def show_pokemon_selection_view(self):
        """Displays a list of projects with sprite previews to choose from."""
        self.clear_frame()
        self.sprite_previews.clear() # Clear previous image references
        top_frame = Frame(self.main_frame); top_frame.pack(fill='x', padx=10, pady=5)
        Button(top_frame, text="Back to Tasks", command=self.show_task_selection_view).pack(side='left')
        
        Label(self.main_frame, text="Select a Project to Preview", font=('Arial', 14)).pack(pady=10)
        
        canvas = Canvas(self.main_frame)
        scrollbar = Scrollbar(self.main_frame, orient="vertical", command=canvas.yview)
        scroll_frame = Frame(canvas)
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True); scrollbar.pack(side="right", fill="y")

        for folder_name in self.project_folders:
            sprite_path = os.path.join(self.parent_folder, folder_name, "Sprites", "sprite_1.png")
            
            try:
                if os.path.exists(sprite_path):
                    img = Image.open(sprite_path).convert("RGBA")
                else:
                    # Create a transparent placeholder if sprite is not found
                    img = Image.new('RGBA', (40, 40), (0, 0, 0, 0))
                
                img.thumbnail((40, 40))
                photo = ImageTk.PhotoImage(img)
                self.sprite_previews.append(photo) # Store reference
            
                btn = Button(scroll_frame, text=folder_name, image=photo, compound="left",
                             anchor="w", justify="left",
                             command=lambda f=folder_name: self.launch_previewer(f))
                btn.pack(padx=20, pady=5, fill='x')

            except Exception as e:
                print(f"Could not load preview for {folder_name}: {e}")
                # Fallback to a text-only button on error
                Button(scroll_frame, text=folder_name, 
                       command=lambda f=folder_name: self.launch_previewer(f), 
                       width=40).pack(padx=20, pady=5, anchor='w')


    def launch_previewer(self, folder_name):
        """Launches the AnimationCreator in preview mode for the selected project."""
        self.clear_frame()
        project_path = os.path.join(self.parent_folder, folder_name)
        self.animation_creator = AnimationCreator(
            self.main_frame,
            project_path,
            self.show_pokemon_selection_view, # Callback to return here
            start_in_preview_mode=True
        )

    def start_sprite_generation(self):
        self.current_folder_index = 0
        self.show_sprite_generation_view()

    def show_sprite_generation_view(self):
        self.clear_frame()
        if self.current_folder_index >= len(self.project_folders):
            messagebox.showinfo("Complete", "All project folders have been processed for sprites.")
            self.show_task_selection_view()
            return

        current_folder_name = self.project_folders[self.current_folder_index]
        self.current_project_path = os.path.join(self.parent_folder, current_folder_name)
        
        try:
            png_files = [f for f in os.listdir(self.current_project_path) if f.lower().endswith('.png')]
            if not png_files: raise FileNotFoundError("No PNG files found.")
            self.current_spritesheet_path = os.path.join(self.current_project_path, png_files[0])
        except Exception as e:
            messagebox.showerror("Error", f"Could not find a spritesheet in '{current_folder_name}': {e}. Skipping folder.")
            self.process_next_folder()
            return

        top_frame = Frame(self.main_frame); top_frame.pack(fill='x', padx=10, pady=5)
        Button(top_frame, text="Back to Task Selection", command=self.show_task_selection_view).pack(side='left')
        Button(top_frame, text="Skip Folder", command=self.process_next_folder).pack(side='left', padx=5)
        content_frame = Frame(self.main_frame); content_frame.pack(fill='both', expand=True, padx=20, pady=10)
        progress_text = (f"Processing {self.current_folder_index + 1} of {len(self.project_folders)}: {current_folder_name}")
        Label(content_frame, text=progress_text, font=('Arial', 10, 'bold')).pack(pady=5)
        
        try:
            img = Image.open(self.current_spritesheet_path); img.thumbnail((500, 400))
            self.img_tk = ImageTk.PhotoImage(img)
            Label(content_frame, image=self.img_tk).pack(pady=10)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load image {os.path.basename(self.current_spritesheet_path)}: {e}")
            self.process_next_folder()
            return

        form_frame = Frame(content_frame); form_frame.pack(pady=10)
        Label(form_frame, text="Size (width/height):").grid(row=0, column=0, padx=5)
        self.size_entry = Entry(form_frame, width=10); self.size_entry.grid(row=0, column=1, padx=5)
        self.size_entry.focus_set(); self.size_entry.bind("<Return>", self.process_current_folder_sprites)
        Button(form_frame, text="Process and Next", command=self.process_current_folder_sprites).grid(row=1, columnspan=2, pady=10)

    def process_current_folder_sprites(self, event=None):
        try:
            size = int(self.size_entry.get())
            if size <= 0: raise ValueError("Size must be a positive number.")
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid positive number for the size."); return
        try:
            output_folder = os.path.join(self.current_project_path, "Sprites")
            if os.path.exists(output_folder) and os.listdir(output_folder):
                msg = f"The 'Sprites' folder in '{os.path.basename(self.current_project_path)}' will be overwritten. Continue?"
                if not messagebox.askyesno("Confirmation", msg): self.process_next_folder(); return
            os.makedirs(output_folder, exist_ok=True)
            for file in os.listdir(output_folder): os.unlink(os.path.join(output_folder, file))
            handler = SpriteSheetHandler(self.current_spritesheet_path, remove_first_row=True, remove_first_col=False)
            sprites, _, _ = handler.split_sprites(size, size)
            if not sprites: raise Exception("Splitting the spritesheet yielded no sprites.")
            for idx, sprite in enumerate(sprites):
                bbox = sprite.getbbox()
                if bbox:
                    sprite = sprite.crop(bbox)
                sprite.save(os.path.join(output_folder, f"sprite_{idx + 1}.png"))
        except Exception as e:
            messagebox.showerror("Processing Error", f"An error occurred while processing the spritesheet: {e}")
        self.process_next_folder()

    def process_next_folder(self):
        self.current_folder_index += 1
        self.show_sprite_generation_view()

    def start_animation_generation(self):
        self.clear_frame(); self.cancel_operation = False
        top_frame = Frame(self.main_frame); top_frame.pack(fill='x', padx=10, pady=5)
        self.back_button = Button(top_frame, text="Back to Task Selection", command=self.show_task_selection_view)
        self.back_button.pack(side='left'); self.back_button.config(state="disabled")
        content_frame = Frame(self.main_frame); content_frame.pack(pady=20, fill='x')
        self.status_label = Label(content_frame, text="Preparing to generate animations...", font=('Arial', 12)); self.status_label.pack(pady=10)
        self.action_button = Button(content_frame, text="Cancel", command=self.request_cancel, bg="tomato"); self.action_button.pack(pady=10)
        self.progress_queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self._animation_generation_worker, args=(self.progress_queue,), daemon=True)
        self.worker_thread.start()
        self.parent_frame.after(100, self.check_progress_queue)

    def _animation_generation_worker(self, q):
        total_anims_saved, projects_failed = 0, 0
        for i, folder_name in enumerate(self.project_folders):
            if self.cancel_operation: q.put("Cancelled by user."); break
            project_path = os.path.join(self.parent_folder, folder_name)
            q.put(f"Processing ({i+1}/{len(self.project_folders)}): {folder_name}")
            try:
                handler = AnimationDataHandler(project_path)
                if not handler.anim_data:
                    print(f"Skipping {folder_name}: No valid animation data found in XML.")
                    projects_failed += 1; continue
                project_anims_saved = 0
                for index, anim in enumerate(handler.anim_data):
                    if self.cancel_operation: break
                    json_data = handler.generate_animation_data(index)
                    if json_data:
                        _, error = handler.export_optimized_animation(json_data)
                        if error: print(f"Failed to export {anim['name']} in {folder_name}: {error}")
                        else: project_anims_saved += 1
                if project_anims_saved > 0: total_anims_saved += project_anims_saved
                else: projects_failed += 1
            except Exception as e:
                print(f"Critical error processing project '{folder_name}': {e}"); projects_failed += 1
        q.put(f"DONE:{total_anims_saved}:{projects_failed}")

    def check_progress_queue(self):
        try:
            message = self.progress_queue.get_nowait()
            if isinstance(message, str) and message.startswith("DONE"):
                _, saved, failed = message.split(":")
                msg = f"Process finished.\n\nAnimations Exported: {saved}\nProjects Failed/Skipped: {failed}"
                if self.cancel_operation: msg = "Operation cancelled by user."
                messagebox.showinfo("Batch Export Complete", msg)
                self.show_task_selection_view()
            else:
                self.status_label.config(text=message)
                self.parent_frame.after(100, self.check_progress_queue)
        except queue.Empty:
            self.parent_frame.after(100, self.check_progress_queue)

    def request_cancel(self):
        self.cancel_operation = True
        self.action_button.config(state="disabled", text="Cancelling...")
        self.status_label.config(text="Cancellation requested, finishing current task...")

    def clear_frame(self):
        self.cancel_operation = True
        self.sprite_previews.clear()
        for widget in self.main_frame.winfo_children(): widget.destroy()