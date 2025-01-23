import os
from tkinter import Frame, Label, Canvas, Scrollbar
from PIL import Image, ImageTk
import xml.etree.ElementTree as ET
from sprite_sheet_handler import SpriteSheetHandler

class AnimationViewer:
    def __init__(self, parent_frame, anim_folder):
        self.parent_frame = parent_frame
        self.anim_folder = anim_folder
        self.sprite_folder = os.path.join(anim_folder, "sprite")
        self.anim_data = self.load_anim_data()
        self.current_anim_index = 0
        self.after_ids = []
        
        self.setup_interface()
        self.show_animation()

    def setup_interface(self):
        # Main container with scroll
        self.main_canvas = Canvas(self.parent_frame)
        self.scrollbar = Scrollbar(self.parent_frame, orient="vertical", command=self.main_canvas.yview)
        self.scroll_frame = Frame(self.main_canvas)
        
        self.scroll_frame.bind("<Configure>", lambda e: self.main_canvas.configure(
            scrollregion=self.main_canvas.bbox("all")
        ))
        
        self.main_canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.main_canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.main_canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

    def load_anim_data(self):
        anim_data_path = os.path.join(self.sprite_folder, "AnimData.xml")
        if not os.path.exists(anim_data_path):
            raise FileNotFoundError(f"XML file not found in: {self.sprite_folder}")

        tree = ET.parse(anim_data_path)
        return self.process_xml(tree)

    def process_xml(self, tree):
        animations = []
        for anim in tree.getroot().find("Anims"):
            anim_data = {
                "name": anim.find("Name").text,
                "frame_width": int(anim.find("FrameWidth").text),
                "frame_height": int(anim.find("FrameHeight").text),
                "durations": [int(d.text) for d in anim.findall("Durations/Duration")],
                "image_path": os.path.join(self.sprite_folder, f"{anim.find('Name').text}-Anim.png")
            }
            
            with Image.open(anim_data["image_path"]) as img:
                anim_data["total_groups"] = img.height // anim_data["frame_height"]
                anim_data["frames_per_group"] = img.width // anim_data["frame_width"]
            
            animations.append(anim_data)
        return animations

    def show_animation(self):
        # Clear previous callbacks
        self.clear_animations()
        
        # Clear previous frame
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        
        anim = self.anim_data[self.current_anim_index]
        handler = SpriteSheetHandler(anim["image_path"])
        all_frames = handler.split_animation_frames(anim["frame_width"], anim["frame_height"])
        
        # Create a group for each row of frames
        total_groups = anim["total_groups"]
        frames_per_group = anim["frames_per_group"]
        
        main_title = Label(self.scroll_frame, 
                          text=f"Animation: {anim['name']}",
                          font=('Arial', 14, 'bold'))
        main_title.pack(pady=10)
        
        for group_idx in range(total_groups):
            group_frame = Frame(self.scroll_frame, bd=2, relief="groove")
            group_frame.pack(fill="x", padx=5, pady=5)
            
            # Group header
            Label(group_frame, 
                 text=f"Group {group_idx + 1}", 
                 font=('Arial', 12, 'bold')).pack(anchor="w")
            
            # Animation and frames container
            content_frame = Frame(group_frame)
            content_frame.pack(fill="x")
            
            # Animation panel
            anim_panel = Frame(content_frame)
            anim_panel.pack(side="left", padx=10)
            
            # Frames panel
            frames_panel = Frame(content_frame)
            frames_panel.pack(side="right", fill="x", expand=True)
            
            # Get frames for the current group
            start = group_idx * frames_per_group
            end = start + frames_per_group
            group_frames = all_frames[start:end]
            
            # Adjust durations
            durations = anim["durations"]
            if len(durations) < len(group_frames):
                durations = durations * (len(group_frames) // len(durations) + 1)
            durations = durations[:len(group_frames)]
            
            # Show animation
            anim_label = Label(anim_panel)
            anim_label.pack()
            self.start_group_animation(anim_label, group_frames, durations)
            
            # Show frames
            for idx, frame in enumerate(group_frames):
                frame.thumbnail((80, 80))
                img = ImageTk.PhotoImage(frame)
                lbl = Label(frames_panel, image=img)
                lbl.image = img
                lbl.grid(row=0, column=idx, padx=2)
                Label(frames_panel, 
                     text=f"Frame {idx+1}\n({durations[idx]} frames)", 
                     font=('Arial', 7)).grid(row=1, column=idx)

    def clear_animations(self):
        """Cancel all pending animations"""
        for aid in self.after_ids:
            self.parent_frame.after_cancel(aid)
        self.after_ids.clear()

    def start_group_animation(self, label, frames, durations):
        current_frame = [0]
        
        def update():
            if current_frame[0] >= len(frames):
                current_frame[0] = 0
                
            frame = frames[current_frame[0]]
            frame.thumbnail((200, 200))
            img = ImageTk.PhotoImage(frame)
            label.config(image=img)
            label.image = img
            
            delay = durations[current_frame[0]] * 33  # 33ms per frame (≈30fps)
            current_frame[0] += 1
            self.after_ids.append(self.parent_frame.after(delay, update))
        
        update()

    def prev_animation(self):
        self.current_anim_index = (self.current_anim_index - 1) % len(self.anim_data)
        self.show_animation()

    def next_animation(self):
        self.current_anim_index = (self.current_anim_index + 1) % len(self.anim_data)
        self.show_animation()