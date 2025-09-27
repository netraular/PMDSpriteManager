# batch_resizer.py

import os
import pathlib
import zipfile
import shutil
import json
import threading
import queue
import concurrent.futures
from tkinter import Frame, Label, Button, Entry, messagebox, filedialog, Canvas, Scrollbar, Text, END, Toplevel, StringVar, OptionMenu
from PIL import Image, ImageTk
from animation_data_handler import AnimationDataHandler
from animation_creator import AnimationCreator
from sprite_sheet_handler import SpriteSheetHandler

class BatchResizer:
    def __init__(self, parent_frame, return_to_main_callback, update_breadcrumbs_callback=None, base_path=None):
        self.parent_frame = parent_frame
        self.return_to_main = return_to_main_callback
        self.update_breadcrumbs = update_breadcrumbs_callback
        self.base_path = base_path if base_path is not None else []
        
        self.parent_folder = None
        self.project_folders = []
        self.current_folder_index = 0
        self.cancel_operation = False
        self.animation_creator = None
        self.sprite_previews = [] # To hold image references

        self.main_frame = Frame(self.parent_frame)
        self.main_frame.pack(fill='both', expand=True)

        # UI elements for generic task view
        self.action_button = None
        self.log_text = None
        
        # Threading and progress
        self.progress_queue = None
        self.worker_thread = None

        self.setup_initial_view()

    def clear_frame(self):
        self.cancel_operation = True # Signal any running threads to stop
        self.sprite_previews.clear()
        if self.animation_creator:
            self.animation_creator.clear_frame()
            self.animation_creator = None
        for widget in self.main_frame.winfo_children():
            widget.destroy()

    def request_cancel(self):
        self.cancel_operation = True
        if self.action_button and self.action_button.winfo_exists():
            self.action_button.config(state="disabled", text="Cancelling...")
        self._log("Cancellation requested, finishing current operation...")

    # --- Main UI Navigation ---

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
        if self.update_breadcrumbs:
            path = self.base_path + [("Batch Tasks", self.show_task_selection_view)]
            self.update_breadcrumbs(path)
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
        
        Button(content_frame, text="Generate Assets", command=self.show_asset_generation_view, font=('Arial', 12), width=35).pack(pady=10)
        Button(content_frame, text="Generate Sprites", command=self.start_sprite_generation, font=('Arial', 12), width=35).pack(pady=10)
        Button(content_frame, text="Generate Optimized Animations", command=self.start_animation_generation, font=('Arial', 12), width=35).pack(pady=10)
        Button(content_frame, text="Export Final Assets", command=self.show_export_assets_view, font=('Arial', 12), width=35, bg="lightgreen").pack(pady=10)
        Button(content_frame, text="Export Final Assets (x2)", command=self.show_export_assets_x2_view, font=('Arial', 12), width=35, bg="lightblue").pack(pady=10)
        Button(content_frame, text="Generate Shadow Sprites", command=self.show_shadow_generation_view, font=('Arial', 12), width=35).pack(pady=10)
        Button(content_frame, text="Preview Optimized Animations", command=self.show_optimized_animation_previewer, font=('Arial', 12), width=35).pack(pady=10)

    # --- Task View Setup Methods (using the generic framework) ---

    def start_animation_generation(self):
        description = "Automatically identifies sprites and generates optimized JSON data for all animations in each project subfolder."
        self._setup_task_view(
            title="Generate Optimized Animations",
            description=description,
            start_button_text="Start Generation",
            worker_function=self._animation_generation_worker
        )

    def show_export_assets_view(self):
        description = "This will find common animations and copy them with their sprites to a new 'output' folder."
        self._setup_task_view(
            title="Export Final Assets",
            description=description,
            start_button_text="Start Export",
            worker_function=self._export_assets_worker
        )

    def show_export_assets_x2_view(self):
        description = "This will create a new 'output x2' folder based on the existing 'output' folder.\nAll sprites will be resized to 200% (pixel-perfect), and all JSON data (frame sizes, offsets) will be adjusted accordingly."
        self._setup_task_view(
            title="Export Final Assets (x2)",
            description=description,
            start_button_text="Start x2 Export",
            worker_function=self._export_assets_x2_worker
        )

    def show_shadow_generation_view(self):
        description = "This will find the 'sprite_shadow.png' for each character and copy it into the 'output' folder.\nA 2x version will be created for the 'output x2' folder."
        self._setup_task_view(
            title="Generate Shadow Sprites",
            description=description,
            start_button_text="Start Generation",
            worker_function=self._shadow_generation_worker
        )

    # --- Generic Task Execution Framework ---

    def _setup_task_view(self, title, description, start_button_text, worker_function):
        if self.update_breadcrumbs:
            path = self.base_path + [
                ("Batch Tasks", self.show_task_selection_view),
                (title, lambda: self._setup_task_view(title, description, start_button_text, worker_function))
            ]
            self.update_breadcrumbs(path)
        
        self.clear_frame()
        top_frame = Frame(self.main_frame); top_frame.pack(fill='x', padx=10, pady=5)
        Button(top_frame, text="Back to Tasks", command=self.show_task_selection_view).pack(side='left')
        
        Label(self.main_frame, text=title, font=('Arial', 14)).pack(pady=10)
        if description:
            Label(self.main_frame, text=description, wraplength=600).pack(pady=5)
        Label(self.main_frame, text=f"Target Folder: {self.parent_folder}", font=('Arial', 10)).pack(pady=5)

        self.action_button = Button(self.main_frame, text=start_button_text, command=lambda: self._start_task(worker_function), font=('Arial', 12), width=20)
        self.action_button.pack(pady=20)

        log_frame = Frame(self.main_frame); log_frame.pack(fill='both', expand=True, padx=10, pady=10)
        Label(log_frame, text="Log Output:").pack(anchor='w')
        self.log_text = Text(log_frame, height=15, wrap='word', state='disabled')
        log_scroll = Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.config(yscrollcommand=log_scroll.set)
        log_scroll.pack(side='right', fill='y')
        self.log_text.pack(side='left', fill='both', expand=True)

    def _start_task(self, worker_function):
        self.cancel_operation = False
        self._clear_log()
        self.action_button.config(text="Cancel", command=self.request_cancel, bg="tomato")
        
        self.progress_queue = queue.Queue()
        self.worker_thread = threading.Thread(target=worker_function, args=(self.progress_queue,), daemon=True)
        self.worker_thread.start()
        self.parent_frame.after(100, self._check_progress_queue)

    def _check_progress_queue(self):
        try:
            message = self.progress_queue.get_nowait()
            if isinstance(message, str) and message.startswith("DONE"):
                parts = message.split(":")
                status = parts[1]
                
                msg = ""
                title = "Batch Process Complete"
                if self.cancel_operation:
                    msg = "Operation cancelled by user."
                elif status == "COMPLETE":
                    msg = "Process completed successfully."
                elif status == "CANCEL":
                    msg = "Operation cancelled by user."
                elif status == "ERROR":
                    msg = "An error occurred. Check the log for details."
                else: # Assumes the format DONE:saved_count:failed_count
                    saved, failed = parts[1], parts[2]
                    msg = f"Process finished.\n\nSuccessfully processed: {saved}\nFailed/Skipped: {failed}"
                
                messagebox.showinfo(title, msg)
                self.show_task_selection_view()
            else:
                self._log(message)
                self.parent_frame.after(100, self._check_progress_queue)
        except queue.Empty:
            self.parent_frame.after(100, self._check_progress_queue)

    def _log(self, message):
        if self.log_text and self.log_text.winfo_exists():
            self.log_text.config(state='normal')
            self.log_text.insert(END, message + "\n")
            self.log_text.see(END)
            self.log_text.config(state='disabled')
            self.parent_frame.update_idletasks()

    def _clear_log(self):
        if self.log_text and self.log_text.winfo_exists():
            self.log_text.config(state='normal')
            self.log_text.delete('1.0', END)
            self.log_text.config(state='disabled')

    # --- Task Worker Functions (Background Logic) ---

    def _process_project_for_anim_gen(self, project_path, folder_name, q):
        if self.cancel_operation:
            return 0, 0, True

        q.put(f"Processing: {folder_name}")
        try:
            handler = AnimationDataHandler(project_path)
            if not handler.anim_data:
                q.put(f"  -> Skipping {folder_name}: No valid animation data found in XML.")
                return 0, 1, False

            project_anims_saved = 0
            for index, anim in enumerate(handler.anim_data):
                if self.cancel_operation:
                    return project_anims_saved, 0, True
                
                json_data = handler.generate_animation_data(index)
                if json_data:
                    _, error = handler.export_optimized_animation(json_data)
                    if error:
                        q.put(f"  -> Failed to export {anim['name']} for {folder_name}: {error}")
                    else:
                        project_anims_saved += 1
            
            if project_anims_saved == 0 and not self.cancel_operation:
                 return 0, 1, False
            
            return project_anims_saved, 0, False

        except Exception as e:
            q.put(f"  -> Critical error processing project '{folder_name}': {e}")
            return 0, 1, False

    def _animation_generation_worker(self, q):
        total_anims_saved, projects_failed = 0, 0
        
        tasks = [(os.path.join(self.parent_folder, fn), fn) for fn in self.project_folders]

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {executor.submit(self._process_project_for_anim_gen, path, name, q): name for path, name in tasks}
            
            for future in concurrent.futures.as_completed(futures):
                if self.cancel_operation:
                    break 

                try:
                    saved, failed, skipped = future.result()
                    if not skipped:
                        total_anims_saved += saved
                        projects_failed += failed
                except Exception as exc:
                    folder_name = futures[future]
                    q.put(f"  -> Exception for '{folder_name}': {exc}")
                    projects_failed += 1

        if self.cancel_operation:
            q.put("DONE:CANCEL")
        else:
            q.put(f"DONE:{total_anims_saved}:{projects_failed}")

    def _process_project_for_export(self, char_folder, common_animations, output_dir, q):
        if self.cancel_operation: return

        char_name = char_folder.name
        source_anim_path = char_folder / "AnimationData"
        q.put(f"\n--- Processing: {char_name} ---")
        output_char_dir = output_dir / char_name
        output_char_dir.mkdir()
        
        for json_name in sorted(list(common_animations)):
            if self.cancel_operation: return
            
            shutil.copy2(source_anim_path / json_name, output_char_dir / json_name)
            
            anim_name = json_name.removesuffix("-AnimData.json")
            source_sprites_path = source_anim_path / anim_name
            if source_sprites_path.is_dir():
                shutil.copytree(source_sprites_path, output_char_dir / anim_name)
                q.put(f"  ✅ Copied assets for '{anim_name}' from '{char_name}'")
            else:
                q.put(f"  - Warning: Sprite folder for '{anim_name}' not found in '{char_name}'.")

    def _export_assets_worker(self, q):
        main_path = pathlib.Path(self.parent_folder)
        q.put(f"Analyzing folder structure in: {main_path}\n")
        character_folders = [d for d in main_path.iterdir() if d.is_dir() and not d.name.startswith(('.', 'output'))]
        if not character_folders:
            q.put("Error: No character subfolders found in the specified directory.")
            q.put("DONE:ERROR"); return

        animations_by_character = {}
        for char_folder in character_folders:
            if self.cancel_operation: q.put("DONE:CANCEL"); return
            anim_data_path = char_folder / "AnimationData"
            if anim_data_path.is_dir():
                animations_by_character[char_folder.name] = {f.name for f in anim_data_path.rglob('*.json')}
                q.put(f"-> Found '{char_folder.name}' with {len(animations_by_character[char_folder.name])} animations.")
        
        if not animations_by_character:
            q.put("\nNo characters with valid 'AnimationData' folders found."); q.put("DONE:ERROR"); return

        common_animations = set.intersection(*animations_by_character.values())
        if not common_animations:
            q.put("\nNo .json animation was found to be common to all characters."); q.put("DONE:COMPLETE"); return

        q.put("\n" + "-"*50 + "\n✅ Common animations found:")
        for file_name in sorted(list(common_animations)): q.put(f"   - {file_name}")
        q.put("-" * 50 + "\n\nStarting export process...")

        output_dir = main_path / "output"
        if output_dir.exists():
            q.put(f"Deleting existing 'output' folder..."); shutil.rmtree(output_dir)
        output_dir.mkdir()

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(self._process_project_for_export, cf, common_animations, output_dir, q) for cf in character_folders]
            for future in concurrent.futures.as_completed(futures):
                if self.cancel_operation: break
                try: future.result()
                except Exception as e: q.put(f"  -> An error occurred during export: {e}")

        if self.cancel_operation:
            q.put("DONE:CANCEL")
        else:
            q.put("\n" + "-"*50 + f"\n✅ Process completed. Files are in: {output_dir}\n" + "-"*50)
            q.put("DONE:COMPLETE")

    def _process_project_for_x2_export(self, char_folder, dest_dir, q):
        if self.cancel_operation: return
            
        char_name = char_folder.name
        q.put(f"\n--- Processing: {char_name} ---")
        dest_char_dir = dest_dir / char_name
        dest_char_dir.mkdir()

        for json_file in char_folder.glob("*.json"):
            if self.cancel_operation: return
            
            q.put(f"  -> Processing {json_file.name} for {char_name}")
            with open(json_file, 'r') as f: data = json.load(f)
            for group in data.get('sprites', {}).values():
                group['framewidth'] *= 2; group['frameheight'] *= 2
                if group.get('sprite_anchor_offset'):
                    group['sprite_anchor_offset'] = [v * 2 for v in group['sprite_anchor_offset']]
                for frame in group.get('frames', []):
                    if frame.get('render_offset'):
                        frame['render_offset'] = [v * 2 for v in frame['render_offset']]
            with open(dest_char_dir / json_file.name, 'w') as f: json.dump(data, f, indent=4)
            
            anim_name = json_file.name.removesuffix("-AnimData.json")
            source_sprites_dir, dest_sprites_dir = char_folder / anim_name, dest_char_dir / anim_name
            if source_sprites_dir.is_dir():
                dest_sprites_dir.mkdir()
                for sprite_file in source_sprites_dir.glob("*.png"):
                    if self.cancel_operation: return
                    with Image.open(sprite_file) as img:
                        img.resize((img.width * 2, img.height * 2), Image.NEAREST).save(dest_sprites_dir / sprite_file.name)

    def _export_assets_x2_worker(self, q):
        main_path = pathlib.Path(self.parent_folder)
        source_dir, dest_dir = main_path / "output", main_path / "output x2"
        if not source_dir.is_dir():
            q.put(f"❌ ERROR: Source folder '{source_dir}' does not exist. Run 'Export Final Assets' first."); q.put("DONE:ERROR"); return

        q.put(f"Starting x2 export from '{source_dir}' to '{dest_dir}'...")
        if dest_dir.exists():
            q.put(f"Deleting existing '{dest_dir}'..."); shutil.rmtree(dest_dir)
        dest_dir.mkdir()

        character_folders = [d for d in source_dir.iterdir() if d.is_dir()]

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(self._process_project_for_x2_export, cf, dest_dir, q) for cf in character_folders]
            for future in concurrent.futures.as_completed(futures):
                if self.cancel_operation: break
                try: future.result()
                except Exception as e: q.put(f"  -> An error occurred during x2 export: {e}")
        
        if self.cancel_operation:
            q.put("DONE:CANCEL")
        else:
            q.put("\n" + "-"*50 + f"\n✅ x2 Export completed. Files are in: {dest_dir}\n" + "-"*50)
            q.put("DONE:COMPLETE")

    def _shadow_generation_worker(self, q):
        main_path = pathlib.Path(self.parent_folder)
        output_dirs = {"1x": main_path / "output", "2x": main_path / "output x2"}
        q.put("--- Starting Shadow Sprite Generation ---")
        
        for scale, output_dir in output_dirs.items():
            if not output_dir.is_dir():
                q.put(f"\n- INFO: Folder '{output_dir.name}' not found. Skipping {scale} shadow generation.")
                continue
            
            q.put(f"\nProcessing {scale} shadows for '{output_dir.name}'...")
            copied, skipped = 0, 0
            for char_folder in [d for d in output_dir.iterdir() if d.is_dir()]:
                if self.cancel_operation: q.put("DONE:CANCEL"); return
                
                source_shadow_path = main_path / char_folder.name / "Sprites" / "sprite_shadow.png"
                if not source_shadow_path.exists():
                    source_shadow_path = main_path / char_folder.name / "Animations" / "sprite_shadow.png"
                if not source_shadow_path.exists():
                    source_shadow_path = main_path / char_folder.name / "sprite_shadow.png"
                
                if source_shadow_path.exists():
                    try:
                        with Image.open(source_shadow_path) as img:
                            if scale == "2x":
                                img = img.resize((img.width * 2, img.height * 2), Image.NEAREST)
                            img.save(char_folder / "sprite_shadow.png")
                        q.put(f"  ✅ Created {scale} shadow for '{char_folder.name}'")
                        copied += 1
                    except Exception as e:
                        q.put(f"  ❌ Error for '{char_folder.name}': {e}"); skipped += 1
                else:
                    q.put(f"  - WARNING: No 'sprite_shadow.png' found for '{char_folder.name}'."); skipped += 1
        
        q.put("\n" + "-"*50 + "\n✅ Shadow generation completed.\n" + "-"*50)
        q.put("DONE:COMPLETE")

    # --- Unique/Interactive Task Handlers ---

    def show_asset_generation_view(self):
        if self.update_breadcrumbs:
            path = self.base_path + [("Batch Tasks", self.show_task_selection_view), ("Generate Assets", self.show_asset_generation_view)]
            self.update_breadcrumbs(path)
        self.clear_frame()
        top_frame = Frame(self.main_frame); top_frame.pack(fill='x', padx=10, pady=5)
        Button(top_frame, text="Back to Tasks", command=self.show_task_selection_view).pack(side='left')
        Label(self.main_frame, text="Asset Generation Workflow", font=('Arial', 14)).pack(pady=10)
        
        button_frame = Frame(self.main_frame); button_frame.pack(pady=10)
        Button(button_frame, text="1. Create Folders from names.txt", command=self._create_folders_from_file, width=35).pack(pady=5)
        Button(button_frame, text="2. Uncompress ZIPs", command=self._uncompress_zips, width=35).pack(pady=5)
        Button(button_frame, text="3. Cleanup ZIP files", command=self._cleanup_zip_files, width=35).pack(pady=5)
        Button(button_frame, text="4. Show Asset Download Link", command=self._show_download_link, width=35).pack(pady=5)

        log_frame = Frame(self.main_frame); log_frame.pack(fill='both', expand=True, padx=10, pady=10)
        self.log_text = Text(log_frame, height=15, wrap='word', state='disabled'); self.log_text.pack(side='left', fill='both', expand=True)
        log_scroll = Scrollbar(log_frame, command=self.log_text.yview); log_scroll.pack(side='right', fill='y')
        self.log_text.config(yscrollcommand=log_scroll.set)

    def _create_folders_from_file(self):
        self._clear_log(); self._log("--- 1. Creating Folders from 'names.txt' ---")
        names_file = pathlib.Path(self.parent_folder) / "names.txt"
        if not names_file.exists():
            self._log(f"!! ERROR: File not found: '{names_file}'."); return
        created, skipped = 0, 0
        with open(names_file, 'r') as f:
            for line in f:
                folder_name = line.strip()
                if folder_name:
                    folder_path = pathlib.Path(self.parent_folder) / folder_name
                    if not folder_path.exists():
                        folder_path.mkdir(); self._log(f"-> Created: '{folder_name}'"); created += 1
                    else:
                        self._log(f"-> Exists, skipping: '{folder_name}'"); skipped += 1
        self._log(f"\nFinished. Created: {created}, Skipped: {skipped}")

    def _uncompress_zips(self):
        self._clear_log(); self._log("--- 2. Uncompressing ZIPs ---")
        success, skipped = 0, 0
        for folder in [p for p in pathlib.Path(self.parent_folder).iterdir() if p.is_dir()]:
            try:
                zip_file = next(folder.glob('*.zip'))
                dest_path = folder / "Animations"; dest_path.mkdir(exist_ok=True)
                with zipfile.ZipFile(zip_file, 'r') as z: z.extractall(dest_path)
                self._log(f"-> Uncompressed ZIP in '{folder.name}'"); success += 1
            except StopIteration:
                self._log(f"-> No ZIP found in '{folder.name}', skipping."); skipped += 1
            except Exception as e:
                self._log(f"-> ERROR in '{folder.name}': {e}")
        self._log(f"\nFinished. Success: {success}, Skipped: {skipped}")

    def _cleanup_zip_files(self):
        self._clear_log(); self._log("--- 3. Cleaning up ZIP files ---")
        zips = list(pathlib.Path(self.parent_folder).rglob('*.zip'))
        if not zips: self._log("No .zip files found to clean up."); return
        if messagebox.askyesno("Confirm Deletion", f"Found {len(zips)} .zip files. Delete them all?"):
            for z in zips: z.unlink(); self._log(f"-> Deleted: {z.name}")
            self._log("\nCleanup complete.")
        else: self._log("\nOperation cancelled.")

    def _show_download_link(self):
        url = "https://sprites.pmdcollab.org/"
        popup = Toplevel(self.parent_frame); popup.title("Asset Download Link")
        Label(popup, text="Asset download source:", padx=20, pady=10).pack()
        Entry(popup, width=50, textvariable=StringVar(value=url), state='readonly').pack(padx=20, pady=5)
        Button(popup, text="Close", command=popup.destroy).pack(pady=10)
        popup.transient(self.parent_frame); popup.grab_set()

    def start_sprite_generation(self):
        if self.update_breadcrumbs:
            path = self.base_path + [("Batch Tasks", self.show_task_selection_view), ("Generate Sprites", self.start_sprite_generation)]
            self.update_breadcrumbs(path)
        self.current_folder_index = 0
        self.show_sprite_generation_view()

    def show_sprite_generation_view(self):
        self.clear_frame()
        if self.current_folder_index >= len(self.project_folders):
            messagebox.showinfo("Complete", "All project folders have been processed."); self.show_task_selection_view(); return

        folder_name = self.project_folders[self.current_folder_index]
        self.current_project_path = os.path.join(self.parent_folder, folder_name)
        try:
            self.current_spritesheet_path = os.path.join(self.current_project_path, [f for f in os.listdir(self.current_project_path) if f.lower().endswith('.png')][0])
        except (FileNotFoundError, IndexError):
            messagebox.showerror("Error", f"No spritesheet found in '{folder_name}'. Skipping."); self.process_next_folder(); return

        top_frame = Frame(self.main_frame); top_frame.pack(fill='x', padx=10, pady=5)
        Button(top_frame, text="Back to Tasks", command=self.show_task_selection_view).pack(side='left')
        Button(top_frame, text="Skip Folder", command=self.process_next_folder).pack(side='left', padx=5)
        
        progress = f"Processing {self.current_folder_index + 1}/{len(self.project_folders)}: {folder_name}"
        Label(self.main_frame, text=progress, font=('Arial', 10, 'bold')).pack(pady=5)
        img = Image.open(self.current_spritesheet_path); img.thumbnail((500, 400)); self.img_tk = ImageTk.PhotoImage(img)
        Label(self.main_frame, image=self.img_tk).pack(pady=10)

        form = Frame(self.main_frame); form.pack(pady=10)
        Label(form, text="Size (width/height):").grid(row=0, column=0, padx=5)
        self.size_entry = Entry(form, width=10); self.size_entry.grid(row=0, column=1, padx=5)
        self.size_entry.focus_set(); self.size_entry.bind("<Return>", self.process_current_folder_sprites)
        Button(form, text="Process and Next", command=self.process_current_folder_sprites).grid(row=1, columnspan=2, pady=10)

    def process_current_folder_sprites(self, event=None):
        try:
            size = int(self.size_entry.get())
            output_folder = os.path.join(self.current_project_path, "Sprites")
            os.makedirs(output_folder, exist_ok=True)
            for file in os.listdir(output_folder): os.unlink(os.path.join(output_folder, file))
            handler = SpriteSheetHandler(self.current_spritesheet_path, remove_first_row=True)
            sprites, _, _ = handler.split_sprites(size, size)
            for idx, sprite in enumerate(sprites):
                if bbox := sprite.getbbox(): sprite = sprite.crop(bbox)
                sprite.save(os.path.join(output_folder, f"sprite_{idx + 1}.png"))
        except Exception as e:
            messagebox.showerror("Processing Error", f"An error occurred: {e}")
        self.process_next_folder()

    def process_next_folder(self):
        self.current_folder_index += 1
        self.show_sprite_generation_view()

    def show_optimized_animation_previewer(self):
        self.clear_frame()
        if self.update_breadcrumbs:
            path = self.base_path + [("Batch Tasks", self.show_task_selection_view), ("Preview Animations", self.show_optimized_animation_previewer)]
            self.update_breadcrumbs(path)
        
        top_frame = Frame(self.main_frame); top_frame.pack(fill='x', padx=10, pady=5)
        Button(top_frame, text="Back to Tasks", command=self.show_task_selection_view).pack(side='left')
        
        output_folder = next((p for p in [os.path.join(self.parent_folder, "output x2"), os.path.join(self.parent_folder, "output")] if os.path.exists(p)), None)
        if not output_folder:
            messagebox.showerror("Error", "'output' or 'output x2' folder not found."); return

        characters = sorted([d for d in os.listdir(output_folder) if os.path.isdir(os.path.join(output_folder, d))])
        if not characters:
            Label(self.main_frame, text="No characters found in output folder.", fg="red").pack(pady=50); return

        Label(top_frame, text="Character:").pack(side='left', padx=(20, 5))
        self.selected_char_var = StringVar(value=characters[0])
        OptionMenu(top_frame, self.selected_char_var, *characters, command=self._on_character_selected_for_preview).pack(side='left')
        
        self.preview_content_frame = Frame(self.main_frame)
        self.preview_content_frame.pack(fill='both', expand=True)
        self._on_character_selected_for_preview(characters[0])

    def _on_character_selected_for_preview(self, char_name):
        if self.animation_creator: self.animation_creator.clear_frame()
        for widget in self.preview_content_frame.winfo_children(): widget.destroy()

        output_folder = next(p for p in [os.path.join(self.parent_folder, "output x2"), os.path.join(self.parent_folder, "output")] if os.path.exists(p))
        character_path = os.path.join(output_folder, char_name)

        self.animation_creator = AnimationCreator(
            parent_frame=self.preview_content_frame,
            folder=character_path,
            return_to_main_callback=self.show_task_selection_view,
            update_breadcrumbs_callback=self.update_breadcrumbs,
            base_path=self.base_path + [("Batch Tasks", self.show_task_selection_view), ("Preview Animations", self.show_optimized_animation_previewer)],
            start_in_preview_mode=True,
            anim_data_subfolder=None,
            show_navigation=False
        )