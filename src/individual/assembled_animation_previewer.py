# individual/assembled_animation_previewer.py

import os
import json
from tkinter import Frame, Label, Button, messagebox, Canvas, Scrollbar
from PIL import Image, ImageTk, ImageDraw
from ui.animation_player import AnimationPlayer

class AssembledAnimationPreviewer:
    def __init__(self, parent_frame, folder, return_to_main_callback, update_breadcrumbs_callback=None, base_path=None):
        self.parent_frame = parent_frame
        self.project_folder = folder
        self.assembled_folder = os.path.join(folder, "AssembledAnimations")
        self.return_to_main = return_to_main_callback
        self.update_breadcrumbs = update_breadcrumbs_callback
        self.base_path = base_path if base_path is not None else []
        
        self.main_frame = Frame(self.parent_frame)
        self.main_frame.pack(fill='both', expand=True)
        
        self.players_context = []
        self.animations_list = []
        self.canvas = None
        self.frame_updater_after_id = None

        self.setup_ui()

    def setup_ui(self):
        if self.update_breadcrumbs:
            path = self.base_path + [("Assembled Preview", self.setup_ui)]
            self.update_breadcrumbs(path)
        
        self.cleanup()
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        if not os.path.exists(self.assembled_folder):
            messagebox.showerror("Error", f"The 'AssembledAnimations' folder could not be found in:\n{self.project_folder}")
            self.return_to_main()
            return
        
        self._scan_for_animations()

        # --- Top Controls ---
        top_controls = Frame(self.main_frame)
        top_controls.pack(fill='x', padx=10, pady=5)
        Button(top_controls, text="Main Menu", command=self.return_to_main).pack(side='left', padx=(0, 20))
        
        if not self.animations_list:
            Label(self.main_frame, text="No assembled animations found in the folder.", font=('Arial', 12), fg="red").pack(pady=50)
            return

        # --- Scrollable Preview Area ---
        self.canvas = Canvas(self.main_frame)
        scrollbar = Scrollbar(self.main_frame, orient="vertical", command=self.canvas.yview)
        scroll_frame = Frame(self.canvas)
        scroll_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self._bind_mousewheel_recursively(self.canvas)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self._populate_animations_grid(scroll_frame)
        self._bind_mousewheel_recursively(scroll_frame)
        self._start_frame_counter_updater()

    def _scan_for_animations(self):
        self.animations_list = sorted([
            f.replace("-AnimSheetData.json", "")
            for f in os.listdir(self.assembled_folder)
            if f.lower().endswith('-animsheetdata.json')
        ])

    def _populate_animations_grid(self, parent):
        grid_container = Frame(parent)
        grid_container.pack(pady=10, padx=10)
        
        row, col = 0, 0
        max_cols = 4

        for anim_name in self.animations_list:
            json_path = os.path.join(self.assembled_folder, f"{anim_name}-AnimSheetData.json")
            png_path = os.path.join(self.assembled_folder, f"{anim_name}-Anim.png")

            if not os.path.exists(json_path) or not os.path.exists(png_path):
                continue
            
            try:
                with open(json_path, 'r') as f: sheet_data = json.load(f)
                spritesheet_img = Image.open(png_path).convert('RGBA')

                preview_data = self._generate_isometric_frames_from_assembled(spritesheet_img, sheet_data)
                
                group_frame = Frame(grid_container, bd=2, relief="groove")
                group_frame.grid(row=row, column=col, padx=10, pady=10, sticky="n")
                
                Label(group_frame, text=anim_name, font=('Arial', 12, 'bold')).pack(pady=5)

                if preview_data["frames"]:
                    anim_panel = Frame(group_frame)
                    anim_panel.pack(pady=5)
                    anim_label = Label(anim_panel)
                    anim_label.pack()
                    text_label = Label(anim_panel, text="", font=('Arial', 9), justify="left", height=4)
                    text_label.pack(pady=(5,0))
                    
                    player = AnimationPlayer(self.parent_frame, anim_label, text_label)
                    player.set_animation(**preview_data)
                    player.play()
                    
                    control_frame = Frame(group_frame)
                    control_frame.pack(pady=(5, 5))

                    frame_count = len(preview_data.get("frames", []))
                    counter_label = Label(control_frame, text=f"1 / {frame_count}", width=8)
                    play_pause_button = Button(control_frame, text="Pause")

                    Button(control_frame, text="<", command=lambda p=player, lbl=counter_label, btn=play_pause_button: self._prev_frame(p, lbl, btn)).pack(side='left')
                    play_pause_button.config(command=lambda p=player, btn=play_pause_button: self._toggle_play_pause(p, btn))
                    play_pause_button.pack(side='left')
                    Button(control_frame, text=">", command=lambda p=player, lbl=counter_label, btn=play_pause_button: self._next_frame(p, lbl, btn)).pack(side='left')
                    counter_label.pack(side='left', padx=5)

                    self.players_context.append({'player': player, 'counter_label': counter_label})
                else:
                    Label(group_frame, text="No frames to display.", fg="red").pack(pady=10)

                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1

            except Exception as e:
                print(f"Error loading animation {anim_name}: {e}")

    def _generate_isometric_frames_from_assembled(self, spritesheet_img, sheet_data):
        consts = {'WIDTH': 32, 'HEIGHT': 16, 'WIDTH_HALF': 16, 'HEIGHT_HALF': 8}
        canvas_w, canvas_h = consts['WIDTH'] * 5, consts['HEIGHT'] * 5
        
        all_final_frames, all_text_data = [], []
        
        frame_width = sheet_data["frameWidth"]
        frame_height = sheet_data["frameHeight"]
        base_durations = sheet_data["durations"]
        
        sorted_groups = sorted(sheet_data["groups"].items(), key=lambda item: int(item[0]))
        
        for row_idx, (group_id, group_data) in enumerate(sorted_groups):
            bounding_box_anchor = group_data.get("boundingBoxAnchor")

            for col_idx, hitbox_data in enumerate(group_data.get("frames", [])):
                
                canvas = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
                world_anchor = (canvas_w // 2, canvas_h // 2)
                grid_origin = (world_anchor[0] - consts['WIDTH_HALF'], world_anchor[1] - consts['HEIGHT_HALF'] * 3)
                
                self._draw_iso_grid(canvas, grid_origin, consts)
                
                current_text = f"Group: {group_data['name']}\nFrame: {col_idx+1}"

                # Crop the character sprite cell from the spritesheet
                box = (col_idx * frame_width, row_idx * frame_height, (col_idx + 1) * frame_width, (row_idx + 1) * frame_height)
                char_sprite_cell = spritesheet_img.crop(box)
                
                # Use the boundingBoxAnchor to position the entire cell correctly
                if bounding_box_anchor:
                    paste_pos = (world_anchor[0] + bounding_box_anchor[0], world_anchor[1] + bounding_box_anchor[1])
                else:
                    # Fallback for older assembled files without the anchor
                    paste_pos = (world_anchor[0] - frame_width // 2, world_anchor[1] - frame_height // 2)

                canvas.paste(char_sprite_cell, paste_pos, char_sprite_cell)
                
                # Prepare a transparent overlay for drawing visuals (hitbox, outlines)
                overlay = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
                draw_overlay = ImageDraw.Draw(overlay)

                # Draw the grey outline for the entire animation cell
                cell_outline_color = (150, 150, 150, 255)
                draw_overlay.rectangle(
                    [paste_pos[0], paste_pos[1], paste_pos[0] + frame_width - 1, paste_pos[1] + frame_height - 1],
                    outline=cell_outline_color,
                    width=1
                )

                if hitbox_data:
                    x, y, w, h = hitbox_data['x'], hitbox_data['y'], hitbox_data['w'], hitbox_data['h']
                    
                    # Draw the semi-transparent red hitbox relative to the cell's paste position
                    red_with_alpha = (255, 0, 0, 128)
                    hitbox_rect = [paste_pos[0] + x, paste_pos[1] + y, paste_pos[0] + x + w - 1, paste_pos[1] + y + h - 1]
                    draw_overlay.rectangle(hitbox_rect, fill=red_with_alpha)
                    
                    current_text += f"\nHitbox: (w:{w}, h:{h})"
                else:
                    current_text += f"\nHitbox: (None)"

                # Composite the overlay with the drawings onto the main canvas
                canvas = Image.alpha_composite(canvas, overlay)

                # Draw world anchor crosshair on the final image
                draw = ImageDraw.Draw(canvas)
                s = 3
                draw.line((world_anchor[0]-s, world_anchor[1], world_anchor[0]+s, world_anchor[1]), fill="red", width=1)
                draw.line((world_anchor[0], world_anchor[1]-s, world_anchor[0], world_anchor[1]+s), fill="red", width=1)
                    
                all_final_frames.append(canvas)
                all_text_data.append(current_text)
                
        total_frames = len(all_final_frames)
        durations = (base_durations * (total_frames // len(base_durations) + 1))[:total_frames] if base_durations else [1] * total_frames

        return {"frames": all_final_frames, "durations": durations, "text_data": all_text_data, "thumbnail_size": (300, 300)}

    def _draw_iso_grid(self, image, origin, consts):
        draw = ImageDraw.Draw(image)
        for y in range(3):
            for x in range(3):
                # Using a simplified grid_to_screen conversion
                pos_x = origin[0] + (x - y) * consts['WIDTH_HALF']
                pos_y = origin[1] + (x + y) * consts['HEIGHT_HALF']
                points = [
                    (pos_x + consts['WIDTH_HALF'], pos_y),
                    (pos_x + consts['WIDTH'], pos_y + consts['HEIGHT_HALF']),
                    (pos_x + consts['WIDTH_HALF'], pos_y + consts['HEIGHT']),
                    (pos_x, pos_y + consts['HEIGHT_HALF'])
                ]
                draw.polygon(points, fill=(220, 220, 220), outline=(180, 180, 180))
    
    def _toggle_play_pause(self, player, button):
        if player.is_playing:
            player.pause()
            button.config(text="Play")
        else:
            player.play()
            button.config(text="Pause")

    def _next_frame(self, player, label, play_pause_button):
        if player.is_playing: self._toggle_play_pause(player, play_pause_button)
        if not player.frames: return
        new_index = (player.current_frame_index + 1) % len(player.frames)
        player.go_to_frame(new_index)
        label.config(text=f"{player.current_frame_index + 1} / {len(player.frames)}")

    def _prev_frame(self, player, label, play_pause_button):
        if player.is_playing: self._toggle_play_pause(player, play_pause_button)
        if not player.frames: return
        new_index = (player.current_frame_index - 1 + len(player.frames)) % len(player.frames)
        player.go_to_frame(new_index)
        label.config(text=f"{player.current_frame_index + 1} / {len(player.frames)}")

    def _start_frame_counter_updater(self):
        if not self.main_frame.winfo_exists(): return
        for context in self.players_context:
            player, label = context['player'], context['counter_label']
            if player.frames and player.is_playing:
                label.config(text=f"{player.current_frame_index + 1} / {len(player.frames)}")
        self.frame_updater_after_id = self.parent_frame.after(100, self._start_frame_counter_updater)

    def _on_mousewheel(self, event):
        if self.canvas:
            if event.num == 4: self.canvas.yview_scroll(-1, "units")
            elif event.num == 5: self.canvas.yview_scroll(1, "units")
            else: self.canvas.yview_scroll(-1 * (event.delta // 120), "units")

    def _bind_mousewheel_recursively(self, widget):
        widget.bind("<MouseWheel>", self._on_mousewheel)
        widget.bind("<Button-4>", self._on_mousewheel)
        widget.bind("<Button-5>", self._on_mousewheel)
        for child in widget.winfo_children():
            self._bind_mousewheel_recursively(child)

    def cleanup(self):
        if self.frame_updater_after_id:
            self.parent_frame.after_cancel(self.frame_updater_after_id)
            self.frame_updater_after_id = None
        for context in self.players_context:
            context['player'].stop()
        self.players_context.clear()