# sprite_matcher.py

from PIL import Image
import os
import numpy as np

class SpriteMatcher:
    def __init__(self, edited_sprites_folder):
        """
        Initializes the matcher by loading and preprocessing all available library sprites.
        """
        self.processed_sprites = []
        
        if not os.path.exists(edited_sprites_folder):
            raise FileNotFoundError(f"Sprites folder not found at: {edited_sprites_folder}")

        # Load library sprites, sorted numerically to ensure consistent order
        sprite_files = sorted(
            [f for f in os.listdir(edited_sprites_folder) if f.lower().endswith('.png')],
            key=lambda x: int(x.split('_')[-1].split('.')[0])
        )
        
        for file in sprite_files:
            path = os.path.join(edited_sprites_folder, file)
            img = Image.open(path).convert('RGBA')
            
            # Preprocess the sprite by cropping it and converting to a NumPy array
            processed_sprite_array = self._preprocess_sprite(img)
            
            if processed_sprite_array is not None:
                # Store the sprite's name and its pixel data array
                self.processed_sprites.append((file, processed_sprite_array))
    
    def _preprocess_sprite(self, image):
        """
        Preprocesses a single sprite image for comparison.
        1. Finds the bounding box of the non-transparent content.
        2. Crops the image to this bounding box.
        3. Converts the cropped image to a NumPy array for fast comparison.
        """
        # Get the bounding box of the actual sprite content
        bbox = image.getbbox()
        
        if bbox:
            # Crop the image to the content
            cropped = image.crop(bbox)
            # Convert to a NumPy array for pixel-perfect comparison
            return np.array(cropped)
        else:
            # This is a fully transparent image, so there's nothing to match
            return None
    
    def _find_match(self, target_array):
        """
        Compares a target sprite array against the entire library of processed sprites.
        
        Args:
            target_array: The NumPy array of the sprite to find a match for.

        Returns:
            The filename of the matching sprite, or None if no match is found.
        """
        if target_array is None:
            return None
            
        # Check for a direct, pixel-perfect match
        for name, lib_sprite_array in self.processed_sprites:
            # First, check if dimensions are identical. This is a fast way to rule out non-matches.
            if target_array.shape == lib_sprite_array.shape:
                # If shapes match, perform a full, element-wise array comparison.
                if np.array_equal(target_array, lib_sprite_array):
                    return name
        return None

    def match_group(self, group_frames):
        """
        Finds the best matching library sprite for each frame in a given animation group.
        It checks for both a direct match and a horizontally mirrored match.
        
        Returns:
            A list of tuples, where each tuple is (filename, is_mirrored_match).
        """
        matches = []
        for frame in group_frames:
            match_filename = None
            is_mirrored = False
            
            # 1. Preprocess the animation frame to isolate the sprite content
            processed_frame = self._preprocess_sprite(frame)
            
            # 2. Try to find a direct match
            match_filename = self._find_match(processed_frame)
            
            # 3. If no direct match is found, try finding a mirrored match
            if not match_filename and processed_frame is not None:
                # Flip the frame horizontally (left-to-right)
                mirrored_frame = np.fliplr(processed_frame)
                match_filename = self._find_match(mirrored_frame)
                if match_filename:
                    is_mirrored = True

            matches.append((match_filename, is_mirrored))
            
        return matches