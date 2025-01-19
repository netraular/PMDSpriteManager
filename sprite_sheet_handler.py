from PIL import Image
import os

class SpriteSheetHandler:
    def __init__(self, image_path, remove_first_row_and_col=False):
        """
        Initialize the SpriteSheetHandler with the path to the sprite sheet.
        :param image_path: Path to the sprite sheet image.
        :param remove_first_row_and_col: If True, removes the first row and column of pixels from each sprite.
        """
        self.image_path = image_path
        self.image = Image.open(image_path)
        self.remove_first_row_and_col = remove_first_row_and_col

    def split_sprites(self, sprites_ancho, sprites_alto):
        """
        Split the sprite sheet into individual sprites.
        :param sprites_ancho: Number of sprites horizontally.
        :param sprites_alto: Number of sprites vertically.
        :return: List of cropped sprites, width of each sprite, height of each sprite.
        """
        ancho_imagen, alto_imagen = self.image.size
        ancho_sprite = ancho_imagen // sprites_ancho
        alto_sprite = alto_imagen // sprites_alto

        sprites = []
        for i in range(sprites_alto):
            for j in range(sprites_ancho):
                # Calculate cropping coordinates
                left = j * ancho_sprite + (1 if self.remove_first_row_and_col else 0)
                top = i * alto_sprite + (1 if self.remove_first_row_and_col else 0)
                right = left + ancho_sprite - (1 if self.remove_first_row_and_col else 0)
                bottom = top + alto_sprite - (1 if self.remove_first_row_and_col else 0)

                # Crop the sprite
                sprite = self.image.crop((left, top, right, bottom))
                sprites.append(sprite)

        return sprites, ancho_sprite, alto_sprite

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

    def display_sprites(self, sprites, sprites_ancho, sprites_alto, ancho_sprite, alto_sprite):
        """
        Display the sprites in a grid using matplotlib.
        :param sprites: List of sprites to display.
        :param sprites_ancho: Number of sprites horizontally.
        :param sprites_alto: Number of sprites vertically.
        :param ancho_sprite: Width of each sprite.
        :param alto_sprite: Height of each sprite.
        """
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches

        fig, axes = plt.subplots(sprites_alto, sprites_ancho, figsize=(10, 10))
        fig.suptitle("Sprites con fondo gris claro", fontsize=16)

        for i in range(sprites_alto):
            for j in range(sprites_ancho):
                ax = axes[i, j] if sprites_alto > 1 else axes[j]
                sprite = sprites[i * sprites_ancho + j]

                # Draw a light gray background
                fondo_gris = Image.new('RGBA', sprite.size, 'lightgray')
                ax.imshow(fondo_gris, extent=[0, ancho_sprite, 0, alto_sprite], aspect='auto')

                # Draw the sprite on top of the background
                ax.imshow(sprite, extent=[0, ancho_sprite, 0, alto_sprite], aspect='auto')

                # Ensure the sprite maintains its original dimensions
                ax.set_aspect('equal')
                ax.axis('off')
                ax.set_title(f"Sprite {i * sprites_ancho + j}")

        plt.tight_layout()
        plt.show()