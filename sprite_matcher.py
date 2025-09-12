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

        sprite_files = sorted(
            [f for f in os.listdir(edited_sprites_folder) if f.lower().endswith('.png')],
            key=lambda x: int(x.split('_')[-1].split('.')[0])
        )
        
        for file in sprite_files:
            path = os.path.join(edited_sprites_folder, file)
            img = Image.open(path).convert('RGBA')
            processed_sprite_array = self._preprocess_sprite(img)
            
            if processed_sprite_array is not None:
                self.processed_sprites.append((file, processed_sprite_array))
    
    def _preprocess_sprite(self, image):
        """
        Preprocesses a single sprite image for comparison by cropping non-transparent content.
        """
        bbox = image.getbbox()
        if bbox:
            return np.array(image.crop(bbox))
        return None
    
    def _find_match(self, target_array):
        """
        Compares a target sprite array against the entire library of processed sprites.
        """
        if target_array is None:
            return None
            
        for name, lib_sprite_array in self.processed_sprites:
            if target_array.shape == lib_sprite_array.shape and np.array_equal(target_array, lib_sprite_array):
                return name
        return None

    def match_group(self, group_frames):
        """
        Finds the best matching library sprite for each frame and determines if the
        entire group should be considered mirrored.

        Returns:
            A dictionary containing:
            - "frame_matches": A list of sprite numbers (e.g., [10, 11, 12]).
            - "group_is_mirrored": A boolean indicating if the group is mirrored.
            - "per_frame_mirror": A list of booleans indicating if each individual match was mirrored.
        """
        frame_results = []
        for frame in group_frames:
            match_filename = None
            is_mirrored = False
            
            processed_frame = self._preprocess_sprite(frame)
            
            # 1. Try a direct match
            match_filename = self._find_match(processed_frame)
            
            # 2. If no direct match, try a mirrored match
            if not match_filename and processed_frame is not None:
                mirrored_frame = np.fliplr(processed_frame)
                match_filename = self._find_match(mirrored_frame)
                if match_filename:
                    is_mirrored = True
            
            frame_results.append((match_filename, is_mirrored))
        
        mirrored_count = 0
        non_mirrored_count = 0
        sprite_numbers = []
        per_frame_mirror_flags = []

        for filename, is_mirrored in frame_results:
            per_frame_mirror_flags.append(is_mirrored)
            if filename:
                if is_mirrored:
                    mirrored_count += 1
                else:
                    non_mirrored_count += 1
                sprite_numbers.append(int(filename.split('_')[-1].split('.')[0]))
            else:
                sprite_numbers.append(0)
        
        group_is_mirrored = mirrored_count > non_mirrored_count
        
        return {
            "frame_matches": sprite_numbers,
            "group_is_mirrored": group_is_mirrored,
            "per_frame_mirror": per_frame_mirror_flags
        }