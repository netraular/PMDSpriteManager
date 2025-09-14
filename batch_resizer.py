# batch_resizer.py

import os
import pathlib
import zipfile
import shutil
import json
from tkinter import Frame, Label, Button, Entry, messagebox, filedialog, Canvas, Scrollbar, Text, END, Toplevel
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
        self.show_task_selection_view()

    def show_task_selection_view(self):
        self.clear_frame()
        self.cancel_operation = False
        if self.parent_folder:
            self.project_folders = sorted([d for d in os.listdir(self.parent_folder) if os.path.isdir(os.path.join(self.parent_folder, d))])

        top_frame = Frame(self.main_frame); top_frame.pack(fill='x', padx=10, pady=5)
        Button(top_frame, text="Main Menu", command=self.return_to_main).pack(side='left')
        content_frame = Frame(self.main_frame); content_frame.pack(pady=50)
        Label(content_frame, text=f"Folder: {os.path.basename(self.parent_folder)}", font=('Arial', 10)).pack(pady=(0, 10))
        Label(content_frame, text=f"Found {len(self.project_folders)} project subfolders.", font=('Arial', 10)).pack(pady=(0, 20))
        Label(content_frame, text="Choose a batch operation to perform:", font=('Arial', 14)).pack(pady=20)
        Button(content_frame, text="Generate Assets", command=self.show_asset_generation_view, font=('Arial', 12), width=30).pack(pady=10)
        Button(content_frame, text="Generate Sprites", command=self.start_sprite_generation, font=('Arial', 12), width=30).pack(pady=10)
        Button(content_frame, text="Generate Optimized Animations", command=self.start_animation_generation, font=('Arial', 12), width=30).pack(pady=10)
        Button(content_frame, text="Preview Optimized Animations", command=self.show_pokemon_selection_view, font=('Arial', 12), width=30).pack(pady=10)
        Button(content_frame, text="Export Final Assets", command=self.show_export_assets_view, font=('Arial', 12), width=30, bg="lightgreen").pack(pady=10)
        Button(content_frame, text="Export Final Assets (x2)", command=self.show_export_assets_x2_view, font=('Arial', 12), width=30, bg="lightblue").pack(pady=10)

    def show_asset_generation_view(self):
        self.clear_frame()
        top_frame = Frame(self.main_frame); top_frame.pack(fill='x', padx=10, pady=5)
        Button(top_frame, text="Back to Tasks", command=self.show_task_selection_view).pack(side='left')
        
        Label(self.main_frame, text="Asset Generation Workflow", font=('Arial', 14)).pack(pady=10)
        Label(self.main_frame, text=f"Target Folder: {self.parent_folder}", font=('Arial', 10)).pack(pady=5)

        button_frame = Frame(self.main_frame); button_frame.pack(pady=10)
        Button(button_frame, text="1. Create Folders from names.txt", command=self._create_folders_from_file, width=35).pack(pady=5)
        Button(button_frame, text="2. Uncompress ZIPs", command=self._uncompress_zips, width=35).pack(pady=5)
        Button(button_frame, text="3. Cleanup ZIP files", command=self._cleanup_zip_files, width=35).pack(pady=5)
        Button(button_frame, text="4. Show Asset Download Link", command=self._show_download_link, width=35).pack(pady=5)

        log_frame = Frame(self.main_frame); log_frame.pack(fill='both', expand=True, padx=10, pady=10)
        Label(log_frame, text="Log Output:").pack(anchor='w')
        self.log_text = Text(log_frame, height=15, wrap='word', state='disabled')
        log_scroll = Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.config(yscrollcommand=log_scroll.set)
        log_scroll.pack(side='right', fill='y')
        self.log_text.pack(side='left', fill='both', expand=True)

    def _log(self, message):
        if hasattr(self, 'log_text') and self.log_text.winfo_exists():
            self.log_text.config(state='normal')
            self.log_text.insert(END, message + "\n")
            self.log_text.see(END)
            self.log_text.config(state='disabled')
            self.parent_frame.update_idletasks()

    def _clear_log(self):
        if hasattr(self, 'log_text') and self.log_text.winfo_exists():
            self.log_text.config(state='normal')
            self.log_text.delete('1.0', END)
            self.log_text.config(state='disabled')

    def _create_folders_from_file(self):
        self._clear_log()
        self._log("--- 1. Starting: Create Folders from 'names.txt' ---")
        main_path = pathlib.Path(self.parent_folder)
        names_file_path = main_path / "names.txt"
        self._log(f"Reading from: '{names_file_path}'")

        if not names_file_path.exists():
            self._log(f"!! ERROR: Could not find the file '{names_file_path}'.")
            messagebox.showerror("Error", f"Could not find 'names.txt' in the target folder.")
            return

        created_count, skipped_count, error_count = 0, 0, 0
        try:
            with open(names_file_path, 'r', encoding='utf-8') as file:
                for line in file:
                    folder_name = line.strip()
                    if folder_name:
                        try:
                            folder_path = main_path / folder_name
                            if not folder_path.exists():
                                folder_path.mkdir()
                                self._log(f"-> Folder created: '{folder_name}'")
                                created_count += 1
                            else:
                                self._log(f"-> Folder already exists, skipping: '{folder_name}'")
                                skipped_count += 1
                        except OSError as e:
                            self._log(f"!! Error creating folder '{folder_name}': {e}"); error_count += 1
                    else:
                        self._log("-> Found an empty line, skipping.")
        except Exception as e:
            self._log(f"!! An unexpected error occurred: {e}")
            messagebox.showerror("Error", f"An unexpected error occurred: {e}"); return
        
        summary = f"Folder creation finished.\n\nCreated: {created_count}\nSkipped (already exist): {skipped_count}\nErrors: {error_count}"
        self._log(summary); messagebox.showinfo("Complete", summary)

    def _uncompress_zips(self):
        self._clear_log()
        self._log("--- 2. Starting: Uncompress ZIPs ---")
        main_path = pathlib.Path(self.parent_folder)
        destination_folder_name = "Animations"
        
        subfolders = [item for item in main_path.iterdir() if item.is_dir()]
        if not subfolders:
            self._log("No subfolders found in this directory.")
            messagebox.showinfo("Info", "No subfolders found to process."); return

        success_count, skipped_count, error_count = 0, 0, 0
        for folder in subfolders:
            self._log(f"📂 Checking folder: {folder.name}")
            try:
                zip_file = next(folder.glob('*.zip'))
                self._log(f"  -> Found zip file: {zip_file.name}")
                destination_path = folder / destination_folder_name
                destination_path.mkdir(exist_ok=True)
                with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                    zip_ref.extractall(destination_path)
                self._log(f"  ✅ Success! Uncompressed to: '{destination_path.relative_to(main_path)}'")
                success_count += 1
            except StopIteration:
                self._log("  -> No .zip file found. Skipping."); skipped_count += 1
            except zipfile.BadZipFile:
                self._log(f"  ❌ Error! The file '{zip_file.name}' is corrupt or not a valid zip file."); error_count += 1
            except Exception as e:
                self._log(f"  ❌ Error! An unexpected problem occurred: {e}"); error_count += 1
            self._log("-" * 20)
        
        summary = f"Uncompress process finished.\n\nSuccessfully unzipped: {success_count}\nFolders skipped (no zip): {skipped_count}\nErrors: {error_count}"
        self._log(summary); messagebox.showinfo("Complete", summary)

    def _cleanup_zip_files(self):
        self._clear_log()
        self._log("--- 3. Starting: Cleanup ZIP files ---")
        main_path = pathlib.Path(self.parent_folder)
        
        zip_files_to_delete = list(main_path.rglob('*.zip'))
        if not zip_files_to_delete:
            self._log("✅ No residual .zip files found.")
            messagebox.showinfo("Info", "No .zip files found to clean up."); return

        self._log("ATTENTION! The following .zip files were found for deletion:")
        for file_path in zip_files_to_delete:
            self._log(f"  -> {file_path.relative_to(main_path)}")
        
        confirmation = messagebox.askyesno(
            "Confirm Deletion",
            f"Found {len(zip_files_to_delete)} .zip files.\n\nThis action is IRREVERSIBLE.\nAre you sure you want to delete them all?"
        )

        if confirmation:
            self._log("\n✅ Confirmation received. Starting deletion...")
            deleted_count, error_count = 0, 0
            for file_path in zip_files_to_delete:
                try:
                    file_path.unlink()
                    self._log(f"  🗑️  Deleted: {file_path.relative_to(main_path)}"); deleted_count += 1
                except Exception as e:
                    self._log(f"  ❌ Error! Could not delete {file_path.name}: {e}"); error_count += 1
            
            summary = f"Cleanup finished.\n\nFiles deleted: {deleted_count}\nErrors: {error_count}"
            self._log(summary); messagebox.showinfo("Complete", summary)
        else:
            self._log("\n❌ Operation cancelled. No files have been deleted.")
            messagebox.showinfo("Cancelled", "Operation cancelled. No files were deleted.")

    def _show_download_link(self):
        url = "https://sprites.pmdcollab.org/"
        popup = Toplevel(self.parent_frame); popup.title("Asset Download Link")
        Label(popup, text="Copy the link below to download assets:", padx=20, pady=10).pack()
        link_entry = Entry(popup, width=50); link_entry.pack(padx=20, pady=5)
        link_entry.insert(0, url); link_entry.config(state='readonly')
        Button(popup, text="Close", command=popup.destroy).pack(pady=10)
        popup.transient(self.parent_frame); popup.grab_set(); self.parent_frame.wait_window(popup)

    def show_pokemon_selection_view(self):
        self.clear_frame()
        self.sprite_previews.clear()
        top_frame = Frame(self.main_frame); top_frame.pack(fill='x', padx=10, pady=5)
        Button(top_frame, text="Back to Tasks", command=self.show_task_selection_view).pack(side='left')
        Label(self.main_frame, text="Select a Project to Preview", font=('Arial', 14)).pack(pady=10)
        canvas = Canvas(self.main_frame); scrollbar = Scrollbar(self.main_frame, orient="vertical", command=canvas.yview)
        scroll_frame = Frame(canvas); scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw"); canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True); scrollbar.pack(side="right", fill="y")
        for folder_name in self.project_folders:
            sprite_path = os.path.join(self.parent_folder, folder_name, "Sprites", "sprite_1.png")
            try:
                img = Image.open(sprite_path).convert("RGBA") if os.path.exists(sprite_path) else Image.new('RGBA', (40, 40), (0, 0, 0, 0))
                img.thumbnail((40, 40)); photo = ImageTk.PhotoImage(img); self.sprite_previews.append(photo)
                btn = Button(scroll_frame, text=folder_name, image=photo, compound="left", anchor="w", justify="left", command=lambda f=folder_name: self.launch_previewer(f))
                btn.pack(padx=20, pady=5, fill='x')
            except Exception as e:
                print(f"Could not load preview for {folder_name}: {e}")
                Button(scroll_frame, text=folder_name, command=lambda f=folder_name: self.launch_previewer(f), width=40).pack(padx=20, pady=5, anchor='w')

    def launch_previewer(self, folder_name):
        self.clear_frame()
        project_path = os.path.join(self.parent_folder, folder_name)
        self.animation_creator = AnimationCreator(self.main_frame, project_path, self.show_pokemon_selection_view, start_in_preview_mode=True)

    def start_sprite_generation(self):
        self.current_folder_index = 0
        self.show_sprite_generation_view()

    def show_sprite_generation_view(self):
        self.clear_frame()
        if self.current_folder_index >= len(self.project_folders):
            messagebox.showinfo("Complete", "All project folders have been processed for sprites.")
            self.show_task_selection_view(); return

        current_folder_name = self.project_folders[self.current_folder_index]
        self.current_project_path = os.path.join(self.parent_folder, current_folder_name)
        try:
            png_files = [f for f in os.listdir(self.current_project_path) if f.lower().endswith('.png')]
            if not png_files: raise FileNotFoundError("No PNG files found.")
            self.current_spritesheet_path = os.path.join(self.current_project_path, png_files[0])
        except Exception as e:
            messagebox.showerror("Error", f"Could not find a spritesheet in '{current_folder_name}': {e}. Skipping folder.")
            self.process_next_folder(); return

        top_frame = Frame(self.main_frame); top_frame.pack(fill='x', padx=10, pady=5)
        Button(top_frame, text="Back to Task Selection", command=self.show_task_selection_view).pack(side='left')
        Button(top_frame, text="Skip Folder", command=self.process_next_folder).pack(side='left', padx=5)
        content_frame = Frame(self.main_frame); content_frame.pack(fill='both', expand=True, padx=20, pady=10)
        progress_text = f"Processing {self.current_folder_index + 1} of {len(self.project_folders)}: {current_folder_name}"
        Label(content_frame, text=progress_text, font=('Arial', 10, 'bold')).pack(pady=5)
        try:
            img = Image.open(self.current_spritesheet_path); img.thumbnail((500, 400)); self.img_tk = ImageTk.PhotoImage(img)
            Label(content_frame, image=self.img_tk).pack(pady=10)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load image {os.path.basename(self.current_spritesheet_path)}: {e}")
            self.process_next_folder(); return

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
            os.makedirs(output_folder, exist_ok=True)
            for file in os.listdir(output_folder): os.unlink(os.path.join(output_folder, file))
            handler = SpriteSheetHandler(self.current_spritesheet_path, remove_first_row=True, remove_first_col=False)
            sprites, _, _ = handler.split_sprites(size, size)
            if not sprites: raise Exception("Splitting the spritesheet yielded no sprites.")
            for idx, sprite in enumerate(sprites):
                bbox = sprite.getbbox()
                if bbox: sprite = sprite.crop(bbox)
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
                    print(f"Skipping {folder_name}: No valid animation data found in XML."); projects_failed += 1; continue
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

    def show_export_assets_view(self):
        self.clear_frame()
        top_frame = Frame(self.main_frame); top_frame.pack(fill='x', padx=10, pady=5)
        Button(top_frame, text="Back to Tasks", command=self.show_task_selection_view).pack(side='left')
        
        Label(self.main_frame, text="Export Final Assets", font=('Arial', 14)).pack(pady=10)
        Label(self.main_frame, text="This will find common animations and copy them with their sprites to a new 'output' folder.", wraplength=600).pack(pady=5)
        Label(self.main_frame, text=f"Target Folder: {self.parent_folder}", font=('Arial', 10)).pack(pady=5)

        self.action_button = Button(self.main_frame, text="Start Export", command=self._start_export_assets, font=('Arial', 12), width=20)
        self.action_button.pack(pady=20)

        log_frame = Frame(self.main_frame); log_frame.pack(fill='both', expand=True, padx=10, pady=10)
        Label(log_frame, text="Log Output:").pack(anchor='w')
        self.log_text = Text(log_frame, height=15, wrap='word', state='disabled')
        log_scroll = Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.config(yscrollcommand=log_scroll.set)
        log_scroll.pack(side='right', fill='y')
        self.log_text.pack(side='left', fill='both', expand=True)

    def _start_export_assets(self):
        self.cancel_operation = False
        self._clear_log()
        self.action_button.config(text="Cancel", command=self.request_cancel, bg="tomato")
        
        self.export_progress_queue = queue.Queue()
        self.export_worker_thread = threading.Thread(target=self._export_assets_worker, args=(self.export_progress_queue,), daemon=True)
        self.export_worker_thread.start()
        self.parent_frame.after(100, self._check_export_progress_queue)

    def _export_assets_worker(self, q):
        main_path = pathlib.Path(self.parent_folder)
        q.put(f"Analyzing folder structure in: {main_path}\n")

        animations_by_character = {}
        character_folders = [d for d in main_path.iterdir() if d.is_dir() and not d.name.startswith(('.', 'output'))]

        if not character_folders:
            q.put("Error: No character subfolders found in the specified directory.")
            q.put("DONE:ERROR"); return

        for character_folder in character_folders:
            if self.cancel_operation: q.put("Cancelled."); q.put("DONE:CANCEL"); return
            animation_data_path = character_folder / "AnimationData"
            if not animation_data_path.is_dir(): continue

            animation_names = {f.name for f in animation_data_path.rglob('*.json')}
            if animation_names:
                animations_by_character[character_folder.name] = animation_names
                q.put(f"-> Character '{character_folder.name}' found with {len(animation_names)} animations.")
            else:
                animations_by_character[character_folder.name] = set()

        if not animations_by_character:
            q.put("\nNo characters with valid 'AnimationData' folders were found.")
            q.put("DONE:ERROR"); return

        set_list = list(animations_by_character.values())
        common_animations = set_list[0].copy()
        for next_set in set_list[1:]: common_animations.intersection_update(next_set)

        if not common_animations:
            q.put("\n❌ No .json animation was found to be common to all characters. Process finished.")
            q.put("DONE:COMPLETE"); return

        q.put("\n-----------------------------------------------------")
        q.put("✅ Common .json animations found:")
        for file_name in sorted(list(common_animations)): q.put(f"   - {file_name}")
        q.put("-----------------------------------------------------\n")

        q.put("Starting export process...")
        output_dir = main_path / "output"
        if output_dir.exists():
            q.put(f"Deleting existing 'output' folder for a clean export...")
            try:
                shutil.rmtree(output_dir)
            except Exception as e:
                q.put(f"Error deleting output folder: {e}"); q.put("DONE:ERROR"); return
        output_dir.mkdir()

        for character_folder in character_folders:
            if self.cancel_operation: q.put("Cancelled."); q.put("DONE:CANCEL"); return
            character_name = character_folder.name
            q.put(f"\n--- Processing character: {character_name} ---")

            source_animation_data_path = character_folder / "AnimationData"
            if not source_animation_data_path.is_dir():
                q.put(f"Warning: Character '{character_name}' has no 'AnimationData'. Skipping."); continue

            output_character_dir = output_dir / character_name; output_character_dir.mkdir()
            output_sprites_dir = output_character_dir / "Sprites"; output_sprites_dir.mkdir()
            copied_png_names = set()

            for json_name in sorted(list(common_animations)):
                if self.cancel_operation: q.put("Cancelled."); q.put("DONE:CANCEL"); return
                try:
                    source_json_path = next(source_animation_data_path.rglob(json_name))
                    dest_json_path = output_character_dir / json_name
                    shutil.copy2(source_json_path, dest_json_path)
                    q.put(f"  ✅ Copied JSON: {json_name}")
                except StopIteration:
                    q.put(f"  ❌ Error: Could not find the file '{json_name}' for '{character_name}'."); continue

                animation_name = json_name.removesuffix("-AnimData.json")
                source_sprites_path = source_animation_data_path / animation_name

                if not source_sprites_path.is_dir():
                    q.put(f"  - Warning: Sprite folder '{animation_name}' for this JSON was not found."); continue

                q.put(f"  - Searching for sprites in: '{source_sprites_path.relative_to(main_path)}'")
                found_pngs = list(source_sprites_path.glob('*.png'))

                if not found_pngs:
                    q.put("    - No .png files were found in this folder."); continue

                for source_png in found_pngs:
                    if source_png.name not in copied_png_names:
                        shutil.copy2(source_png, output_sprites_dir)
                        copied_png_names.add(source_png.name)
                    else:
                        q.put(f"    - Skipping (duplicate file name): {source_png.name}")

        q.put("\n-----------------------------------------------------")
        q.put(f"✅ Process completed. Files have been generated in the folder: {output_dir}")
        q.put("-----------------------------------------------------")
        q.put("DONE:COMPLETE")

    def _check_export_progress_queue(self):
        try:
            message = self.export_progress_queue.get_nowait()
            if isinstance(message, str) and message.startswith("DONE"):
                status = message.split(":")[1]
                if status == "COMPLETE": msg = "Export process completed successfully."
                elif status == "CANCEL": msg = "Operation cancelled by user."
                else: msg = "An error occurred during the export process. Check the log for details."
                
                messagebox.showinfo("Export Complete", msg)
                self.show_task_selection_view()
            else:
                self._log(message)
                self.parent_frame.after(100, self._check_export_progress_queue)
        except queue.Empty:
            self.parent_frame.after(100, self._check_export_progress_queue)

    def show_export_assets_x2_view(self):
        self.clear_frame()
        top_frame = Frame(self.main_frame); top_frame.pack(fill='x', padx=10, pady=5)
        Button(top_frame, text="Back to Tasks", command=self.show_task_selection_view).pack(side='left')
        
        Label(self.main_frame, text="Export Final Assets (x2)", font=('Arial', 14)).pack(pady=10)
        description = "This will create a new 'output x2' folder based on the existing 'output' folder.\nAll sprites will be resized to 200% (pixel-perfect), and all JSON data (frame sizes, offsets) will be adjusted accordingly."
        Label(self.main_frame, text=description, wraplength=600).pack(pady=5)
        Label(self.main_frame, text=f"Target Folder: {self.parent_folder}", font=('Arial', 10)).pack(pady=5)

        self.action_button = Button(self.main_frame, text="Start x2 Export", command=self._start_export_assets_x2, font=('Arial', 12), width=20)
        self.action_button.pack(pady=20)

        log_frame = Frame(self.main_frame); log_frame.pack(fill='both', expand=True, padx=10, pady=10)
        Label(log_frame, text="Log Output:").pack(anchor='w')
        self.log_text = Text(log_frame, height=15, wrap='word', state='disabled')
        log_scroll = Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.config(yscrollcommand=log_scroll.set)
        log_scroll.pack(side='right', fill='y')
        self.log_text.pack(side='left', fill='both', expand=True)

    def _start_export_assets_x2(self):
        self.cancel_operation = False
        self._clear_log()
        self.action_button.config(text="Cancel", command=self.request_cancel, bg="tomato")
        
        self.export_progress_queue = queue.Queue()
        self.export_worker_thread = threading.Thread(target=self._export_assets_x2_worker, args=(self.export_progress_queue,), daemon=True)
        self.export_worker_thread.start()
        self.parent_frame.after(100, self._check_export_progress_queue)

    def _export_assets_x2_worker(self, q):
        main_path = pathlib.Path(self.parent_folder)
        source_dir = main_path / "output"
        dest_dir = main_path / "output x2"

        if not source_dir.is_dir():
            q.put(f"❌ ERROR: The source folder '{source_dir}' does not exist.")
            q.put("Please run the 'Export Final Assets' task first.")
            q.put("DONE:ERROR"); return

        q.put(f"Starting x2 export from '{source_dir}' to '{dest_dir}'...")
        if dest_dir.exists():
            q.put(f"Deleting existing '{dest_dir}' for a clean export...")
            try:
                shutil.rmtree(dest_dir)
            except Exception as e:
                q.put(f"Error deleting destination folder: {e}"); q.put("DONE:ERROR"); return
        dest_dir.mkdir()

        character_folders = [d for d in source_dir.iterdir() if d.is_dir()]

        for char_folder in character_folders:
            if self.cancel_operation: q.put("Cancelled."); q.put("DONE:CANCEL"); return
            char_name = char_folder.name
            q.put(f"\n--- Processing character: {char_name} ---")

            dest_char_dir = dest_dir / char_name; dest_char_dir.mkdir()

            # Process Sprites
            source_sprites_dir = char_folder / "Sprites"
            dest_sprites_dir = dest_char_dir / "Sprites"
            if source_sprites_dir.is_dir():
                dest_sprites_dir.mkdir()
                q.put("  Resizing sprites...")
                for sprite_file in source_sprites_dir.glob("*.png"):
                    if self.cancel_operation: q.put("Cancelled."); q.put("DONE:CANCEL"); return
                    try:
                        with Image.open(sprite_file) as img:
                            new_size = (img.width * 2, img.height * 2)
                            resized_img = img.resize(new_size, Image.NEAREST)
                            resized_img.save(dest_sprites_dir / sprite_file.name)
                    except Exception as e:
                        q.put(f"    ❌ Error resizing {sprite_file.name}: {e}")
                q.put("  ✅ Sprites resized.")

            # Process JSONs
            q.put("  Adjusting JSON files...")
            for json_file in char_folder.glob("*.json"):
                if self.cancel_operation: q.put("Cancelled."); q.put("DONE:CANCEL"); return
                try:
                    with open(json_file, 'r') as f:
                        data = json.load(f)
                    
                    data['framewidth'] *= 2
                    data['frameheight'] *= 2
                    for group in data.get('sprites', {}).values():
                        for frame in group.get('frames', []):
                            if 'offset' in frame and len(frame['offset']) == 2:
                                frame['offset'][0] *= 2
                                frame['offset'][1] *= 2
                    
                    with open(dest_char_dir / json_file.name, 'w') as f:
                        json.dump(data, f, indent=4)
                except Exception as e:
                    q.put(f"    ❌ Error processing {json_file.name}: {e}")
            q.put("  ✅ JSON files adjusted.")

        q.put("\n-----------------------------------------------------")
        q.put(f"✅ x2 Export completed. Files are in: {dest_dir}")
        q.put("-----------------------------------------------------")
        q.put("DONE:COMPLETE")

    def request_cancel(self):
        self.cancel_operation = True
        if hasattr(self, 'action_button') and self.action_button.winfo_exists():
            self.action_button.config(state="disabled", text="Cancelling...")
        
        msg = "Cancellation requested, finishing current task..."
        if hasattr(self, 'status_label') and self.status_label and self.status_label.winfo_exists():
            self.status_label.config(text=msg)
        elif hasattr(self, 'log_text') and self.log_text and self.log_text.winfo_exists():
            self._log(msg)

    def clear_frame(self):
        self.cancel_operation = True
        self.sprite_previews.clear()
        for widget in self.main_frame.winfo_children(): widget.destroy()