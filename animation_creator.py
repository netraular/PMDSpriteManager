# animation_creator.py

from tkinter import Frame, Label, Button, Entry, Canvas, Scrollbar, messagebox, filedialog, OptionMenu, StringVar
from PIL import Image, ImageTk, ImageOps, ImageDraw
from sprite_sheet_handler import SpriteSheetHandler
from ui_components.animation_player import AnimationPlayer
from ui_components import isometric_renderer
import os
import json
import math
import pathlib

class AnimationCreator:
    def __init__(self, parent_frame, folder, return_to_main_callback, update_breadcrumbs_callback=None, base_path=None, start_directly_at_json_upload=False, start_in_preview_mode=False, anim_data_subfolder="AnimationData", show_navigation=True):
        self.parent_frame = parent_frame
        self.folder = folder
        self.return_to_main = return_to_main_callback
        self.update_breadcrumbs = update_breadcrumbs_callback
        self.base_path = base_path if base_path is not None else []
        self.start_directly_at_json_upload = start_directly_at_json_upload
        self.start_in_preview_mode = start_in_preview_mode
        self.anim_data_subfolder = anim_data_subfolder
        self.show_navigation = show_navigation
        
        parent_dir_name = pathlib.Path(folder).parent.name
        self.is_2x_preview = (parent_dir_name == "output x2")

        self.sprites = []
        self.image_path = None
        self.json_data = None
        self.players = []
        self.canvas = None
        self.frame_updater_after_id = None
        
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
            self.show_all_animations_preview()
        elif self.start_directly_at_json_upload:
            self.sprite_output_folder = os.path.join(self.folder, "Sprites")
            self.show_json_upload_view()
        elif self._auto_load_image():
            self.show_process_sheet_view()

    def show_process_sheet_view(self):
        if self.update_breadcrumbs:
            path = self.base_path + [("Process Spritesheet", self.show_process_sheet_view)]
            self.update_breadcrumbs(path)
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
            
            self.sprite_output_folder = os.path.join(self.folder, "Sprites")
            if os.path.exists(self.sprite_output_folder) and os.listdir(self.sprite_output_folder):
                if not messagebox.askyesno("Confirmation", "The 'Sprites' folder will be overwritten. Continue?"): return
            
            os.makedirs(self.sprite_output_folder, exist_ok=True)
            for file in os.listdir(self.sprite_output_folder): os.unlink(os.path.join(self.sprite_output_folder, file))
            
            handler = SpriteSheetHandler(self.image_path, remove_first_row=True, remove_first_col=False)
            self.sprites, _, _ = handler.split_sprites(size, size)
            self.sprites = self.sprites[:sprite_number]
            for idx, sprite in enumerate(self.sprites):
                bbox = sprite.getbbox()
                if bbox:
                    sprite = sprite.crop(bbox)
                sprite.save(os.path.join(self.sprite_output_folder, f"sprite_{idx + 1}.png"))
            
            messagebox.showinfo("Success", f"{len(self.sprites)} sprites saved in:\n{self.sprite_output_folder}")
            self.show_json_upload_view()
        except ValueError: messagebox.showerror("Error", "Please enter valid numeric values")
        except Exception as e: messagebox.showerror("Error", f"Processing error: {str(e)}")

    def show_json_upload_view(self):
        if self.update_breadcrumbs:
            if self.start_directly_at_json_upload:
                path = self.base_path + [("JSON Upload", self.show_json_upload_view)]
            else:
                path = self.base_path + [
                    ("Process Spritesheet", self.show_process_sheet_view),
                    ("JSON Upload", self.show_json_upload_view)
                ]
            self.update_breadcrumbs(path)
        self.clear_frame()
        json_frame = Frame(self.main_frame); json_frame.pack(pady=20, fill='both', expand=True)
        button_frame = Frame(json_frame); button_frame.pack(fill='x', pady=10)
        Button(button_frame, text="Main Menu", command=self.return_to_main).pack(side='left', padx=5)
        if not self.start_directly_at_json_upload:
            Button(button_frame, text="Back", command=self.show_process_sheet_view).pack(side='left', padx=5)
        Button(button_frame, text="Select Optimized Animation JSON", command=self._load_json_from_dialog).pack(side='left', padx=5)
        self.show_generated_sprites()

    def show_generated_sprites(self):
        if not self.sprite_output_folder or not os.path.exists(self.sprite_output_folder): return
        try:
            sprite_files = sorted([f for f in os.listdir(self.sprite_output_folder) if f.lower().endswith('.png')], key=lambda x: int(x.split('_')[-1].split('.')[0]))
        except ValueError:
            sprite_files = sorted([f for f in os.listdir(self.sprite_output_folder) if f.lower().endswith('.png')])
        
        sprite_display_frame = Frame(self.main_frame); sprite_display_frame.pack(fill='both', expand=True, pady=10)
        num_columns = getattr(self, 'saved_width', 10)
        row, col = 0, 0
        for sprite_file in sprite_files:
            sprite_path = os.path.join(self.sprite_output_folder, sprite_file)
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
            self._load_and_preview_single_json(file_path)

    def _load_and_preview_single_json(self, file_path):
        try:
            with open(file_path, 'r') as f:
                json_data = json.load(f)
            
            json_dir = os.path.dirname(file_path)
            anim_name = os.path.basename(file_path).replace("-AnimData.json", "")
            sprite_folder = os.path.join(json_dir, anim_name)

            if not os.path.exists(sprite_folder):
                messagebox.showerror("Error", f"Sprite folder for this animation not found at:\n{sprite_folder}")
                return

            self.clear_frame()
            self.animation_frame = Frame(self.main_frame)
            self.animation_frame.pack(fill='both', expand=True)
            
            back_command = self.show_json_upload_view
            Button(self.animation_frame, text="Back", command=back_command).pack(pady=10)
            
            Label(self.animation_frame, text=f"Preview: {anim_name}", font=('Arial', 16)).pack(pady=10)
            
            base_shadow = self._load_base_shadow()
            sprite_map = isometric_renderer.load_sprites_from_json(json_data, sprite_folder)
            preview_data = isometric_renderer.generate_isometric_preview_data(json_data, sprite_map, base_shadow, self.is_2x_preview)

            anim_panel = Frame(self.animation_frame)
            anim_panel.pack(pady=10)
            
            anim_label = Label(anim_panel)
            anim_label.pack()
            
            text_label = Label(anim_panel, text="Render Offset: [N/A]", font=('Arial', 10), justify="left")
            text_label.pack(pady=(5,0))
            
            player = AnimationPlayer(self.parent_frame, anim_label, text_label)
            player.set_animation(**preview_data)
            player.play()
            self.players.append({'player': player})

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load or process JSON file: {e}")

    def _on_mousewheel(self, event):
        if self.canvas:
            if event.num == 4:
                self.canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.canvas.yview_scroll(1, "units")
            else:
                self.canvas.yview_scroll(-1 * (event.delta // 120), "units")

    def _bind_mousewheel_recursively(self, widget):
        widget.bind("<MouseWheel>", self._on_mousewheel)
        widget.bind("<Button-4>", self._on_mousewheel)
        widget.bind("<Button-5>", self._on_mousewheel)
        for child in widget.winfo_children():
            self._bind_mousewheel_recursively(child)

    def show_all_animations_preview(self):
        if self.update_breadcrumbs and self.show_navigation:
            path = self.base_path + [("All Animations Preview", self.show_all_animations_preview)]
            self.update_breadcrumbs(path)
        self.clear_frame()

        self.animation_frame = Frame(self.main_frame)
        self.animation_frame.pack(fill='both', expand=True)

        self.canvas = Canvas(self.animation_frame)
        scrollbar = Scrollbar(self.animation_frame, orient="vertical", command=self.canvas.yview)
        scroll_frame = Frame(self.canvas)
        scroll_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", self._on_mousewheel)
        self.canvas.bind("<Button-5>", self._on_mousewheel)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        if self.show_navigation:
            top_bar = Frame(scroll_frame)
            top_bar.pack(fill='x', pady=10, padx=10)
            Button(top_bar, text="Back", command=self.return_to_main).pack(side='left')
        
        Label(scroll_frame, text="All Animations Preview", font=('Arial', 16)).pack(pady=10)

        if self.anim_data_subfolder:
            optimized_folder = os.path.join(self.folder, self.anim_data_subfolder)
        else:
            optimized_folder = self.folder
            
        if not os.path.exists(optimized_folder):
            messagebox.showerror("Error", f"Animation data folder not found at:\n{optimized_folder}")
            self.return_to_main()
            return

        try:
            json_files = sorted([f for f in os.listdir(optimized_folder) if f.lower().endswith('-animdata.json')])
            if not json_files:
                Label(scroll_frame, text="No optimized animations found.").pack()
                return

            grid_container = Frame(scroll_frame)
            grid_container.pack(pady=10, padx=10)
            
            row, col = 0, 0
            max_cols = 5
            
            base_shadow = self._load_base_shadow()

            for json_file in json_files:
                file_path = os.path.join(optimized_folder, json_file)
                anim_name = os.path.basename(file_path).replace("-AnimData.json", "")
                
                with open(file_path, 'r') as f:
                    json_data = json.load(f)
                
                sprite_folder = os.path.join(optimized_folder, anim_name)
                if not os.path.exists(sprite_folder):
                    print(f"Warning: Sprite folder not found for {anim_name}, skipping.")
                    continue

                group_frame = Frame(grid_container, bd=2, relief="groove")
                group_frame.grid(row=row, column=col, padx=10, pady=10, sticky="n")
                
                Label(group_frame, text=anim_name, font=('Arial', 12, 'bold')).pack(pady=5)
                
                sprite_map = isometric_renderer.load_sprites_from_json(json_data, sprite_folder)
                preview_data = isometric_renderer.generate_isometric_preview_data(json_data, sprite_map, base_shadow, self.is_2x_preview)

                if preview_data["frames"]:
                    anim_panel = Frame(group_frame)
                    anim_panel.pack(pady=5)
                    anim_label = Label(anim_panel)
                    anim_label.pack()
                    text_label = Label(anim_panel, text="Render Offset: [N/A]", font=('Arial', 10), justify="left")
                    text_label.pack(pady=(5,0))
                    
                    player = AnimationPlayer(self.parent_frame, anim_label, text_label)
                    player.set_animation(**preview_data)
                    player.play()
                    
                    control_frame = Frame(group_frame)
                    control_frame.pack(pady=(5, 5))

                    frame_count = len(preview_data.get("frames", []))
                    counter_label = Label(control_frame, text=f"1 / {frame_count}", width=8)
                    
                    play_pause_button = Button(control_frame, text="Pause")

                    prev_button = Button(control_frame, text="<", command=lambda p=player, lbl=counter_label, btn=play_pause_button: self._prev_frame(p, lbl, btn))
                    prev_button.pack(side='left')

                    play_pause_button.config(command=lambda p=player, btn=play_pause_button: self._toggle_play_pause(p, btn))
                    play_pause_button.pack(side='left')

                    next_button = Button(control_frame, text=">", command=lambda p=player, lbl=counter_label, btn=play_pause_button: self._next_frame(p, lbl, btn))
                    next_button.pack(side='left')
                    
                    counter_label.pack(side='left', padx=5)

                    self.players.append({
                        'player': player,
                        'counter_label': counter_label
                    })
                else:
                    Label(group_frame, text="No frames to display.", fg="red").pack(pady=10)

                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1

        except Exception as e:
            messagebox.showerror("Error", f"Failed to read animations: {e}")

        self._bind_mousewheel_recursively(scroll_frame)
        self._start_frame_counter_updater()

    def _toggle_play_pause(self, player, button):
        if player.is_playing:
            player.pause()
            button.config(text="Play")
        else:
            player.play()
            button.config(text="Pause")

    def _next_frame(self, player, label, play_pause_button):
        if player.is_playing:
            self._toggle_play_pause(player, play_pause_button)
        
        if not player.frames:
            return
        
        new_index = (player.current_frame_index + 1) % len(player.frames)
        player.go_to_frame(new_index)
        label.config(text=f"{player.current_frame_index + 1} / {len(player.frames)}")

    def _prev_frame(self, player, label, play_pause_button):
        if player.is_playing:
            self._toggle_play_pause(player, play_pause_button)

        if not player.frames:
            return
            
        new_index = (player.current_frame_index - 1 + len(player.frames)) % len(player.frames)
        player.go_to_frame(new_index)
        label.config(text=f"{player.current_frame_index + 1} / {len(player.frames)}")

    def _start_frame_counter_updater(self):
        if not hasattr(self, 'main_frame') or not self.main_frame.winfo_exists():
            return

        for context in self.players:
            player = context['player']
            label = context['counter_label']
            
            if player.frames and player.is_playing:
                label.config(text=f"{player.current_frame_index + 1} / {len(player.frames)}")

        self.frame_updater_after_id = self.parent_frame.after(100, self._start_frame_counter_updater)

    def _load_base_shadow(self):
        try:
            path = os.path.join(self.folder, "Animations", "sprite_base.png")
            if not os.path.exists(path):
                 path = os.path.join(self.folder, "sprite_base.png")
            
            if os.path.exists(path):
                return Image.open(path).convert('RGBA')
        except Exception as e:
            print(f"Could not load sprite_base.png: {e}")
        
        if self.is_2x_preview:
            shadow = Image.new('RGBA', (64, 32), (0,0,0,0))
            draw = ImageDraw.Draw(shadow)
            draw.ellipse([(0,0), (63,31)], fill=(0,0,0,100))
        else:
            shadow = Image.new('RGBA', (32, 16), (0,0,0,0))
            draw = ImageDraw.Draw(shadow)
            draw.ellipse([(0,0), (31,15)], fill=(0,0,0,100))
        return shadow
            
    def clear_frame(self):
        if self.frame_updater_after_id:
            self.parent_frame.after_cancel(self.frame_updater_after_id)
            self.frame_updater_after_id = None
        for context in self.players:
            context['player'].stop()
        self.players.clear()
        for widget in self.main_frame.winfo_children(): widget.destroy()