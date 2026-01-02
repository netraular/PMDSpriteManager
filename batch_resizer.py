# batch_resizer.py

import os
import pathlib
import zipfile
import shutil
import json
import threading
import queue
import concurrent.futures
import urllib.request
import re
from tkinter import Frame, Label, Button, Entry, messagebox, filedialog, Canvas, Scrollbar, Text, END, Toplevel, StringVar, OptionMenu
from PIL import Image, ImageTk
from animation_data_handler import AnimationDataHandler
from animation_creator import AnimationCreator
from sprite_sheet_handler import SpriteSheetHandler
from ui_components.esp32_asset_exporter import ESP32AssetExporter
from rpg_tile_previewer import RPGTilePreviewer

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
        self.rpg_previewer = None
        self.sprite_previews = [] # To hold image references
        
        # Cache for tracker data (to avoid fetching multiple times)
        self._tracker_cache = None

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
        if self.rpg_previewer:
            self.rpg_previewer.clear_frame()
            self.rpg_previewer = None
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
        
        Button(content_frame, text="0- Prepare Pokemon Data (Portraits)", command=self.show_prepare_data_view, font=('Arial', 12), width=40, bg="lightcyan").pack(pady=10)
        Button(content_frame, text="1- Download Sprites from PMDCollab", command=self.show_download_sprites_visual_view, font=('Arial', 12), width=40, bg="lightyellow").pack(pady=10)
        Button(content_frame, text="2- Generate Sprites", command=self.show_sprite_generation_menu, font=('Arial', 12), width=40).pack(pady=10)
        Button(content_frame, text="3- Generate Optimized Animations", command=self.start_animation_generation, font=('Arial', 12), width=40).pack(pady=10)
        Button(content_frame, text="Export Final Assets", command=self.show_export_assets_view, font=('Arial', 12), width=40, bg="lightgreen").pack(pady=10)
        Button(content_frame, text="Export Final Assets (x2)", command=self.show_export_assets_x2_view, font=('Arial', 12), width=40, bg="lightblue").pack(pady=10)
        Button(content_frame, text="Generate Shadow Sprites", command=self.show_shadow_generation_view, font=('Arial', 12), width=40).pack(pady=10)
        Button(content_frame, text="Preview Optimized Animations", command=self.show_optimized_animation_previewer, font=('Arial', 12), width=40).pack(pady=10)
        Button(content_frame, text="RPG Tile Preview (32x32)", command=self.show_rpg_tile_previewer, font=('Arial', 12), width=40, bg="lightcoral").pack(pady=10)
        Button(content_frame, text="ESP32 Export", command=self.show_esp32_export_view, font=('Arial', 12), width=40).pack(pady=10)

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

    def show_esp32_export_view(self):
        description = "Finds the most frequent animations across all characters and exports them to a new 'esp32_output' folder.\nIt copies the required JSON and sprite files from the 'output x2' directory."
        self._setup_task_view(
            title="ESP32 Export",
            description=description,
            start_button_text="Start ESP32 Export",
            worker_function=self._esp32_export_worker
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
            # Check if Animations folder and AnimData.xml exist
            animations_folder = os.path.join(project_path, "Animations")
            animdata_path = os.path.join(animations_folder, "AnimData.xml")
            
            if not os.path.exists(animations_folder):
                q.put(f"  -> Skipping {folder_name}: No Animations folder found.")
                return 0, 1, False
            
            if not os.path.exists(animdata_path):
                q.put(f"  -> Skipping {folder_name}: AnimData.xml not found in Animations folder.")
                return 0, 1, False
            
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
        
        # Filter only valid Pokemon folders (format: "XXXX Name") 
        valid_folders = [fn for fn in self.project_folders if self._is_valid_pokemon_folder(fn)]
        
        # Only process folders that have Sprites folder (step 2 completed) and don't have AnimationData yet
        folders_to_process = []
        skipped_no_sprites = 0
        skipped_has_animdata = 0
        
        for fn in valid_folders:
            folder_path = os.path.join(self.parent_folder, fn)
            sprites_folder = os.path.join(folder_path, "Sprites")
            animdata_folder = os.path.join(folder_path, "AnimationData")
            
            if not os.path.exists(sprites_folder):
                skipped_no_sprites += 1
                continue
            
            if os.path.exists(animdata_folder):
                skipped_has_animdata += 1
                continue
                
            folders_to_process.append(fn)
        
        q.put(f"Found {len(folders_to_process)} folders to process (out of {len(valid_folders)} valid folders)")
        q.put(f"Skipping {skipped_no_sprites} folders without Sprites folder (step 2 not completed)")
        q.put(f"Skipping {skipped_has_animdata} folders that already have AnimationData\n")
        
        if not folders_to_process:
            q.put("No folders need processing.")
            q.put("DONE:0:0")
            return
        
        tasks = [(os.path.join(self.parent_folder, fn), fn) for fn in folders_to_process]

        # Use more workers for better parallelization (default is CPU count, we use CPU count * 2)
        max_workers = min(32, (os.cpu_count() or 4) * 2)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
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
                group['framewidth'] *= 2
                group['frameheight'] *= 2
                if group.get('bounding_box_anchor'):
                    group['bounding_box_anchor'] = [v * 2 for v in group['bounding_box_anchor']]
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
        
    def _esp32_export_worker(self, q):
        try:
            exporter = ESP32AssetExporter(self.parent_folder)
            
            def log_to_queue(message):
                if self.cancel_operation:
                    raise InterruptedError("Operation cancelled by user.")
                q.put(message)
            
            success = exporter.export(log_callback=log_to_queue)
            
            if self.cancel_operation:
                q.put("DONE:CANCEL")
            elif success:
                q.put("DONE:COMPLETE")
            else:
                q.put("DONE:ERROR")
        
        except InterruptedError:
            q.put("\nOperation was cancelled during execution.")
            q.put("DONE:CANCEL")
        except Exception as e:
            q.put(f"\n❌ A critical error occurred during ESP32 export: {e}")
            q.put("DONE:ERROR")

    # --- Unique/Interactive Task Handlers ---

    def _is_valid_pokemon_folder(self, folder_name):
        """Checks if folder name matches the format 'XXXX Name' (4 digits + space + name)."""
        if len(folder_name) < 6:  # Minimum: "0000 X"
            return False
        # Check if first 4 characters are digits and 5th is a space
        return folder_name[:4].isdigit() and folder_name[4] == ' ' and len(folder_name) > 5

    def show_sprite_generation_menu(self):
        """Shows the sprite generation menu with options to process all or select specific folder."""
        if self.update_breadcrumbs:
            path = self.base_path + [("Batch Tasks", self.show_task_selection_view), ("2- Generate Sprites", self.show_sprite_generation_menu)]
            self.update_breadcrumbs(path)
        
        self.clear_frame()
        
        top_frame = Frame(self.main_frame); top_frame.pack(fill='x', padx=10, pady=5)
        Button(top_frame, text="Back to Tasks", command=self.show_task_selection_view).pack(side='left')
        
        content_frame = Frame(self.main_frame); content_frame.pack(pady=30)
        Label(content_frame, text="Generate Sprites", font=('Arial', 14, 'bold')).pack(pady=10)
        
        # Filter valid folders (format: "XXXX Name") and those without Sprites subfolder
        self.valid_project_folders = [f for f in self.project_folders if self._is_valid_pokemon_folder(f)]
        self.folders_without_sprites = [
            f for f in self.valid_project_folders 
            if not os.path.exists(os.path.join(self.parent_folder, f, "Sprites"))
        ]
        
        info_text = f"Found {len(self.folders_without_sprites)} valid folders without Sprites subfolder (out of {len(self.valid_project_folders)} valid folders)"
        Label(content_frame, text=info_text, font=('Arial', 10)).pack(pady=10)
        
        Button(content_frame, text="⚡ Auto Process All (detect sprite size from XML)", 
               command=self.start_auto_sprite_generation, font=('Arial', 12), width=45, bg="lightyellow").pack(pady=10)
        
        Button(content_frame, text="Manual Process All (enter size for each)", 
               command=self.start_sprite_generation_sequential, font=('Arial', 12), width=45, bg="lightgreen").pack(pady=10)
        
        Label(content_frame, text="— OR —", font=('Arial', 10)).pack(pady=10)
        
        Label(content_frame, text="Select a specific folder to process:", font=('Arial', 10)).pack(pady=5)
        
        # Create dropdown for folder selection (only valid folders)
        self.selected_folder_var = StringVar()
        if self.valid_project_folders:
            self.selected_folder_var.set(self.valid_project_folders[0])
        
        dropdown_frame = Frame(content_frame); dropdown_frame.pack(pady=5)
        if self.valid_project_folders:
            folder_menu = OptionMenu(dropdown_frame, self.selected_folder_var, *self.valid_project_folders)
            folder_menu.config(width=30)
            folder_menu.pack(side='left', padx=5)
            
            Button(dropdown_frame, text="Process Selected", command=self.start_sprite_generation_selected, 
                   font=('Arial', 11)).pack(side='left', padx=5)
        else:
            Label(dropdown_frame, text="No valid folders found (format: 'XXXX Name')", fg="red").pack()

    def start_auto_sprite_generation(self):
        """Starts automatic sprite generation by detecting sprite boundaries in the image."""
        self.clear_frame()
        
        top_frame = Frame(self.main_frame)
        top_frame.pack(fill='x', padx=10, pady=5)
        Button(top_frame, text="Back to Menu", command=self.show_sprite_generation_menu).pack(side='left')
        
        content_frame = Frame(self.main_frame)
        content_frame.pack(pady=10, padx=20, fill='both', expand=True)
        
        Label(content_frame, text="Auto Generate Sprites", font=('Arial', 14, 'bold')).pack(pady=(0, 10))
        Label(content_frame, text="Automatically detecting sprite boundaries by analyzing pixel groups in the image", 
              font=('Arial', 10)).pack(pady=(0, 10))
        
        # Log area
        log_frame = Frame(content_frame)
        log_frame.pack(pady=10, fill='both', expand=True)
        
        self.auto_log_text = Text(log_frame, height=20, width=90, font=('Courier', 9))
        scrollbar = Scrollbar(log_frame, command=self.auto_log_text.yview)
        self.auto_log_text.configure(yscrollcommand=scrollbar.set)
        self.auto_log_text.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        def log_auto(msg):
            self.auto_log_text.insert(END, msg + "\n")
            self.auto_log_text.see(END)
        
        def auto_process_thread():
            folders_to_process = self.folders_without_sprites.copy()
            
            log_auto(f"Starting auto sprite generation for {len(folders_to_process)} folders...\n")
            
            success_count = 0
            fail_count = 0
            
            for i, folder_name in enumerate(folders_to_process):
                self.main_frame.after(0, lambda fn=folder_name, idx=i+1, total=len(folders_to_process): 
                    log_auto(f"[{idx}/{total}] Processing: {fn}"))
                
                project_path = os.path.join(self.parent_folder, folder_name)
                
                try:
                    # Get Pokemon ID from folder name
                    pokemon_id = folder_name.split(' ', 1)[0]
                    sprite_recolor_name = f"sprite_recolor-{pokemon_id}-0000-0001.png"
                    spritesheet_path = os.path.join(project_path, sprite_recolor_name)
                    
                    if not os.path.exists(spritesheet_path):
                        # Try any PNG as fallback
                        png_files = [f for f in os.listdir(project_path) if f.lower().endswith('.png') and 'portrait' not in f.lower()]
                        if png_files:
                            spritesheet_path = os.path.join(project_path, png_files[0])
                        else:
                            self.main_frame.after(0, lambda fn=folder_name: 
                                log_auto(f"  ❌ No spritesheet found for {fn}"))
                            fail_count += 1
                            continue
                    
                    # First try to detect from image analysis (more accurate for sprite_recolor images)
                    sprites_per_row_img = self._detect_sprites_per_row_from_image(spritesheet_path)
                    sprites_per_row_xml = self._get_sprites_per_row_from_xml(project_path, spritesheet_path)
                    
                    # Log detection results
                    self.main_frame.after(0, lambda fn=folder_name, xml=sprites_per_row_xml, img=sprites_per_row_img: 
                        log_auto(f"  🔍 {fn}: Image={img}, XML={xml}"))
                    
                    # Prefer image detection since sprite_recolor has different scale than AnimData.xml
                    sprites_per_row = sprites_per_row_img if sprites_per_row_img else sprites_per_row_xml
                    
                    if sprites_per_row is None or sprites_per_row < 1:
                        self.main_frame.after(0, lambda fn=folder_name: 
                            log_auto(f"  ❌ Could not determine sprite count for {fn}"))
                        fail_count += 1
                        continue
                    
                    # Process sprites
                    output_folder = os.path.join(project_path, "Sprites")
                    os.makedirs(output_folder, exist_ok=True)
                    
                    # Clear existing sprites
                    for file in os.listdir(output_folder):
                        os.unlink(os.path.join(output_folder, file))
                    
                    handler = SpriteSheetHandler(spritesheet_path, remove_first_row=True)
                    # Pass number of sprites per row (assuming square grid)
                    sprites, _, _ = handler.split_sprites(sprites_per_row, sprites_per_row)
                    
                    saved_count = 0
                    for idx, sprite in enumerate(sprites):
                        if bbox := sprite.getbbox():
                            sprite = sprite.crop(bbox)
                        sprite.save(os.path.join(output_folder, f"sprite_{idx + 1}.png"))
                        saved_count += 1
                    
                    # Calculate cell size for display
                    with Image.open(spritesheet_path) as img:
                        cell_size = img.width // sprites_per_row
                    
                    self.main_frame.after(0, lambda fn=folder_name, size=cell_size, cnt=saved_count, spr=sprites_per_row: 
                        log_auto(f"  ✅ {fn} (grid: {spr}x{spr}, cell: {size}x{size}, {cnt} sprites)"))
                    success_count += 1
                    
                except Exception as e:
                    self.main_frame.after(0, lambda fn=folder_name, err=str(e): 
                        log_auto(f"  ❌ Error processing {fn}: {err}"))
                    fail_count += 1
            
            self.main_frame.after(0, lambda s=success_count, f=fail_count: 
                log_auto(f"\n{'='*50}\n✅ Complete! Success: {s}, Failed: {f}"))
        
        # Start processing in background thread
        thread = threading.Thread(target=auto_process_thread, daemon=True)
        thread.start()

    def _detect_sprites_per_row_from_image(self, image_path):
        """
        Detects number of sprites per row by analyzing multiple horizontal slices of the image.
        Counts transparent/gap columns to find sprite boundaries.
        """
        try:
            with Image.open(image_path) as img:
                img = img.convert('RGBA')
                width, height = img.size
                
                # We'll analyze several horizontal slices and find gaps (transparent columns)
                # Skip the first row (palette) and sample multiple bands
                
                # A "gap" is a column that is mostly transparent across all sampled rows
                gap_columns = []
                
                # Sample from row 1 to end (skip row 0 which is palette)
                sample_rows = list(range(1, height))
                
                # For each column, count how many sampled rows have transparent pixels
                for x in range(width):
                    transparent_count = 0
                    for y in sample_rows:
                        pixel = img.getpixel((x, y))
                        if len(pixel) >= 4 and pixel[3] < 10:  # Transparent
                            transparent_count += 1
                    
                    # If more than 80% of the column is transparent, it's a gap
                    if transparent_count > len(sample_rows) * 0.8:
                        gap_columns.append(x)
                
                # Find continuous gap regions and sprite regions
                # A sprite region is between gap regions
                if not gap_columns:
                    # No gaps found, maybe entire image is one sprite
                    return 1
                
                # Find the start of each gap sequence
                gap_regions = []
                gap_start = gap_columns[0]
                prev_x = gap_columns[0]
                
                for x in gap_columns[1:]:
                    if x != prev_x + 1:
                        # End of gap sequence
                        gap_regions.append((gap_start, prev_x + 1))
                        gap_start = x
                    prev_x = x
                gap_regions.append((gap_start, prev_x + 1))
                
                # Calculate gaps between sprite regions
                # Sprite regions are between gap regions
                sprite_widths = []
                
                # If first gap starts after 0, there's a sprite at the beginning
                if gap_regions[0][0] > 0:
                    sprite_widths.append(gap_regions[0][0])
                
                # Sprites between gaps
                for i in range(len(gap_regions) - 1):
                    current_gap_end = gap_regions[i][1]
                    next_gap_start = gap_regions[i + 1][0]
                    sprite_width = next_gap_start - current_gap_end
                    if sprite_width > 0:
                        sprite_widths.append(sprite_width)
                
                # If last gap ends before width, there's a sprite at the end
                if gap_regions[-1][1] < width:
                    sprite_widths.append(width - gap_regions[-1][1])
                
                # Number of sprites is the number of sprite regions
                sprites_per_row = len(sprite_widths)
                
                if sprites_per_row < 1:
                    return None
                
                # Validate: check if this creates reasonable sprite cells
                # Cell size should be roughly image_width / sprites_per_row
                cell_size = width / sprites_per_row
                
                # If cell sizes are too inconsistent, try alternative detection
                if sprite_widths and sprites_per_row > 0:
                    avg_width = sum(sprite_widths) / len(sprite_widths)
                    # Check if most sprites have similar width (within 50% of average)
                    consistent = all(abs(w - avg_width) / avg_width < 0.5 for w in sprite_widths if avg_width > 0)
                    
                    if not consistent:
                        # Try simpler approach: divide by common grid numbers
                        for grid_size in [2, 3, 4, 5, 6, 7, 8]:
                            if width % grid_size == 0 and height % grid_size == 0:
                                return grid_size
                
                return sprites_per_row
                
        except Exception as e:
            print(f"Error detecting sprite count: {e}")
            return None

    def _get_sprites_per_row_from_xml(self, project_path, spritesheet_path):
        """
        Gets number of sprites per row by calculating from Walk frame size and image dimensions.
        """
        frame_size = self._get_walk_frame_size(project_path)
        if frame_size is None:
            return None
        
        try:
            with Image.open(spritesheet_path) as img:
                width = img.width
                sprites_per_row = width // frame_size
                if sprites_per_row > 0:
                    return sprites_per_row
        except:
            pass
        
        return None

    def _get_walk_frame_size(self, project_path):
        """Gets the Walk animation frame size from AnimData.xml."""
        import xml.etree.ElementTree as ET
        
        animations_folder = os.path.join(project_path, "Animations")
        animdata_path = os.path.join(animations_folder, "AnimData.xml")
        
        if not os.path.exists(animdata_path):
            return None
        
        try:
            tree = ET.parse(animdata_path)
            root = tree.getroot()
            anims_root = root.find("Anims")
            
            if anims_root is None:
                return None
            
            # Look for Walk animation
            for anim in anims_root.findall("Anim"):
                name_elem = anim.find("Name")
                if name_elem is not None and name_elem.text == "Walk":
                    fw_elem = anim.find("FrameWidth")
                    fh_elem = anim.find("FrameHeight")
                    
                    if fw_elem is not None and fh_elem is not None:
                        fw = int(fw_elem.text)
                        fh = int(fh_elem.text)
                        # Return the larger dimension (usually they're equal)
                        return max(fw, fh)
                    
                    # If Walk is a CopyOf another animation, find the source
                    copy_of = anim.find("CopyOf")
                    if copy_of is not None:
                        return self._get_anim_size_by_name(anims_root, copy_of.text)
            
            return None
            
        except Exception as e:
            print(f"Error parsing AnimData.xml: {e}")
            return None

    def _get_anim_size_by_name(self, anims_root, anim_name, visited=None):
        """Recursively gets animation frame size by name, handling CopyOf references."""
        if visited is None:
            visited = set()
        
        if anim_name in visited:
            return None
        visited.add(anim_name)
        
        for anim in anims_root.findall("Anim"):
            name_elem = anim.find("Name")
            if name_elem is not None and name_elem.text == anim_name:
                fw_elem = anim.find("FrameWidth")
                fh_elem = anim.find("FrameHeight")
                
                if fw_elem is not None and fh_elem is not None:
                    return max(int(fw_elem.text), int(fh_elem.text))
                
                copy_of = anim.find("CopyOf")
                if copy_of is not None:
                    return self._get_anim_size_by_name(anims_root, copy_of.text, visited)
        
        return None

    def start_sprite_generation_sequential(self):
        """Starts processing folders sequentially, skipping those with Sprites subfolder."""
        if self.update_breadcrumbs:
            path = self.base_path + [("Batch Tasks", self.show_task_selection_view), ("2- Generate Sprites", self.show_sprite_generation_menu)]
            self.update_breadcrumbs(path)
        
        # Use only folders without Sprites subfolder
        self.sprite_gen_folders = self.folders_without_sprites.copy()
        self.current_folder_index = 0
        self.sprite_gen_mode = "sequential"
        self.show_sprite_generation_view()

    def start_sprite_generation_selected(self):
        """Starts processing a specific selected folder."""
        if self.update_breadcrumbs:
            path = self.base_path + [("Batch Tasks", self.show_task_selection_view), ("2- Generate Sprites", self.show_sprite_generation_menu)]
            self.update_breadcrumbs(path)
        
        selected = self.selected_folder_var.get()
        self.sprite_gen_folders = [selected]
        self.current_folder_index = 0
        self.sprite_gen_mode = "single"
        self.show_sprite_generation_view()

    def show_sprite_generation_view(self):
        self.clear_frame()
        
        # Check if we have folders to process
        if not hasattr(self, 'sprite_gen_folders') or not self.sprite_gen_folders:
            messagebox.showinfo("Complete", "No folders to process.")
            self.show_sprite_generation_menu()
            return
        
        if self.current_folder_index >= len(self.sprite_gen_folders):
            messagebox.showinfo("Complete", "All project folders have been processed.")
            self.show_sprite_generation_menu()
            return

        folder_name = self.sprite_gen_folders[self.current_folder_index]
        self.current_project_path = os.path.join(self.parent_folder, folder_name)
        
        # Extract Pokemon ID from folder name (format: "XXXX Name")
        folder_parts = folder_name.split(' ', 1)
        pokemon_id = folder_parts[0] if len(folder_parts) >= 1 else None
        
        # Look for the sprite_recolor PNG file first
        sprite_recolor_path = None
        if pokemon_id:
            sprite_recolor_name = f"sprite_recolor-{pokemon_id}-0000-0001.png"
            potential_path = os.path.join(self.current_project_path, sprite_recolor_name)
            if os.path.exists(potential_path):
                sprite_recolor_path = potential_path
        
        try:
            if sprite_recolor_path:
                self.current_spritesheet_path = sprite_recolor_path
            else:
                # Fallback to any PNG in the folder
                png_files = [f for f in os.listdir(self.current_project_path) if f.lower().endswith('.png')]
                if not png_files:
                    raise FileNotFoundError("No PNG files found")
                self.current_spritesheet_path = os.path.join(self.current_project_path, png_files[0])
        except (FileNotFoundError, IndexError):
            messagebox.showerror("Error", f"No spritesheet found in '{folder_name}'. Skipping.")
            self.process_next_folder()
            return

        top_frame = Frame(self.main_frame); top_frame.pack(fill='x', padx=10, pady=5)
        Button(top_frame, text="Back to Menu", command=self.show_sprite_generation_menu).pack(side='left')
        Button(top_frame, text="Skip Folder", command=self.process_next_folder).pack(side='left', padx=5)
        
        progress = f"Processing {self.current_folder_index + 1}/{len(self.sprite_gen_folders)}: {folder_name}"
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

    def show_rpg_tile_previewer(self):
        """Shows the RPG Tile Previewer for 32x32px tile-based RPG visualization."""
        self.clear_frame()
        if self.update_breadcrumbs:
            path = self.base_path + [("Batch Tasks", self.show_task_selection_view), ("RPG Tile Preview", self.show_rpg_tile_previewer)]
            self.update_breadcrumbs(path)
        
        self.rpg_previewer = RPGTilePreviewer(
            parent_frame=self.main_frame,
            parent_folder=self.parent_folder,
            return_to_main_callback=self.show_task_selection_view,
            update_breadcrumbs_callback=self.update_breadcrumbs,
            base_path=self.base_path + [("Batch Tasks", self.show_task_selection_view)]
        )

    def show_prepare_data_view(self):
        """Shows the view for preparing Pokemon data (download tracker, create folders, download portraits)."""
        self.clear_frame()
        if self.update_breadcrumbs:
            path = self.base_path + [("Batch Tasks", self.show_task_selection_view), ("Prepare Data", self.show_prepare_data_view)]
            self.update_breadcrumbs(path)
        
        top_frame = Frame(self.main_frame)
        top_frame.pack(fill='x', padx=10, pady=5)
        Button(top_frame, text="Back to Tasks", command=self.show_task_selection_view).pack(side='left')
        
        content_frame = Frame(self.main_frame)
        content_frame.pack(pady=20, padx=20, fill='both', expand=True)
        
        Label(content_frame, text="Prepare Pokemon Data", font=('Arial', 14, 'bold')).pack(pady=(0, 10))
        Label(content_frame, text="This will download tracker.json, create folders for all Pokemon,\nand download portrait images for visual browsing.", font=('Arial', 10)).pack(pady=(0, 10))
        
        # Options frame
        options_frame = Frame(content_frame)
        options_frame.pack(pady=10)
        
        Label(options_frame, text="ID Range (start - end):").pack(side='left', padx=(0, 5))
        self.prepare_start_id = Entry(options_frame, width=8, font=('Arial', 11))
        self.prepare_start_id.insert(0, "0000")
        self.prepare_start_id.pack(side='left', padx=5)
        Label(options_frame, text="-").pack(side='left')
        self.prepare_end_id = Entry(options_frame, width=8, font=('Arial', 11))
        self.prepare_end_id.insert(0, "0500")
        self.prepare_end_id.pack(side='left', padx=5)
        
        # Buttons frame
        button_frame = Frame(content_frame)
        button_frame.pack(pady=15)
        
        self.prepare_button = Button(button_frame, text="Start Preparation", command=self._start_prepare_data, 
                                      bg="lightcyan", font=('Arial', 12), width=20)
        self.prepare_button.pack(side='left', padx=10)
        
        self.cancel_prepare_button = Button(button_frame, text="Cancel", command=self._cancel_prepare_data,
                                            bg="lightcoral", font=('Arial', 12), width=15, state='disabled')
        self.cancel_prepare_button.pack(side='left', padx=10)
        
        # Progress
        self.prepare_progress_label = Label(content_frame, text="", font=('Arial', 10))
        self.prepare_progress_label.pack(pady=5)
        
        # Log area
        log_frame = Frame(content_frame)
        log_frame.pack(pady=10, fill='both', expand=True)
        
        Label(log_frame, text="Preparation Log:", font=('Arial', 10, 'bold')).pack(anchor='w')
        
        self.log_text = Text(log_frame, height=18, width=80, font=('Courier', 9))
        scrollbar = Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

    def _cancel_prepare_data(self):
        """Cancels the data preparation process."""
        self.cancel_operation = True
        self._log_download("Cancellation requested...")

    def _start_prepare_data(self):
        """Starts the data preparation process."""
        try:
            start_id = int(self.prepare_start_id.get().strip())
            end_id = int(self.prepare_end_id.get().strip())
        except ValueError:
            messagebox.showwarning("Warning", "Please enter valid numeric IDs.")
            return
        
        if start_id > end_id:
            messagebox.showwarning("Warning", "Start ID must be less than or equal to End ID.")
            return
        
        self.prepare_button.config(state='disabled', text='Preparing...')
        self.cancel_prepare_button.config(state='normal')
        self.cancel_operation = False
        
        def prepare_thread():
            try:
                # Step 1: Download and cache tracker.json
                self._log_safe("Step 1: Downloading tracker.json from GitHub...")
                tracker_url = "https://raw.githubusercontent.com/PMDCollab/SpriteCollab/master/tracker.json"
                
                req = urllib.request.Request(
                    tracker_url,
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                )
                
                with urllib.request.urlopen(req, timeout=60) as response:
                    self._tracker_cache = json.loads(response.read().decode('utf-8'))
                
                # Save tracker.json to parent folder
                tracker_path = os.path.join(self.parent_folder, "tracker.json")
                with open(tracker_path, 'w', encoding='utf-8') as f:
                    json.dump(self._tracker_cache, f, ensure_ascii=False, indent=2)
                
                self._log_safe(f"✅ Tracker data saved: {tracker_path}")
                self._log_safe(f"   Found {len(self._tracker_cache)} Pokemon entries")
                
                if self.cancel_operation:
                    self._log_safe("❌ Cancelled")
                    return
                
                # Step 2: Create folders and download portraits
                self._log_safe(f"\nStep 2: Creating folders and downloading portraits ({start_id:04d} to {end_id:04d})...")
                
                total = end_id - start_id + 1
                success_count = 0
                skip_count = 0
                fail_count = 0
                
                for i, poke_id in enumerate(range(start_id, end_id + 1)):
                    if self.cancel_operation:
                        self._log_safe(f"\n❌ Cancelled at {poke_id:04d}")
                        break
                    
                    sprite_id = f"{poke_id:04d}"
                    
                    # Update progress
                    self.main_frame.after(0, lambda p=i+1, t=total: self.prepare_progress_label.config(
                        text=f"Progress: {p}/{t} ({p*100//t}%)"
                    ))
                    
                    # Check if Pokemon exists in tracker
                    if sprite_id not in self._tracker_cache:
                        # self._log_safe(f"⚠ {sprite_id}: Not in tracker, skipping")
                        skip_count += 1
                        continue
                    
                    pokemon_data = self._tracker_cache[sprite_id]
                    name = pokemon_data.get('name', 'Unknown')
                    folder_name = f"{sprite_id} {name}"
                    
                    # Create folder
                    dest_folder = os.path.join(self.parent_folder, folder_name)
                    if not os.path.exists(dest_folder):
                        os.makedirs(dest_folder)
                    
                    # Check if portrait already exists
                    portrait_path = os.path.join(dest_folder, "portrait.png")
                    if os.path.exists(portrait_path):
                        skip_count += 1
                        continue
                    
                    # Download portrait
                    portrait_url = f"https://raw.githubusercontent.com/PMDCollab/SpriteCollab/master/portrait/{sprite_id}/Normal.png"
                    
                    try:
                        req = urllib.request.Request(portrait_url, headers={'User-Agent': 'Mozilla/5.0'})
                        with urllib.request.urlopen(req, timeout=15) as response:
                            with open(portrait_path, 'wb') as f:
                                f.write(response.read())
                        success_count += 1
                        if success_count % 25 == 0:
                            self._log_safe(f"   Downloaded {success_count} portraits...")
                    except urllib.error.HTTPError:
                        fail_count += 1
                    except Exception as e:
                        fail_count += 1
                
                self._log_safe(f"\n✅ Preparation complete!")
                self._log_safe(f"   Created/Downloaded: {success_count}")
                self._log_safe(f"   Skipped (existing/not in tracker): {skip_count}")
                self._log_safe(f"   Failed: {fail_count}")
                
            except Exception as e:
                self._log_safe(f"\n❌ Error: {str(e)}")
            finally:
                self.main_frame.after(0, lambda: self.prepare_button.config(state='normal', text='Start Preparation'))
                self.main_frame.after(0, lambda: self.cancel_prepare_button.config(state='disabled'))
        
        thread = threading.Thread(target=prepare_thread, daemon=True)
        thread.start()

    def show_download_sprites_visual_view(self):
        """Shows the visual view for selecting and downloading sprites from PMDCollab."""
        self.clear_frame()
        if self.update_breadcrumbs:
            path = self.base_path + [("Batch Tasks", self.show_task_selection_view), ("Download Sprites", self.show_download_sprites_visual_view)]
            self.update_breadcrumbs(path)
        
        top_frame = Frame(self.main_frame)
        top_frame.pack(fill='x', padx=10, pady=5)
        Button(top_frame, text="Back to Tasks", command=self.show_task_selection_view).pack(side='left')
        
        content_frame = Frame(self.main_frame)
        content_frame.pack(pady=10, padx=10, fill='both', expand=True)
        
        Label(content_frame, text="Download Sprites from PMDCollab", font=('Arial', 14, 'bold')).pack(pady=(0, 5))
        Label(content_frame, text="Click on Pokemon portraits to select/deselect them. Selected Pokemon will be highlighted in green.", 
              font=('Arial', 9)).pack(pady=(0, 10))
        
        # Control frame
        control_frame = Frame(content_frame)
        control_frame.pack(fill='x', pady=5)
        
        # Selection info
        self.selection_label = Label(control_frame, text="Selected: 0", font=('Arial', 10, 'bold'))
        self.selection_label.pack(side='left', padx=10)
        
        Button(control_frame, text="Select All", command=self._select_all_visual).pack(side='left', padx=5)
        Button(control_frame, text="Deselect All", command=self._deselect_all_visual).pack(side='left', padx=5)
        Button(control_frame, text="Select Missing Sprites", command=self._select_missing_sprites).pack(side='left', padx=5)
        
        self.download_selected_button = Button(control_frame, text="Download Selected", 
                                                command=self._download_selected_sprites, 
                                                bg="lightgreen", font=('Arial', 11))
        self.download_selected_button.pack(side='right', padx=10)
        
        # Create scrollable canvas for the grid
        canvas_frame = Frame(content_frame)
        canvas_frame.pack(fill='both', expand=True)
        
        self.visual_canvas = Canvas(canvas_frame, bg='white')
        v_scrollbar = Scrollbar(canvas_frame, orient='vertical', command=self.visual_canvas.yview)
        
        self.visual_canvas.configure(yscrollcommand=v_scrollbar.set)
        
        v_scrollbar.pack(side='right', fill='y')
        self.visual_canvas.pack(side='left', fill='both', expand=True)
        
        # Create inner frame for grid
        self.visual_inner_frame = Frame(self.visual_canvas, bg='white')
        self.canvas_window = self.visual_canvas.create_window((0, 0), window=self.visual_inner_frame, anchor='nw')
        
        # Bind scroll events
        self.visual_inner_frame.bind('<Configure>', lambda e: self.visual_canvas.configure(scrollregion=self.visual_canvas.bbox('all')))
        self.visual_canvas.bind('<MouseWheel>', lambda e: self.visual_canvas.yview_scroll(int(-1*(e.delta/120)), 'units'))
        
        # Storage for selection
        self.selected_pokemon = set()
        self.pokemon_frames = {}
        self.portrait_photos = {}  # Keep references to prevent garbage collection
        
        # Load and display portraits after window is rendered to get proper width
        self.main_frame.after(50, self._load_portrait_grid)

    def _load_portrait_grid(self):
        """Loads the portrait grid from existing folders."""
        # Get all valid folders with portraits
        folders_with_portraits = []
        
        for folder in self.project_folders:
            folder_path = os.path.join(self.parent_folder, folder)
            portrait_path = os.path.join(folder_path, "portrait.png")
            
            if os.path.exists(portrait_path) and self._is_valid_pokemon_folder(folder):
                parts = folder.split(' ', 1)
                if len(parts) == 2:
                    sprite_id = parts[0]
                    name = parts[1]
                    folders_with_portraits.append({
                        'folder': folder,
                        'id': sprite_id,
                        'name': name,
                        'portrait_path': portrait_path,
                        'folder_path': folder_path
                    })
        
        folders_with_portraits.sort(key=lambda x: x['id'])
        
        if not folders_with_portraits:
            Label(self.visual_inner_frame, text="No portraits found. Run 'Prepare Pokemon Data' first!", 
                  font=('Arial', 12), bg='white').pack(pady=50)
            return
        
        PORTRAIT_SIZE = 48
        CELL_WIDTH = 86
        
        # Calculate columns based on current canvas width
        canvas_width = self.visual_canvas.winfo_width()
        if canvas_width < 100:
            canvas_width = 1200  # Default for maximized window
        
        columns = max(1, canvas_width // CELL_WIDTH)
        
        for i, poke_data in enumerate(folders_with_portraits):
            row = i // columns
            col = i % columns
            
            cell_frame = Frame(self.visual_inner_frame, bg='white', relief='flat', bd=2,
                              highlightthickness=2, highlightbackground='lightgray')
            cell_frame.grid(row=row, column=col, padx=2, pady=2, sticky='nw')
            
            self.pokemon_frames[poke_data['id']] = {
                'frame': cell_frame,
                'data': poke_data
            }
            
            try:
                img = Image.open(poke_data['portrait_path'])
                if img.width > PORTRAIT_SIZE or img.height > PORTRAIT_SIZE:
                    img = img.resize((PORTRAIT_SIZE, PORTRAIT_SIZE), Image.Resampling.NEAREST)
                
                photo = ImageTk.PhotoImage(img)
                self.portrait_photos[poke_data['id']] = photo
                
                img_label = Label(cell_frame, image=photo, bg='white', cursor='hand2')
                img_label.pack(pady=(3, 0))
                
                display_name = poke_data['name'][:8] + ".." if len(poke_data['name']) > 10 else poke_data['name']
                name_label = Label(cell_frame, text=f"{poke_data['id']}\n{display_name}", 
                                   font=('Arial', 7), bg='white', cursor='hand2')
                name_label.pack()
                
                sprite_id = poke_data['id']
                img_label.bind('<Button-1>', lambda e, sid=sprite_id: self._toggle_pokemon_selection(sid))
                name_label.bind('<Button-1>', lambda e, sid=sprite_id: self._toggle_pokemon_selection(sid))
                cell_frame.bind('<Button-1>', lambda e, sid=sprite_id: self._toggle_pokemon_selection(sid))
                
            except Exception as e:
                Label(cell_frame, text=f"{poke_data['id']}\nError", font=('Arial', 7), bg='white').pack()

    def _toggle_pokemon_selection(self, sprite_id):
        """Toggles selection for a Pokemon."""
        if sprite_id in self.selected_pokemon:
            self.selected_pokemon.discard(sprite_id)
            if sprite_id in self.pokemon_frames:
                self.pokemon_frames[sprite_id]['frame'].config(highlightbackground='lightgray', bg='white')
                for child in self.pokemon_frames[sprite_id]['frame'].winfo_children():
                    child.config(bg='white')
        else:
            self.selected_pokemon.add(sprite_id)
            if sprite_id in self.pokemon_frames:
                self.pokemon_frames[sprite_id]['frame'].config(highlightbackground='green', bg='lightgreen')
                for child in self.pokemon_frames[sprite_id]['frame'].winfo_children():
                    try:
                        child.config(bg='lightgreen')
                    except:
                        pass
        
        self.selection_label.config(text=f"Selected: {len(self.selected_pokemon)}")

    def _select_all_visual(self):
        """Selects all Pokemon in the visual grid."""
        for sprite_id in self.pokemon_frames.keys():
            if sprite_id not in self.selected_pokemon:
                self._toggle_pokemon_selection(sprite_id)

    def _deselect_all_visual(self):
        """Deselects all Pokemon in the visual grid."""
        for sprite_id in list(self.selected_pokemon):
            self._toggle_pokemon_selection(sprite_id)

    def _select_missing_sprites(self):
        """Selects Pokemon that don't have sprites downloaded yet."""
        self._deselect_all_visual()
        
        for sprite_id, frame_data in self.pokemon_frames.items():
            folder_path = frame_data['data']['folder_path']
            animations_folder = os.path.join(folder_path, "Animations")
            sprites_zip = os.path.join(folder_path, "sprites.zip")
            
            # Check if sprites are missing (no Animations folder or no sprites.zip)
            if not os.path.exists(animations_folder) or not os.path.exists(sprites_zip):
                self._toggle_pokemon_selection(sprite_id)

    def _download_selected_sprites(self):
        """Downloads sprites for all selected Pokemon using parallel downloads."""
        if not self.selected_pokemon:
            messagebox.showwarning("Warning", "Please select at least one Pokemon.")
            return
        
        # Create a simple log dialog
        log_window = Toplevel(self.main_frame)
        log_window.title("Download Progress")
        log_window.geometry("650x450")
        log_window.transient(self.main_frame.winfo_toplevel())
        
        total_count = len(self.selected_pokemon)
        
        header_label = Label(log_window, text=f"Downloading sprites for {total_count} Pokemon (parallel)...", 
              font=('Arial', 11, 'bold'))
        header_label.pack(pady=10)
        
        progress_label = Label(log_window, text="Progress: 0/0 (0%)", font=('Arial', 10))
        progress_label.pack(pady=5)
        
        log_text = Text(log_window, height=16, width=75, font=('Courier', 9))
        scrollbar = Scrollbar(log_window, command=log_text.yview)
        log_text.configure(yscrollcommand=scrollbar.set)
        log_text.pack(side='left', fill='both', expand=True, padx=10, pady=10)
        scrollbar.pack(side='right', fill='y', pady=10)
        
        close_button = Button(log_window, text="Close", command=log_window.destroy, state='disabled')
        close_button.pack(pady=10)
        
        def log_msg(msg):
            log_text.insert(END, msg + "\n")
            log_text.see(END)
        
        self.download_selected_button.config(state='disabled')
        
        def download_single_pokemon(sprite_id):
            """Downloads a single Pokemon's sprites. Returns (sprite_id, success, folder_name, error_msg)."""
            try:
                frame_data = self.pokemon_frames.get(sprite_id)
                if not frame_data:
                    return (sprite_id, False, sprite_id, "Frame data not found")
                
                folder_path = frame_data['data']['folder_path']
                folder_name = frame_data['data']['folder']
                animations_folder = os.path.join(folder_path, "Animations")
                
                if not os.path.exists(animations_folder):
                    os.makedirs(animations_folder)
                
                # Download sprites.zip
                zip_url = f"https://spriteserver.pmdcollab.org/assets/{sprite_id}/sprites.zip"
                zip_path = os.path.join(folder_path, "sprites.zip")
                
                req = urllib.request.Request(zip_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=30) as response:
                    with open(zip_path, 'wb') as f:
                        f.write(response.read())
                
                # Extract
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(animations_folder)
                
                # Download recolor PNG (non-critical, ignore errors)
                try:
                    recolor_url = f"https://spriteserver.pmdcollab.org/assets/sprite_recolor-{sprite_id}-0000-0001.png"
                    recolor_path = os.path.join(folder_path, f"sprite_recolor-{sprite_id}-0000-0001.png")
                    req = urllib.request.Request(recolor_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=15) as response:
                        with open(recolor_path, 'wb') as f:
                            f.write(response.read())
                except:
                    pass
                
                return (sprite_id, True, folder_name, None)
                
            except Exception as e:
                return (sprite_id, False, sprite_id, str(e))
        
        def download_thread():
            try:
                sorted_ids = sorted(list(self.selected_pokemon))
                completed = 0
                success_count = 0
                fail_count = 0
                
                # Use parallel downloads with ThreadPoolExecutor
                max_workers = min(10, len(sorted_ids))  # Max 10 parallel downloads
                
                log_window.after(0, lambda: log_msg(f"Starting parallel download with {max_workers} workers...\n"))
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {executor.submit(download_single_pokemon, sid): sid for sid in sorted_ids}
                    
                    for future in concurrent.futures.as_completed(futures):
                        sprite_id, success, folder_name, error_msg = future.result()
                        completed += 1
                        
                        if success:
                            success_count += 1
                            log_window.after(0, lambda fn=folder_name: log_msg(f"✅ {fn}"))
                        else:
                            fail_count += 1
                            log_window.after(0, lambda sid=sprite_id, err=error_msg: log_msg(f"❌ {sid}: {err}"))
                        
                        # Update progress
                        pct = completed * 100 // total_count
                        log_window.after(0, lambda c=completed, p=pct: progress_label.config(
                            text=f"Progress: {c}/{total_count} ({p}%)"
                        ))
                
                log_window.after(0, lambda: log_msg(f"\n{'='*50}"))
                log_window.after(0, lambda s=success_count, f=fail_count: log_msg(
                    f"✅ Download complete! Success: {s}, Failed: {f}"
                ))
                
            except Exception as e:
                log_window.after(0, lambda: log_msg(f"\n❌ Error: {str(e)}"))
            finally:
                log_window.after(0, lambda: close_button.config(state='normal'))
                self.main_frame.after(0, lambda: self.download_selected_button.config(state='normal'))
        
        thread = threading.Thread(target=download_thread, daemon=True)
        thread.start()

    def _get_pokemon_folder_name(self, sprite_id):
        """
        Gets the Pokemon name for the folder by fetching the tracker.json from GitHub.
        Uses cache to avoid repeated downloads.
        Returns the folder name in format "0001 Bulbasaur" or None if not found.
        """
        try:
            # Use cached tracker data if available
            if self._tracker_cache is None:
                tracker_url = "https://raw.githubusercontent.com/PMDCollab/SpriteCollab/master/tracker.json"
                self._log_safe(f"Fetching tracker data from GitHub...")
                
                req = urllib.request.Request(
                    tracker_url,
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                )
                
                with urllib.request.urlopen(req, timeout=30) as response:
                    self._tracker_cache = json.loads(response.read().decode('utf-8'))
                
                self._log_safe(f"Tracker data loaded successfully ({len(self._tracker_cache)} entries)")
            
            # The tracker uses 4-digit padded string keys like "0001", "0025", etc.
            if sprite_id in self._tracker_cache:
                pokemon_data = self._tracker_cache[sprite_id]
                name = pokemon_data.get('name', '')
                if name:
                    return f"{sprite_id} {name}"
            
            # Also try without leading zeros as fallback
            sprite_id_int = str(int(sprite_id))
            if sprite_id_int in self._tracker_cache:
                pokemon_data = self._tracker_cache[sprite_id_int]
                name = pokemon_data.get('name', '')
                if name:
                    return f"{sprite_id} {name}"
            
            self._log_safe(f"ID {sprite_id} not found in tracker data")
            return None
            
        except Exception as e:
            self._log_safe(f"Could not fetch name for {sprite_id}: {e}")
            return None

    def _log_safe(self, message):
        """Thread-safe logging."""
        self.main_frame.after(0, lambda: self._log_download(message))

    def _log_download(self, message):
        """Logs a message to the download text widget (different from main _log)."""
        if self.log_text and self.log_text.winfo_exists():
            self.log_text.insert(END, message + "\n")
            self.log_text.see(END)