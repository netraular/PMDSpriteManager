# animation_viewer.py

import os
import json
from tkinter import Frame, Label, Canvas, Scrollbar, messagebox, Toplevel, Button, OptionMenu, StringVar, BooleanVar
from PIL import Image, ImageTk, ImageOps
import math
from animation_group_ui import AnimationGroupUI
from animation_data_handler import AnimationDataHandler

class AnimationViewer:
    def __init__(self, parent_frame, anim_folder):
        self.parent_frame = parent_frame
        self.anim_folder = anim_folder
        self.sprite_folder = os.path.join(anim_folder, "Sprites")
        
        self.data_handler = AnimationDataHandler(self.anim_folder)
        self.anim_data = self.data_handler.anim_data
        
        self.current_anim_index = 0
        self.group_ui_instances = []
        
        self.selected_anim_var = StringVar()

        # Visibility control variables
        self.show_original_var = BooleanVar(value=True)
        self.show_editor_var = BooleanVar(value=True)
        self.show_previews_var = BooleanVar(value=True)

        self.setup_interface()
        self.show_animation()

    def _on_mousewheel(self, event):
        if event.num == 4:
            self.main_canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.main_canvas.yview_scroll(1, "units")
        else:
            self.main_canvas.yview_scroll(-1 * (event.delta // 120), "units")

    def _bind_mousewheel_recursively(self, widget):
        widget.bind("<MouseWheel>", self._on_mousewheel)
        widget.bind("<Button-4>", self._on_mousewheel)
        widget.bind("<Button-5>", self._on_mousewheel)
        for child in widget.winfo_children():
            self._bind_mousewheel_recursively(child)

    def setup_interface(self):
        self.main_canvas = Canvas(self.parent_frame)
        self.scrollbar = Scrollbar(self.parent_frame, orient="vertical", command=self.main_canvas.yview)
        self.scroll_frame = Frame(self.main_canvas)
        
        self.scroll_frame.bind("<Configure>", lambda e: self.main_canvas.configure(
            scrollregion=self.main_canvas.bbox("all")
        ))
        
        self.main_canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.main_canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.main_canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.main_canvas.bind("<Button-4>", self._on_mousewheel)
        self.main_canvas.bind("<Button-5>", self._on_mousewheel)

        self.main_canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

    def on_animation_selected(self, selected_name):
        new_index = -1
        for i, anim in enumerate(self.anim_data):
            if anim['name'] == selected_name:
                new_index = i
                break
        
        if new_index != -1 and new_index != self.current_anim_index:
            self.current_anim_index = new_index
            self.show_animation()

    def show_animation(self):
        self.clear_animations()
        for widget in self.scroll_frame.winfo_children(): widget.destroy()
        if not self.anim_data:
             Label(self.scroll_frame, text="No animations found or loaded.", font=('Arial', 14, 'bold')).pack(pady=20); return
        
        anim = self.anim_data[self.current_anim_index]
        
        all_frames, all_offsets_frames, all_shadow_frames, all_metadata = self.data_handler._load_animation_assets(anim)
        
        ui_compatible_json_data = self.load_and_convert_optimized_json(anim["name"])
        run_ai_automatically = ui_compatible_json_data is None

        header_frame = Frame(self.scroll_frame)
        header_frame.pack(fill='x', pady=10)
        
        Label(header_frame, text="Animation:", font=('Arial', 14, 'bold')).pack(side='left', padx=(10, 5))
        anim_names = [a['name'] for a in self.anim_data]
        self.selected_anim_var.set(anim['name'])
        anim_dropdown = OptionMenu(header_frame, self.selected_anim_var, *anim_names, command=self.on_animation_selected)
        anim_dropdown.config(font=('Arial', 12))
        anim_dropdown.pack(side='left', padx=5)

        count_text = f"({self.current_anim_index + 1} of {len(self.anim_data)})"
        Label(header_frame, text=count_text, font=('Arial', 12, 'italic')).pack(side='left', padx=10)

        Button(header_frame, text="View Options", command=self.open_view_options).pack(side='left', padx=10)

        for group_idx in range(anim["total_groups"]):
            start, end = group_idx * anim["frames_per_group"], (group_idx + 1) * anim["frames_per_group"]
            
            group_ui = AnimationGroupUI(
                parent=self.scroll_frame,
                viewer=self,
                group_idx=group_idx,
                anim_data=anim,
                group_frames=all_frames[start:end],
                group_offsets_frames=all_offsets_frames[start:end] if all_offsets_frames else [],
                group_shadow_frames=all_shadow_frames[start:end] if all_shadow_frames else [],
                group_metadata=all_metadata[start:end],
                sprite_folder=self.sprite_folder,
                anim_folder=self.anim_folder,
                json_group_data=ui_compatible_json_data["sprites"].get(str(group_idx + 1)) if ui_compatible_json_data else None,
                ai_callback=self.identify_group_sprites
            )
            self.group_ui_instances.append(group_ui)
            group_ui.set_section_visibility(
                self.show_original_var.get(),
                self.show_editor_var.get(),
                self.show_previews_var.get()
            )

            if run_ai_automatically:
                self.identify_group_sprites(group_ui)
        
        self._bind_mousewheel_recursively(self.scroll_frame)

    def open_view_options(self):
        top = Toplevel(self.parent_frame)
        top.title("View Options")
        top.transient(self.parent_frame)
        top.grab_set()

        main_frame = Frame(top, padx=10, pady=10)
        main_frame.pack()

        Label(main_frame, text="Toggle section visibility:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(0, 5))

        from tkinter import Checkbutton
        Checkbutton(main_frame, text="Show Original Animations", variable=self.show_original_var, command=self._update_all_group_visibilities).pack(anchor='w')
        Checkbutton(main_frame, text="Show Sprite Editor", variable=self.show_editor_var, command=self._update_all_group_visibilities).pack(anchor='w')
        Checkbutton(main_frame, text="Show Generated Previews", variable=self.show_previews_var, command=self._update_all_group_visibilities).pack(anchor='w')

        Button(main_frame, text="Close", command=top.destroy).pack(pady=10)

    def _update_all_group_visibilities(self):
        original_visible = self.show_original_var.get()
        editor_visible = self.show_editor_var.get()
        previews_visible = self.show_previews_var.get()

        for group_ui in self.group_ui_instances:
            group_ui.set_section_visibility(original_visible, editor_visible, previews_visible)

    def identify_group_sprites(self, group_ui_instance):
        try:
            if not os.path.exists(self.sprite_folder): return
            from sprite_matcher import SpriteMatcher
            matcher = SpriteMatcher(self.sprite_folder)
            match_data = matcher.match_group(group_ui_instance.group_frames)
            group_ui_instance.set_sprite_values(match_data["frame_matches"], match_data["per_frame_mirror"])
            group_ui_instance.refresh_all_previews()
        except Exception as e:
            messagebox.showerror("Error", f"Error during identification: {str(e)}")

    def clear_animations(self):
        for instance in self.group_ui_instances:
            instance.cleanup()
        self.group_ui_instances.clear()

    def view_sprites(self):
        if not os.path.exists(self.sprite_folder): messagebox.showwarning("Warning", "No 'Sprites' folder found"); return
        sprite_files = sorted([f for f in os.listdir(self.sprite_folder) if f.lower().endswith('.png')], key=lambda x: int(x.split('_')[-1].split('.')[0]))
        if not sprite_files: messagebox.showwarning("Warning", "No sprites found in the 'Sprites' folder"); return
        num_sprites = len(sprite_files); grid_size = math.ceil(math.sqrt(num_sprites))
        sprite_window = Toplevel(self.parent_frame); sprite_window.title(f"Sprites Gallery ({num_sprites} sprites)")
        canvas = Canvas(sprite_window); scrollbar = Scrollbar(sprite_window, orient="vertical", command=canvas.yview)
        scroll_frame = Frame(canvas); scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw"); canvas.configure(yscrollcommand=scrollbar.set)
        
        def _on_sprite_mousewheel(event):
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")
            else:
                canvas.yview_scroll(-1 * (event.delta // 120), "units")

        canvas.bind("<MouseWheel>", _on_sprite_mousewheel)
        canvas.bind("<Button-4>", _on_sprite_mousewheel)
        canvas.bind("<Button-5>", _on_sprite_mousewheel)

        canvas.pack(side="left", fill="both", expand=True); scrollbar.pack(side="right", fill="y")
        for idx, file in enumerate(sprite_files):
            try:
                sprite_number = int(file.split('_')[-1].split('.')[0])
                row, col = (sprite_number - 1) // grid_size, (sprite_number - 1) % grid_size
                img = Image.open(os.path.join(self.sprite_folder, file)); img.thumbnail((100, 100)); photo = ImageTk.PhotoImage(img)
                frame = Frame(scroll_frame); frame.grid(row=row, column=col, padx=5, pady=5)
                Label(frame, image=photo).pack(); Label(frame, text=file, font=('Arial', 8)).pack(); frame.photo = photo
            except Exception as e: print(f"Error loading {file}: {str(e)}")

        def bind_recursively(widget):
            widget.bind("<MouseWheel>", _on_sprite_mousewheel)
            widget.bind("<Button-4>", _on_sprite_mousewheel)
            widget.bind("<Button-5>", _on_sprite_mousewheel)
            for child in widget.winfo_children():
                bind_recursively(child)
        
        bind_recursively(scroll_frame)

    def _get_data_from_current_view(self):
        try:
            anim = self.anim_data[self.current_anim_index]
            grouped_sprites = {}
            group_names = []
            for i, instance in enumerate(self.group_ui_instances):
                group_data = instance.get_data()
                group_name = group_data["name"]
                if not group_name: messagebox.showerror("Error", "All group names must be filled."); return None
                if group_name in group_names: messagebox.showerror("Error", "Duplicate group names are not allowed."); return None
                group_names.append(group_name)
                grouped_sprites[str(i + 1)] = group_data
            
            return {"index": self.current_anim_index, "name": anim["name"], "framewidth": anim["frame_width"], "frameheight": anim["frame_height"], "sprites": grouped_sprites, "durations": anim["durations"]}
        except Exception as e: messagebox.showerror("Error", f"Failed to gather data from view: {str(e)}"); return None

    def generate_json(self):
        json_data = self._get_data_from_current_view()
        if json_data:
            output_path, error = self.data_handler.export_optimized_animation(json_data)
            if error:
                messagebox.showerror("Export Error", error)
            else:
                messagebox.showinfo("Success", f"Optimized animation saved for {json_data['name']} in:\n{os.path.dirname(output_path)}")

    def save_all_animations(self):
        saved_count, failed_count = 0, 0
        
        for index, anim in enumerate(self.anim_data):
            json_data = None
            if index == self.current_anim_index:
                json_data = self._get_data_from_current_view()
            else:
                json_data = self.data_handler.generate_animation_data(index)

            if json_data:
                _, error = self.data_handler.export_optimized_animation(json_data)
                if error:
                    print(f"Failed to export {anim['name']}: {error}")
                    failed_count += 1
                else:
                    saved_count += 1
            else:
                failed_count += 1
        
        messagebox.showinfo("Batch Export Complete", f"Process finished.\n\nTotal Animations Exported: {saved_count}\nFailed/Skipped: {failed_count}")

    def load_and_convert_optimized_json(self, anim_name):
        folder_name = "AnimationData"
        json_path = os.path.join(self.anim_folder, folder_name, f"{anim_name}-AnimData.json")
        if not os.path.exists(json_path): return None
        try:
            with open(json_path, 'r') as f: optimized_data = json.load(f)
        except Exception as e:
            print(f"Error loading optimized JSON for {anim_name}: {str(e)}"); return None
        
        ui_data = optimized_data.copy()
        ui_data['sprites'] = {}
        for group_id, group_data in optimized_data.get('sprites', {}).items():
            ui_group = {'name': group_data.get('name'), 'values': [], 'offsets': []}
            for frame in group_data.get('frames', []):
                sprite_id_str = frame.get('id', '0')
                offset = frame.get('offset', [0, 0])
                is_mirrored = "_mirrored" in sprite_id_str
                base_id = int(sprite_id_str.replace("_mirrored", "")) if sprite_id_str.replace("_mirrored", "").isdigit() else 0
                ui_group['values'].append({'id': base_id, 'mirrored': is_mirrored})
                ui_group['offsets'].append(offset)
            ui_data['sprites'][group_id] = ui_group
        return ui_data