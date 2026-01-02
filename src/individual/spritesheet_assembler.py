# spritesheet_assembler.py

import os
import json
import threading
import queue
import pathlib
from tkinter import Frame, Label, Button, Checkbutton, BooleanVar, Text, Scrollbar, END, messagebox, Canvas
from PIL import Image, ImageOps

class SpritesheetAssembler:
    def __init__(self, parent_frame, folder, return_to_main_callback, update_breadcrumbs_callback=None, base_path=None):
        self.parent_frame = parent_frame
        self.folder = folder
        self.return_to_main = return_to_main_callback
        self.update_breadcrumbs = update_breadcrumbs_callback
        self.base_path = base_path if base_path is not None else []
        
        self.anim_data_folder = os.path.join(self.folder, "AnimationData")
        self.output_folder = os.path.join(self.folder, "AssembledAnimations")
        
        self.main_frame = Frame(self.parent_frame)
        self.main_frame.pack(fill='both', expand=True)
        
        self.animations = {}
        self.action_button = None
        self.log_text = None
        self.worker_thread = None
        self.progress_queue = None

        self.setup_ui()

    def setup_ui(self):
        if self.update_breadcrumbs:
            path = self.base_path + [("Assemble Spritesheets", self.setup_ui)]
            self.update_breadcrumbs(path)

        top_frame = Frame(self.main_frame)
        top_frame.pack(fill='x', padx=10, pady=5)
        Button(top_frame, text="Main Menu", command=self.return_to_main).pack(side='left')

        content_frame = Frame(self.main_frame)
        content_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        Label(content_frame, text="Assemble Spritesheets from AnimationData", font=('Arial', 14, 'bold')).pack(pady=(0, 10))
        Label(content_frame, text="Select animations and click 'Assemble' to generate the spritesheet images.", wraplength=600).pack(pady=(0, 10))

        # --- Animation selection list ---
        list_container = Frame(content_frame, bd=1, relief="sunken")
        list_container.pack(fill='both', expand=True, pady=5)
        
        canvas = Canvas(list_container)
        scrollbar = Scrollbar(list_container, orient="vertical", command=canvas.yview)
        scroll_frame = Frame(canvas)
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self._scan_and_populate_animations(scroll_frame)

        # --- Actions and Log ---
        bottom_frame = Frame(content_frame)
        bottom_frame.pack(fill='both', expand=True, pady=5)
        
        action_frame = Frame(bottom_frame)
        action_frame.pack(fill='x', pady=5)
        Button(action_frame, text="Select All", command=self._select_all).pack(side='left', padx=5)
        Button(action_frame, text="Deselect All", command=self._deselect_all).pack(side='left', padx=5)
        self.action_button = Button(action_frame, text="Assemble Selected Animations", command=self._start_assembly, bg="lightblue", font=('Arial', 10, 'bold'))
        self.action_button.pack(side='left', padx=20)

        log_frame = Frame(bottom_frame)
        log_frame.pack(fill='both', expand=True, pady=5)
        self.log_text = Text(log_frame, height=10, wrap='word', state='disabled')
        log_scroll = Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.config(yscrollcommand=log_scroll.set)
        log_scroll.pack(side='right', fill='y')
        self.log_text.pack(side='left', fill='both', expand=True)

    def _scan_and_populate_animations(self, parent):
        self.animations.clear()
        if not os.path.exists(self.anim_data_folder):
            Label(parent, text="The 'AnimationData' folder could not be found.", fg="red").pack(padx=10, pady=10)
            return

        json_files = sorted([f for f in os.listdir(self.anim_data_folder) if f.lower().endswith('-animdata.json')])

        if not json_files:
            Label(parent, text="No '-AnimData.json' files found in the 'AnimationData' folder.").pack(padx=10, pady=10)
            return

        for json_file in json_files:
            anim_name = json_file.replace("-AnimData.json", "")
            var = BooleanVar(value=True)
            cb = Checkbutton(parent, text=anim_name, variable=var, anchor='w')
            cb.pack(fill='x', padx=5, pady=2)
            self.animations[anim_name] = {
                "path": os.path.join(self.anim_data_folder, json_file),
                "var": var
            }

    def _select_all(self):
        for anim in self.animations.values():
            anim['var'].set(True)

    def _deselect_all(self):
        for anim in self.animations.values():
            anim['var'].set(False)

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

    def _start_assembly(self):
        selected_paths = [
            anim['path'] for anim in self.animations.values() if anim['var'].get()
        ]
        
        if not selected_paths:
            messagebox.showwarning("No Selection", "Please select at least one animation to assemble.")
            return

        self._clear_log()
        self.action_button.config(state="disabled", text="Assembling...")
        
        self.progress_queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self._assembly_worker, args=(selected_paths, self.progress_queue), daemon=True)
        self.worker_thread.start()
        self.parent_frame.after(100, self._check_progress_queue)

    def _check_progress_queue(self):
        try:
            message = self.progress_queue.get_nowait()
            if message == "DONE":
                self.action_button.config(state="normal", text="Assemble Selected Animations")
                messagebox.showinfo("Complete", f"Assembly process finished. Spritesheets are in:\n{self.output_folder}")
            else:
                self._log(message)
                self.parent_frame.after(100, self._check_progress_queue)
        except queue.Empty:
            self.parent_frame.after(100, self._check_progress_queue)

    def _assembly_worker(self, selected_paths, q):
        q.put(f"Starting assembly for {len(selected_paths)} animation(s)...")
        os.makedirs(self.output_folder, exist_ok=True)
        
        success_count, fail_count = 0, 0
        for json_path in selected_paths:
            if self._assemble_one_animation(json_path, q):
                success_count += 1
            else:
                fail_count += 1

        q.put("\n" + "="*50)
        q.put(f"Assembly finished. Success: {success_count}, Failed: {fail_count}")
        q.put("="*50)
        q.put("DONE")

    def _load_sprite(self, sprite_folder, sprite_id_str):
        is_mirrored = "_mirrored" in sprite_id_str
        base_id = sprite_id_str.replace("_mirrored", "")
        
        path = os.path.join(sprite_folder, f"sprite_{base_id}.png")
        try:
            sprite = Image.open(path).convert('RGBA')
            return ImageOps.mirror(sprite) if is_mirrored else sprite
        except FileNotFoundError:
            return None

    def _assemble_one_animation(self, json_path, q):
        try:
            anim_name = pathlib.Path(json_path).stem.replace("-AnimData", "")
            q.put(f"-> Assembling '{anim_name}'...")

            with open(json_path, 'r') as f:
                data = json.load(f)

            sprite_folder = os.path.join(self.anim_data_folder, anim_name)
            if not os.path.exists(sprite_folder):
                q.put(f"  [ERROR] Sprite folder not found for '{anim_name}'. Skipping.")
                return False

            groups = data.get('sprites', {})
            if not groups:
                q.put(f"  [WARNING] No sprite groups found in JSON for '{anim_name}'. Skipping.")
                return False
            
            sheet_data = {
                "name": anim_name,
                "durations": data.get("durations", []),
                "groups": {}
            }
            
            num_groups = len(groups)
            num_frames, max_fw, max_fh = 0, 0, 0
            
            sorted_groups = sorted(groups.items(), key=lambda item: int(item[0]))

            for _, group_data in sorted_groups:
                num_frames = max(num_frames, len(group_data.get('frames', [])))
                max_fw = max(max_fw, group_data.get('framewidth', 0))
                max_fh = max(max_fh, group_data.get('frameheight', 0))
            
            if num_frames == 0 or max_fw == 0 or max_fh == 0:
                q.put(f"  [ERROR] Invalid frame dimensions for '{anim_name}'. Skipping.")
                return False

            sheet_data["frameWidth"] = max_fw
            sheet_data["frameHeight"] = max_fh
            sheet_data["framesPerGroup"] = num_frames
            sheet_data["totalGroups"] = num_groups

            sheet_width = max_fw * num_frames
            sheet_height = max_fh * num_groups
            
            spritesheet = Image.new('RGBA', (sheet_width, sheet_height), (0, 0, 0, 0))

            for row_idx, (group_id, group_data) in enumerate(sorted_groups):
                bbox_anchor = group_data.get('bounding_box_anchor')
                if not bbox_anchor:
                    q.put(f"  [WARNING] No bounding_box_anchor for group {group_id} in '{anim_name}'. Sprites may be misplaced.")
                    bbox_anchor = [0, 0]

                group_name = group_data.get("name", f"group{group_id}")
                sheet_data["groups"][group_id] = {
                    "name": group_name,
                    "frames": [],
                    "boundingBoxAnchor": bbox_anchor
                }

                frames = group_data.get('frames', [])
                for col_idx, frame_info in enumerate(frames):
                    sprite_id = frame_info.get('id', '0')
                    if sprite_id == '0':
                        sheet_data["groups"][group_id]["frames"].append(None)
                        continue

                    sprite_img = self._load_sprite(sprite_folder, sprite_id)
                    if not sprite_img:
                        q.put(f"  [WARNING] Could not load sprite '{sprite_id}' for '{anim_name}'.")
                        sheet_data["groups"][group_id]["frames"].append(None)
                        continue

                    render_offset = frame_info.get('render_offset')
                    if not render_offset:
                        q.put(f"  [WARNING] No render_offset for sprite '{sprite_id}' in '{anim_name}'.")
                        sheet_data["groups"][group_id]["frames"].append(None)
                        continue
                    
                    paste_x_in_cell = render_offset[0] - bbox_anchor[0]
                    paste_y_in_cell = render_offset[1] - bbox_anchor[1]
                    
                    cell_x = col_idx * max_fw
                    cell_y = row_idx * max_fh
                    
                    final_paste_pos = (cell_x + paste_x_in_cell, cell_y + paste_y_in_cell)
                    spritesheet.paste(sprite_img, final_paste_pos, sprite_img)

                    sprite_w, sprite_h = sprite_img.size
                    frame_hitbox_data = {
                        "x": paste_x_in_cell,
                        "y": paste_y_in_cell,
                        "w": sprite_w,
                        "h": sprite_h
                    }
                    sheet_data["groups"][group_id]["frames"].append(frame_hitbox_data)

            output_path = os.path.join(self.output_folder, f"{anim_name}-Anim.png")
            spritesheet.save(output_path)
            q.put(f"  [SUCCESS] Saved spritesheet to '{pathlib.Path(output_path).relative_to(pathlib.Path(self.folder))}'")

            json_output_path = os.path.join(self.output_folder, f"{anim_name}-AnimSheetData.json")
            with open(json_output_path, 'w') as f:
                json.dump(sheet_data, f, indent=4)
            q.put(f"  [SUCCESS] Saved metadata to '{pathlib.Path(json_output_path).relative_to(pathlib.Path(self.folder))}'")

            return True

        except Exception as e:
            q.put(f"  [CRITICAL ERROR] Failed to assemble '{anim_name}': {e}")
            return False