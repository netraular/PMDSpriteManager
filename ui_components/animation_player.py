# ui_components/animation_player.py

from tkinter import Label
from PIL import Image, ImageTk

class AnimationPlayer:
    def __init__(self, parent_widget, image_label, text_label=None):
        self.parent_widget = parent_widget
        self.image_label = image_label
        self.text_label = text_label
        
        self.frames = []
        self.durations = []
        self.text_data = []
        self.thumbnail_size = (200, 200)
        
        self.after_id = None
        self.is_playing = False
        self.current_frame_index = 0

    def set_animation(self, frames, durations, text_data=None, thumbnail_size=(200, 200)):
        was_playing = self.is_playing
        if self.after_id:
            self.parent_widget.after_cancel(self.after_id)
            self.after_id = None

        self.frames = frames
        self.durations = durations
        self.text_data = text_data or []
        self.thumbnail_size = thumbnail_size
        self.current_frame_index = 0
        
        if not self.frames:
            self.image_label.config(image='', text="[No Frames]")
            if self.text_label:
                self.text_label.config(text="")
            self.is_playing = False
        else:
            self._render_current_frame()
            if was_playing:
                self.play()

    def play(self):
        if not self.frames or self.is_playing:
            return
        self.is_playing = True
        if self.after_id:
            self.parent_widget.after_cancel(self.after_id)
        
        self._update_frame()

    def pause(self):
        self.is_playing = False
        if self.after_id:
            self.parent_widget.after_cancel(self.after_id)
            self.after_id = None

    def stop(self):
        self.pause()
        self.current_frame_index = 0
        if self.frames:
            self._render_current_frame()

    def go_to_frame(self, frame_index):
        if not self.frames:
            return
        self.current_frame_index = frame_index % len(self.frames)
        self._render_current_frame()
        
        if self.is_playing:
            if self.after_id:
                self.parent_widget.after_cancel(self.after_id)
            self._update_frame()

    def _render_current_frame(self):
        if not self.image_label.winfo_exists() or not self.frames:
            self.pause()
            return

        frame = self.frames[self.current_frame_index]
        frame_copy = frame.copy()
        frame_copy.thumbnail(self.thumbnail_size)
        
        img = ImageTk.PhotoImage(frame_copy)
        self.image_label.config(image=img)
        self.image_label.image = img
        
        if self.text_label and self.text_data:
            if self.current_frame_index < len(self.text_data):
                self.text_label.config(text=self.text_data[self.current_frame_index])
            else:
                self.text_label.config(text="")

    def _update_frame(self):
        if not self.is_playing or not self.image_label.winfo_exists() or not self.frames:
            self.pause()
            return

        self._render_current_frame()
        
        duration_idx = self.current_frame_index % len(self.durations)
        delay = self.durations[duration_idx] * 33
        
        self.current_frame_index = (self.current_frame_index + 1) % len(self.frames)
        
        self.after_id = self.parent_widget.after(delay, self._update_frame)