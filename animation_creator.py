from tkinter import Frame, Label, Button, Entry, Canvas, Scrollbar, messagebox, filedialog
from PIL import Image, ImageTk, ImageOps, ImageDraw
from sprite_sheet_handler import SpriteSheetHandler
import os
import json
import math

class AnimationCreator:
    def __init__(self, parent_frame, folder, return_to_main_callback, start_directly_at_json_upload=False):
        self.parent_frame = parent_frame
        self.folder = folder  # The project folder
        self.return_to_main = return_to_main_callback
        self.start_directly_at_json_upload = start_directly_at_json_upload
        
        self.sprites = []
        self.image_path = None # Will be auto-detected
        self.output_folder = None # Will be the "Sprites" folder
        self.json_data = None
        self.after_ids = []
        
        self.main_frame = Frame(self.parent_frame)
        self.main_frame.pack(fill='both', expand=True)
        
        self.setup_ui()
        
    def _auto_load_image(self):
        """Automatically find and load the first PNG spritesheet in the folder."""
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
        """Set up the step-by-step interface."""
        if self.start_directly_at_json_upload:
            self.output_folder = os.path.join(self.folder, "Sprites")
            self.show_json_upload_view()
        elif self._auto_load_image():
            self.show_process_sheet_view()

    def show_process_sheet_view(self):
        """Show Step 1: Process the spritesheet and save sprites."""
        self.clear_frame()
        
        self.process_frame = Frame(self.main_frame)
        self.process_frame.pack(pady=20)
        
        Label(self.process_frame, text="Step 1: Process Spritesheet", font=('Arial', 14)).pack(pady=10)
        
        img = Image.open(self.image_path)
        img.thumbnail((500, 400))
        self.img_tk = ImageTk.PhotoImage(img)
        Label(self.process_frame, image=self.img_tk, text=f"Loaded: {os.path.basename(self.image_path)}", compound='top').pack(pady=10)
        
        form_frame = Frame(self.process_frame)
        form_frame.pack(pady=10)
        
        Label(form_frame, text="Size (width/height):").grid(row=0, column=0)
        self.size_entry = Entry(form_frame)
        self.size_entry.grid(row=0, column=1, padx=5)
        
        Label(form_frame, text="Number of Sprites to Save:").grid(row=1, column=0)
        self.sprite_number_entry = Entry(form_frame)
        self.sprite_number_entry.grid(row=1, column=1, padx=5)
        
        Button(form_frame, text="Process and Save Sprites", command=self.process_spritesheet).grid(row=2, columnspan=2, pady=10)

    def process_spritesheet(self):
        """Process the spritesheet and save individual sprites to the 'Sprites' folder."""
        try:
            size = int(self.size_entry.get())
            sprites_width = size
            sprites_height = size

            sprite_number = int(self.sprite_number_entry.get())
            
            self.saved_width = sprites_width
            self.saved_height = sprites_height
            
            # This is a rough estimation; the handler now returns the true number.
            img = Image.open(self.image_path)
            total_sprites = (img.width // (img.width // sprites_width)) * (img.height // (img.height // sprites_height))
            
            if sprite_number > total_sprites:
                messagebox.showerror("Error", f"Cannot save {sprite_number} sprites. The spritesheet may only contain up to {total_sprites} sprites.")
                return
            
            folder_name = "Sprites"
            self.output_folder = os.path.join(self.folder, folder_name)
            
            if os.path.exists(self.output_folder) and os.listdir(self.output_folder):
                response = messagebox.askyesno("Confirmation", f"The folder '{folder_name}' already contains files. Do you want to delete them and continue?")
                if not response:
                    return
            
            os.makedirs(self.output_folder, exist_ok=True)
            for file in os.listdir(self.output_folder):
                os.unlink(os.path.join(self.output_folder, file))
            
            handler = SpriteSheetHandler(self.image_path, remove_first_row=True, remove_first_col=False)
            self.sprites, self.sprite_width, self.sprite_height = handler.split_sprites(sprites_width, sprites_height)
            self.sprites = self.sprites[:sprite_number]
            
            for idx, sprite in enumerate(self.sprites):
                sprite.save(os.path.join(self.output_folder, f"sprite_{idx + 1}.png"))
            
            messagebox.showinfo("Success", f"{len(self.sprites)} sprites saved in:\n{self.output_folder}")
            self.show_json_upload_view()
            
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numeric values")
        except Exception as e:
            messagebox.showerror("Error", f"Processing error: {str(e)}")

    def show_json_upload_view(self):
        """Show Step 2: Upload JSON of animations and view generated sprites."""
        self.clear_frame()
        
        json_frame = Frame(self.main_frame)
        json_frame.pack(pady=20, fill='both', expand=True)
        
        button_frame = Frame(json_frame)
        button_frame.pack(fill='x', pady=10)
        
        Button(button_frame, text="Main Menu", command=self.return_to_main).pack(side='left', padx=5)
        if not self.start_directly_at_json_upload:
            Button(button_frame, text="Back", command=self.show_process_sheet_view).pack(side='left', padx=5)
        Button(button_frame, text="Select Animation JSON", command=self.load_json).pack(side='left', padx=5)
        
        self.show_generated_sprites()

    def show_generated_sprites(self):
        """Show the generated sprites in a grid."""
        if not self.output_folder or not os.path.exists(self.output_folder):
            return
        
        sprite_files = sorted(
            [f for f in os.listdir(self.output_folder) if f.lower().endswith('.png')],
            key=lambda x: int(x.split('_')[-1].split('.')[0])
        )
        
        sprite_display_frame = Frame(self.main_frame)
        sprite_display_frame.pack(fill='both', expand=True, pady=10)
        
        # Try to determine a reasonable number of columns
        num_columns = getattr(self, 'saved_width', 10)
        row, col = 0, 0
        
        for sprite_file in sprite_files:
            sprite_path = os.path.join(self.output_folder, sprite_file)
            sprite = Image.open(sprite_path)
            sprite.thumbnail((80, 80))
            img_tk = ImageTk.PhotoImage(sprite)
            
            sprite_frame = Frame(sprite_display_frame)
            sprite_frame.grid(row=row, column=col, padx=5, pady=5)
            
            label = Label(sprite_frame, image=img_tk)
            label.image = img_tk
            label.pack()
            
            Label(sprite_frame, text=sprite_file, font=('Arial', 8)).pack()
            
            col += 1
            if col >= num_columns: col = 0; row += 1

    def load_json(self):
        """Load animation JSON file."""
        file_path = filedialog.askopenfilename(title="Select Animation JSON", filetypes=(("JSON files", "*.json"), ("All files", "*.*")))
        if file_path:
            with open(file_path, 'r') as f:
                self.json_data = json.load(f)
            self.show_animation_preview()

    def show_animation_preview(self):
        """Show the animation preview view."""
        self.clear_frame()
        
        self.animation_frame = Frame(self.main_frame)
        self.animation_frame.pack(fill='both', expand=True)
        
        self.canvas = Canvas(self.animation_frame)
        self.scrollbar = Scrollbar(self.animation_frame, orient="vertical", command=self.canvas.yview)
        self.scroll_frame = Frame(self.canvas)
        self.scroll_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        Button(self.scroll_frame, text="Back", command=self.show_json_upload_view).pack(pady=10)
        Label(self.scroll_frame, text="Animation Preview", font=('Arial', 16)).pack(pady=10)
        
        for group_id, group_data in self.json_data["sprites"].items():
            self.create_group_preview(group_id, group_data)

    def create_group_preview(self, group_id, group_data):
        """Create a preview for an animation group."""
        group_frame = Frame(self.scroll_frame, bd=2, relief="groove")
        group_frame.pack(fill="x", padx=5, pady=5)
        
        header_frame = Frame(group_frame); header_frame.pack(fill="x", pady=5)
        group_name = group_data.get("name", f"Group {group_id}")
        Label(header_frame, text=group_name, font=('Arial', 12, 'bold')).pack(side='left')
        
        is_mirrored_copy = group_data.get("mirrored", False)
        if is_mirrored_copy:
            Label(header_frame, text="(Mirrored)", fg="blue").pack(side='left', padx=10)
        
        content_frame = Frame(group_frame); content_frame.pack(fill="x")
        
        raw_frames = self.get_group_frames(group_data)
        
        offsets = None
        if is_mirrored_copy:
            source_group_data = self.json_data["sprites"][group_data["copy"]]
            offsets = source_group_data.get("offsets")
        else:
            offsets = group_data.get("offsets")

        final_frames = []
        if offsets and self.json_data.get("framewidth"):
            final_frames = self._apply_offsets_to_frames(raw_frames, offsets, is_mirrored_copy)
        else:
            final_frames = raw_frames

        durations = self.json_data["durations"]
        
        anim_panel = Frame(content_frame); anim_panel.pack(side="left", padx=10)
        anim_label = Label(anim_panel); anim_label.pack()
        self.start_animation(anim_label, final_frames, durations)
        
        sprite_panel = Frame(content_frame); sprite_panel.pack(side="right", fill="x", expand=True)
        for idx, frame in enumerate(raw_frames):
            frame.thumbnail((80, 80))
            img = ImageTk.PhotoImage(frame)
            lbl = Label(sprite_panel, image=img); lbl.image = img; lbl.grid(row=0, column=idx, padx=2)
            Label(sprite_panel, text=f"Dur: {durations[idx]}", font=('Arial', 7)).grid(row=1, column=idx)

    def _apply_offsets_to_frames(self, frames, offsets, is_mirrored):
        frame_width = self.json_data["framewidth"]
        frame_height = self.json_data["frameheight"]
        canvas_width = frame_width * 2
        canvas_height = frame_height * 2
        
        positioned_frames = []
        for i, sprite_img in enumerate(frames):
            if i >= len(offsets): continue

            composite_frame = Image.new('RGBA', (canvas_width, canvas_height), (0, 0, 0, 0))
            
            anchor_x, anchor_y = offsets[i]
            
            if is_mirrored:
                anchor_x = frame_width - anchor_x

            base_x = anchor_x + (frame_width // 2)
            base_y = anchor_y + (frame_height // 2)
            
            sprite_w, sprite_h = sprite_img.size
            paste_x = base_x - sprite_w // 2
            paste_y = base_y - sprite_h // 2
            
            composite_frame.paste(sprite_img, (paste_x, paste_y), sprite_img)
            positioned_frames.append(composite_frame)
            
        return positioned_frames

    def get_group_frames(self, group_data):
        """Get the frames for the group, applying mirror if necessary."""
        if group_data.get("mirrored", False):
            source_group = self.json_data["sprites"][group_data["copy"]]
            frames = self.get_group_frames(source_group)
            return [ImageOps.mirror(frame) for frame in frames]
        else:
            sprite_values = group_data["values"]
            frames = []
            for val in sprite_values:
                sprite_id = 0
                is_mirrored = False
                if isinstance(val, dict):
                    sprite_id = val.get("id", 0)
                    is_mirrored = val.get("mirrored", False)
                elif isinstance(val, int):
                    sprite_id = val
                
                sprite_img = self.load_sprite(sprite_id)
                if is_mirrored:
                    sprite_img = ImageOps.mirror(sprite_img)
                frames.append(sprite_img)
            return frames

    def load_sprite(self, sprite_num):
        """Load a sprite from the generated files in the 'Sprites' folder."""
        try:
            sprite_path = os.path.join(self.output_folder, f"sprite_{sprite_num}.png")
            return Image.open(sprite_path).convert('RGBA')
        except (FileNotFoundError, ValueError):
            placeholder = Image.new('RGBA', (40, 40), (0, 0, 0, 0))
            draw = ImageDraw.Draw(placeholder)
            draw.text((5, 10), f"?{sprite_num}?", fill="red")
            return placeholder

    def start_animation(self, label, frames, durations):
        """Start a real-time animation."""
        current_frame = [0]
        def update():
            if not frames: return
            if current_frame[0] >= len(frames): current_frame[0] = 0
            
            frame = frames[current_frame[0]]
            frame.thumbnail((200, 200))
            img = ImageTk.PhotoImage(frame)
            label.config(image=img); label.image = img
            
            delay = durations[current_frame[0] % len(durations)] * 33
            current_frame[0] += 1
            self.after_ids.append(self.parent_frame.after(delay, update))
        update()
            
    def clear_frame(self):
        """Clear the current frame and stop animations."""
        for aid in self.after_ids:
            self.parent_frame.after_cancel(aid)
        self.after_ids.clear()
        
        for widget in self.main_frame.winfo_children():
            widget.destroy()