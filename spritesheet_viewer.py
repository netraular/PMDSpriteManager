from tkinter import Frame, Label, Button, Entry, Canvas, Scrollbar, messagebox
from PIL import Image, ImageTk
from sprite_sheet_handler import SpriteSheetHandler
import os

class SpritesheetViewer:
    def __init__(self, parent_frame, folder, return_to_main_callback):
        self.parent_frame = parent_frame
        self.folder = folder
        self.return_to_main = return_to_main_callback
        self.sprites = []
        self.image_path = None
        self.current_frame = parent_frame
        
        # Values from input fields
        self.sprites_width = None
        self.sprites_height = None
        
        # UI elements
        self.control_frame = None
        self.input_frame = None
        self.result_frame = None
        self.canvas = None
        self.scrollbar = None
        
        # Additional buttons
        self.save_button = None
        self.repeat_button = None
        
        self.initialize_ui()
        
    def initialize_ui(self):
        """Initialize all UI components"""
        self.create_control_frame()
        self.show_input_view()
    
    def create_control_frame(self):
        """Create the top control frame"""
        self.control_frame = Frame(self.parent_frame)
        self.control_frame.pack(fill='x', padx=10, pady=5)
        
        # Main menu button (always visible)
        Button(self.control_frame, text="Main Menu", 
             command=self.return_to_main).pack(side='left')

    def show_input_view(self):
        """Show the initial view with the form"""
        # Clear previous frames
        if self.input_frame:
            self.input_frame.destroy()
        if self.result_frame:
            self.result_frame.destroy()
        
        # Hide additional buttons
        if self.save_button:
            self.save_button.pack_forget()
        if self.repeat_button:
            self.repeat_button.pack_forget()
            
        self.input_frame = Frame(self.parent_frame)
        self.input_frame.pack(pady=20)
        
        try:
            # Load and display image
            self.image_path = self.select_image()
            img = Image.open(self.image_path)
            img.thumbnail((600, 400))
            self.img_tk = ImageTk.PhotoImage(img)
            Label(self.input_frame, image=self.img_tk).pack(pady=10)
            
            # Form
            form_frame = Frame(self.input_frame)
            form_frame.pack(pady=10)
            
            Label(form_frame, text="Sprites width:").grid(row=0, column=0)
            self.width_entry = Entry(form_frame)
            self.width_entry.grid(row=0, column=1, padx=5)
            
            Label(form_frame, text="Sprites height:").grid(row=1, column=0)
            self.height_entry = Entry(form_frame)
            self.height_entry.grid(row=1, column=1, padx=5)
            
            Button(form_frame, text="Process", 
                 command=self.process_spritesheet).grid(row=2, columnspan=2, pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Error: {str(e)}")
            self.return_to_main()

    def _on_mousewheel(self, event):
        if self.canvas:
            if event.num == 4:
                self.canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.canvas.yview_scroll(1, "units")
            else:
                self.canvas.yview_scroll(-1 * (event.delta // 120), "units")

    def show_result_view(self):
        """Show the result view with the sprites"""
        # Clear input frame
        self.input_frame.destroy()
        
        # Result frame
        self.result_frame = Frame(self.parent_frame)
        self.result_frame.pack(fill='both', expand=True)
        
        # Show additional buttons
        self.save_button = Button(self.control_frame, text="Save Sprites", 
                                   command=self.save_sprites)
        self.save_button.pack(side='left', padx=5)
        
        self.repeat_button = Button(self.control_frame, text="Repeat", 
                                   command=self.show_input_view)
        self.repeat_button.pack(side='left', padx=5)
        
        # Show sprites with scroll
        self.canvas = Canvas(self.result_frame)
        self.scrollbar = Scrollbar(self.result_frame, orient="vertical", command=self.canvas.yview)
        scroll_frame = Frame(self.canvas)
        
        scroll_frame.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")
        ))
        
        self.canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", self._on_mousewheel)
        self.canvas.bind("<Button-5>", self._on_mousewheel)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Create sprite grid
        for i, sprite in enumerate(self.sprites):
            row = i // self.sprites_width
            col = i % self.sprites_width
            
            bg = Image.new('RGBA', sprite.size, 'lightgray')
            composite = Image.alpha_composite(bg, sprite)
            composite.thumbnail((100, 100))
            
            img = ImageTk.PhotoImage(composite)
            lbl = Label(scroll_frame, image=img)
            lbl.image = img
            lbl.grid(row=row, column=col, padx=2, pady=2)

        def bind_recursively(widget):
            widget.bind("<MouseWheel>", self._on_mousewheel)
            widget.bind("<Button-4>", self._on_mousewheel)
            widget.bind("<Button-5>", self._on_mousewheel)
            for child in widget.winfo_children():
                bind_recursively(child)
        
        bind_recursively(scroll_frame)

    def process_spritesheet(self):
        """Process the spritesheet and show the results"""
        try:
            # Save input field values before destroying widgets
            self.sprites_width = int(self.width_entry.get())
            self.sprites_height = int(self.height_entry.get())
            
            # Process the spritesheet
            handler = SpriteSheetHandler(self.image_path, remove_first_row=True, remove_first_col=False)
            self.sprites, width, height = handler.split_sprites(self.sprites_width, self.sprites_height)
            
            # Show the result view
            self.show_result_view()
            
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numeric values")
        except Exception as e:
            messagebox.showerror("Error", f"Error processing: {str(e)}")

    def save_sprites(self):
        """Save the cropped sprites"""
        if not self.sprites:
            messagebox.showwarning("Warning", "No sprites to save")
            return
            
        folder_name = os.path.basename(self.folder) + "Edited"
        edited_folder = os.path.join(self.folder, folder_name)
        os.makedirs(edited_folder, exist_ok=True)
        
        for idx, sprite in enumerate(self.sprites):
            sprite.save(os.path.join(edited_folder, f"sprite_{idx + 1}.png"))
        
        messagebox.showinfo("Success", f"Sprites saved in:\n{edited_folder}")

    def select_image(self):
        """Select the first PNG image in the folder"""
        png_files = [f for f in os.listdir(self.folder) if f.lower().endswith('.png')]
        if not png_files:
            raise FileNotFoundError("No PNG files found in the folder")
        return os.path.join(self.folder, png_files[0])