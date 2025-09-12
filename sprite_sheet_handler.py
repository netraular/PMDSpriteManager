from PIL import Image
import os

class SpriteSheetHandler:
    def __init__(self, image_path, remove_first_row=False, remove_first_col=False):
        """
        Initialize the SpriteSheetHandler with the path to the sprite sheet.
        :param image_path: Path to the sprite sheet image.
        :param remove_first_row: If True, removes the first row of pixels from each sprite.
        :param remove_first_col: If True, removes the first col of pixels from each sprite.
        """
        self.image_path = image_path
        self.image = Image.open(image_path)
        self.remove_first_row = remove_first_row
        self.remove_first_col = remove_first_col

    def split_sprites(self, sprites_width, sprites_height):
        """
        Split the sprite sheet into individual sprites.
        :param sprites_width: Number of sprites horizontally.
        :param sprites_height: Number of sprites vertically.
        :return: List of cropped sprites, width of each sprite, height of each sprite.
        """
        image_width, image_height = self.image.size
        sprite_width = image_width // sprites_width
        sprite_height = image_height // sprites_height

        sprites = []
        for i in range(sprites_height):
            for j in range(sprites_width):
                # Calculate offsets for guide pixels
                left_offset = 1 if self.remove_first_col else 0
                top_offset = 1 if self.remove_first_row else 0

                # Define the crop box, starting after any guide pixels
                left = j * sprite_width + left_offset
                top = i * sprite_height + top_offset
                
                # The end of the crop box is the start plus the cell size
                right = (j + 1) * sprite_width
                bottom = (i + 1) * sprite_height

                # Crop the sprite
                sprite = self.image.crop((left, top, right, bottom))
                sprites.append(sprite)
        
        # Return the actual dimensions of the cropped sprites
        final_sprite_width = sprite_width - left_offset
        final_sprite_height = sprite_height - top_offset

        return sprites, final_sprite_width, final_sprite_height

    def split_animation_frames(self, frame_width, frame_height):
        """
        Split an animation image into frames.
        :param frame_width: Width of each frame.
        :param frame_height: Height of each frame.
        :return: List of cropped frames.
        """
        frames = []
        width, height = self.image.size

        # If frame_width or frame_height is None, use the full image size
        if frame_width is None:
            frame_width = width
        if frame_height is None:
            frame_height = height

        for y in range(0, height, frame_height):
            for x in range(0, width, frame_width):
                frame = self.image.crop((x, y, x + frame_width, y + frame_height))
                frames.append(frame)

        return frames

    def save_sprites(self, sprites, output_folder, base_name):
        """
        Save the sprites to the specified output folder.
        :param sprites: List of sprites to save.
        :param output_folder: Folder to save the sprites.
        :param base_name: Base name for the sprite files.
        """
        os.makedirs(output_folder, exist_ok=True)
        for idx, sprite in enumerate(sprites):
            sprite.save(os.path.join(output_folder, f"{base_name}{idx + 1}.png"))

    def display_sprites(self, sprites, sprites_width, sprites_height, sprite_width, sprite_height):
        """
        Display the sprites in a grid using matplotlib.
        :param sprites: List of sprites to display.
        :param sprites_width: Number of sprites horizontally.
        :param sprites_height: Number of sprites vertically.
        :param sprite_width: Width of each sprite.
        :param sprite_height: Height of each sprite.
        """
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches

        fig, axes = plt.subplots(sprites_height, sprites_width, figsize=(10, 10))
        fig.suptitle("Sprites with Light Gray Background", fontsize=16)

        for i in range(sprites_height):
            for j in range(sprites_width):
                ax = axes[i, j] if sprites_height > 1 else axes[j]
                sprite = sprites[i * sprites_width + j]

                # Draw a light gray background
                gray_background = Image.new('RGBA', sprite.size, 'lightgray')
                ax.imshow(gray_background, extent=[0, sprite_width, 0, sprite_height], aspect='auto')

                # Draw the sprite on top of the background
                ax.imshow(sprite, extent=[0, sprite_width, 0, sprite_height], aspect='auto')

                # Ensure the sprite maintains its original dimensions
                ax.set_aspect('equal')
                ax.axis('off')
                ax.set_title(f"Sprite {i * sprites_width + j}")

        plt.tight_layout()
        plt.show()