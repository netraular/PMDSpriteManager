# animation_creator.py

from tkinter import Frame, Label, Button, Entry, Canvas, Scrollbar, messagebox, filedialog, OptionMenu, StringVar
from PIL import Image, ImageTk, ImageOps, ImageDraw
from sprite_sheet_handler import SpriteSheetHandler
import os
import json
import math

class AnimationCreator:
    def __init__(self, parent_frame, folder, return_to_main_callback, start_directly_at_json_upload=False, start_in_preview_mode=False):
        self.parent_frame = parent_frame
        self.folder = folder
        self.return_to_main = return_to_main_callback
        self.start_directly_at_json_upload = start_directly_at_json_upload
        self.start_in_preview_mode = start_in_preview_mode
        
        self.sprites = []
        self.image_path = None
        self.output_folder = None
        self.json_data = None
        self.after_ids = []
        
        self.main_frame = Frame(self.parent_frame)
        self.main_frame.pack(fill='both', expand=True)
        
        self.setup_ui()
        
    def _auto_load_image(self):
        try:
            png_files = [f for f in os.listdir(self.folder) if f.lower().endswith('.png')]
            if not png_files:
                raise FileNotFoundError("No PNG files found in the selected folder.")
            self.image_path = os.path.join(self.folder, png_files[0])
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Could not load spritesheet: {str(e)}")
            self.return_to_main()
            return False

    def setup_ui(self):
        if self.start_in_preview_mode:
            self.show_animation_selector_view()
        elif self.start_directly_at_json_upload:
            self.output_folder = os.path.join(self.folder, "Sprites")
            self.show_json_upload_view()
        elif self._auto_load_image():
            self.show_process_sheet_view()

    def show_animation_selector_view(self):
        self.clear_frame()
        selector_frame = Frame(self.main_frame)
        selector_frame.pack(pady=20)
        
        Button(selector_frame, text="Back", command=self.return_to_main).pack(pady=10)
        Label(selector_frame, text="Select Animation to Preview", font=('Arial', 16)).pack(pady=10)
        
        self.optimized_folder = os.path.join(self.folder, "AnimationData")

        if not os.path.exists(self.optimized_folder):
            messagebox.showerror("Error", f"Animation data folder not found at:\n{self.optimized_folder}")
            self.return_to_main()
            return

        try:
            json_files = [f for f in os.listdir(self.optimized_folder) if f.lower().endswith('-animdata.json')]
            anim_names = sorted([f.replace('-AnimData.json', '') for f in json_files])
            
            if not anim_names:
                Label(selector_frame, text="No optimized animations found.").pack()
                return

            self.selected_anim_var = StringVar(selector_frame)
            self.selected_anim_var.set(anim_names[0])

            dropdown = OptionMenu(selector_frame, self.selected_anim_var, *anim_names)
            dropdown.pack(pady=10)
            
            Button(selector_frame, text="Load Animation", command=self._load_selected_animation).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to read animations: {e}")

    def _load_selected_animation(self):
        anim_name = self.selected_anim_var.get()
        if not anim_name:
            messagebox.showwarning("Warning", "No animation selected.")
            return
        
        file_path = os.path.join(self.optimized_folder, f"{anim_name}-AnimData.json")
        self._load_json_from_path(file_path)

    def show_process_sheet_view(self):
        self.clear_frame()
        self.process_frame = Frame(self.main_frame); self.process_frame.pack(pady=20)
        Label(self.process_frame, text="Step 1: Process Spritesheet", font=('Arial', 14)).pack(pady=10)
        img = Image.open(self.image_path); img.thumbnail((500, 400)); self.img_tk = ImageTk.PhotoImage(img)
        Label(self.process_frame, image=self.img_tk, text=f"Loaded: {os.path.basename(self.image_path)}", compound='top').pack(pady=10)
        form_frame = Frame(self.process_frame); form_frame.pack(pady=10)
        Label(form_frame, text="Size (width/height):").grid(row=0, column=0)
        self.size_entry = Entry(form_frame); self.size_entry.grid(row=0, column=1, padx=5)
        Label(form_frame, text="Number of Sprites to Save:").grid(row=1, column=0)
        self.sprite_number_entry = Entry(form_frame); self.sprite_number_entry.grid(row=1, column=1, padx=5)
        Button(form_frame, text="Process and Save Sprites", command=self.process_spritesheet).grid(row=2, columnspan=2, pady=10)

    def process_spritesheet(self):
        try:
            size = int(self.size_entry.get())
            sprite_number = int(self.sprite_number_entry.get())
            self.saved_width = size
            img = Image.open(self.image_path)
            total_sprites = (img.width // size) * (img.height // size)
            if sprite_number > total_sprites:
                messagebox.showerror("Error", f"Cannot save {sprite_number} sprites. Sheet may only contain {total_sprites}."); return
            
            self.output_folder = os.path.join(self.folder, "Sprites")
            if os.path.exists(self.output_folder) and os.listdir(self.output_folder):
                if not messagebox.askyesno("Confirmation", "The 'Sprites' folder will be overwritten. Continue?"): return
            
            os.makedirs(self.output_folder, exist_ok=True)
            for file in os.listdir(self.output_folder): os.unlink(os.path.join(self.output_folder, file))
            
            handler = SpriteSheetHandler(self.image_path, remove_first_row=True, remove_first_col=False)
            self.sprites, _, _ = handler.split_sprites(size, size)
            self.sprites = self.sprites[:sprite_number]
            for idx, sprite in enumerate(self.sprites):
                bbox = sprite.getbbox()
                if bbox:
                    sprite = sprite.crop(bbox)
                sprite.save(os.path.join(self.output_folder, f"sprite_{idx + 1}.png"))
            
            messagebox.showinfo("Success", f"{len(self.sprites)} sprites saved in:\n{self.output_folder}")
            self.show_json_upload_view()
        except ValueError: messagebox.showerror("Error", "Please enter valid numeric values")
        except Exception as e: messagebox.showerror("Error", f"Processing error: {str(e)}")

    def show_json_upload_view(self):
        self.clear_frame()
        json_frame = Frame(self.main_frame); json_frame.pack(pady=20, fill='both', expand=True)
        button_frame = Frame(json_frame); button_frame.pack(fill='x', pady=10)
        Button(button_frame, text="Main Menu", command=self.return_to_main).pack(side='left', padx=5)
        if not self.start_directly_at_json_upload:
            Button(button_frame, text="Back", command=self.show_process_sheet_view).pack(side='left', padx=5)
        Button(button_frame, text="Select Optimized Animation JSON", command=self._load_json_from_dialog).pack(side='left', padx=5)
        self.show_generated_sprites()

    def show_generated_sprites(self):
        if not self.output_folder or not os.path.exists(self.output_folder): return
        try:
            sprite_files = sorted([f for f in os.listdir(self.output_folder) if f.lower().endswith('.png')], key=lambda x: int(x.split('_')[-1].split('.')[0]))
        except ValueError:
            sprite_files = sorted([f for f in os.listdir(self.output_folder) if f.lower().endswith('.png')])
        
        sprite_display_frame = Frame(self.main_frame); sprite_display_frame.pack(fill='both', expand=True, pady=10)
        num_columns = getattr(self, 'saved_width', 10)
        row, col = 0, 0
        for sprite_file in sprite_files:
            sprite_path = os.path.join(self.output_folder, sprite_file)
            sprite = Image.open(sprite_path); sprite.thumbnail((80, 80)); img_tk = ImageTk.PhotoImage(sprite)
            sprite_frame = Frame(sprite_display_frame); sprite_frame.grid(row=row, column=col, padx=5, pady=5)
            label = Label(sprite_frame, image=img_tk); label.image = img_tk; label.pack()
            Label(sprite_frame, text=sprite_file, font=('Arial', 8)).pack()
            col += 1
            if col >= num_columns: col = 0; row += 1

    def _load_json_from_dialog(self):
        optimized_folder = os.path.join(self.folder, "AnimationData")
        file_path = filedialog.askopenfilename(
            title="Select Optimized Animation JSON",
            initialdir=optimized_folder if os.path.exists(optimized_folder) else self.folder,
            filetypes=(("JSON files", "*.json"), ("All files", "*.*"))
        )
        if file_path:
            self._load_json_from_path(file_path)

    def _load_json_from_path(self, file_path):
        try:
            with open(file_path, 'r') as f:
                self.json_data = json.load(f)
            
            json_dir = os.path.dirname(file_path)
            anim_name = self.json_data.get('name')
            if anim_name:
                self.output_folder = os.path.join(json_dir, anim_name)
            else:
                self.output_folder = json_dir

            if not os.path.exists(self.output_folder):
                messagebox.showerror("Error", f"Sprite folder for this animation not found at:\n{self.output_folder}")
                return
            self.show_animation_preview()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load or process JSON file: {e}")

    def show_animation_preview(self):
        self.clear_frame()
        self.animation_frame = Frame(self.main_frame); self.animation_frame.pack(fill='both', expand=True)
        self.canvas = Canvas(self.animation_frame)
        self.scrollbar = Scrollbar(self.animation_frame, orient="vertical", command=self.canvas.yview)
        self.scroll_frame = Frame(self.canvas)
        self.scroll_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        back_command = self.show_animation_selector_view if self.start_in_preview_mode else self.show_json_upload_view
        Button(self.scroll_frame, text="Back", command=back_command).pack(pady=10)
        
        Label(self.scroll_frame, text="Animation Preview", font=('Arial', 16)).pack(pady=10)
        for group_id, group_data in self.json_data["sprites"].items():
            self.create_group_preview(group_id, group_data)

    def create_group_preview(self, group_id, group_data):
        group_frame = Frame(self.scroll_frame, bd=2, relief="groove"); group_frame.pack(fill="x", padx=5, pady=5)
        header_frame = Frame(group_frame); header_frame.pack(fill="x", pady=5)
        group_name = group_data.get("name", f"Group {group_id}")
        Label(header_frame, text=group_name, font=('Arial', 12, 'bold')).pack(side='left')
        content_frame = Frame(group_frame); content_frame.pack(fill="x")
        raw_frames = self.get_group_frames(group_data)
        
        # --- MODIFICATION START ---
        frame_data = group_data.get('frames', [])
        offsets = [frame.get('offset', [0, 0]) for frame in frame_data]
        offset_texts = [f"Offset: {offset}" for offset in offsets]
        # --- MODIFICATION END ---
        
        final_frames = self._apply_offsets_to_frames(raw_frames, offsets) if offsets and self.json_data.get("framewidth") else raw_frames
        durations = self.json_data["durations"]
        anim_panel = Frame(content_frame); anim_panel.pack(side="left", padx=10)
        anim_label = Label(anim_panel); anim_label.pack()
        
        # --- MODIFICATION START ---
        offset_label = Label(anim_panel, text="Offset: [N/A]", font=('Arial', 8)); offset_label.pack(pady=(5,0))
        self.start_animation(anim_label, final_frames, durations, text_label=offset_label, text_data=offset_texts)
        # --- MODIFICATION END ---
        
        sprite_panel = Frame(content_frame); sprite_panel.pack(side="right", fill="x", expand=True)
        for idx, frame in enumerate(raw_frames):
            if frame:
                frame.thumbnail((80, 80)); img = ImageTk.PhotoImage(frame)
                lbl = Label(sprite_panel, image=img); lbl.image = img; lbl.grid(row=0, column=idx, padx=2)
                Label(sprite_panel, text=f"Dur: {durations[idx % len(durations)]}", font=('Arial', 7)).grid(row=1, column=idx)

    def _apply_offsets_to_frames(self, frames, offsets):
        fw, fh = self.json_data["framewidth"], self.json_data["frameheight"]
        cw, ch = fw * 2, fh * 2
        positioned_frames = []
        for i, sprite_img in enumerate(frames):
            if i >= len(offsets) or not sprite_img: continue
            composite = Image.new('RGBA', (cw, ch), (0, 0, 0, 0))
            anchor_x, anchor_y = offsets[i]
            sprite_w, sprite_h = sprite_img.size
            frame_origin_x, frame_origin_y = (cw - fw) // 2, (ch - fh) // 2
            paste_x = frame_origin_x + anchor_x - (sprite_w // 2)
            paste_y = frame_origin_y + anchor_y - (sprite_h // 2)
            composite.paste(sprite_img, (paste_x, paste_y), sprite_img)
            
            # --- MODIFICATION START: Draw the frame border ---
            draw = ImageDraw.Draw(composite)
            box_x0 = frame_origin_x
            box_y0 = frame_origin_y
            box_x1 = box_x0 + fw
            box_y1 = box_y0 + fh
            draw.rectangle([box_x0, box_y0, box_x1, box_y1], outline="grey")
            # --- MODIFICATION END ---
            
            positioned_frames.append(composite)
        return positioned_frames

    def get_group_frames(self, group_data):
        frames = []
        for frame_info in group_data.get("frames", []):
            frames.append(self.load_sprite(frame_info.get("id", "0")))
        return frames

    def load_sprite(self, sprite_id_str):
        if sprite_id_str == "0": return None 
        try:
            sprite_path = os.path.join(self.output_folder, f"sprite_{sprite_id_str}.png")
            return Image.open(sprite_path).convert('RGBA')
        except (FileNotFoundError, ValueError):
            placeholder = Image.new('RGBA', (40, 40), (0, 0, 0, 0))
            draw = ImageDraw.Draw(placeholder); draw.text((5, 10), f"?{sprite_id_str}?", fill="red")
            return placeholder

    # --- MODIFICATION START: Update function signature and logic ---
    def start_animation(self, label, frames, durations, text_label=None, text_data=None):
        valid_frames = [f for f in frames if f]
        if not valid_frames:
            label.config(image=None, text="[No valid frames]"); return
        current_frame = [0]
        def update():
            if not label.winfo_exists(): return
            frame_index = current_frame[0] % len(valid_frames)
            
            frame = valid_frames[frame_index]; frame.thumbnail((200, 200)); img = ImageTk.PhotoImage(frame)
            label.config(image=img); label.image = img
            
            if text_label and text_data:
                text_label.config(text=text_data[frame_index % len(text_data)])

            delay = durations[frame_index % len(durations)] * 33
            current_frame[0] += 1
            self.after_ids.append(self.parent_frame.after(delay, update))
        update()
    # --- MODIFICATION END ---
            
    def clear_frame(self):
        for aid in self.after_ids: self.parent_frame.after_cancel(aid)
        self.after_ids.clear()
        for widget in self.main_frame.winfo_children(): widget.destroy()