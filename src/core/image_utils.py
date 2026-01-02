# ui_components/image_utils.py
import os
from PIL import Image, ImageDraw, ImageOps

def get_image_bottom_center(image):
    """Calculates the bottom-center of the visible pixels in an image."""
    bbox = image.getbbox()
    return ((bbox[0] + bbox[2]) / 2, bbox[3]) if bbox else None

def get_image_center(image):
    """Calculates the geometric center of the visible pixels in an image."""
    bbox = image.getbbox()
    return ((bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2) if bbox else None

def find_white_pixel_anchor(image):
    """Finds the first white pixel (255, 255, 255, 255) as an anchor."""
    if image.mode != 'RGBA':
        image = image.convert('RGBA')
    
    width, height = image.size
    pixels = image.load()
    white_pixel_color = (255, 255, 255, 255)
    
    for y in range(height):
        for x in range(width):
            if pixels[x, y] == white_pixel_color:
                return (x, y)
    
    return get_image_center(image)

def tint_image(image, color):
    """Tints an image with a specified color."""
    if image.mode != 'RGBA':
        image = image.convert('RGBA')
    
    tint_layer = Image.new('RGBA', image.size, color)
    return Image.composite(tint_layer, image, image)

def load_sprite(sprite_folder, sprite_id, is_mirrored):
    """Loads a single sprite by ID from a folder, with optional mirroring."""
    if not sprite_id or sprite_id <= 0: return None
    try:
        path = os.path.join(sprite_folder, f"sprite_{sprite_id}.png")
        sprite = Image.open(path).convert('RGBA')
        return ImageOps.mirror(sprite) if is_mirrored else sprite
    except FileNotFoundError:
        return None

def load_base_shadow_sprite(project_folder, anim_folder=None, is_2x=False):
    """
    Loads the base shadow sprite, searching in multiple common locations.
    If not found, generates a default placeholder.
    """
    search_paths = []
    if project_folder:
        search_paths.append(os.path.join(project_folder, "Sprites", "sprite_shadow.png"))
        search_paths.append(os.path.join(project_folder, "Animations", "sprite_shadow.png"))
        search_paths.append(os.path.join(project_folder, "sprite_shadow.png"))
    if anim_folder:
        search_paths.append(os.path.join(anim_folder, "sprite_shadow.png"))
        
    for path in search_paths:
        if os.path.exists(path):
            try:
                return Image.open(path).convert('RGBA')
            except Exception as e:
                print(f"Warning: Could not load sprite_shadow.png from {path}: {e}")

    # If not found, create a default one
    if is_2x:
        shadow = Image.new('RGBA', (64, 32), (0,0,0,0))
        draw = ImageDraw.Draw(shadow)
        draw.ellipse([(0,0), (63,31)], fill=(0,0,0,100))
    else:
        shadow = Image.new('RGBA', (32, 16), (0,0,0,0))
        draw = ImageDraw.Draw(shadow)
        draw.ellipse([(0,0), (31,15)], fill=(0,0,0,100))
    return shadow