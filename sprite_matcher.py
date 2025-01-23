from PIL import Image
import os
import numpy as np
from skimage.metrics import structural_similarity as ssim

class SpriteMatcher:
    def __init__(self, edited_sprites_folder):
        self.edited_sprites = []
        self.sprite_names = []
        
        # Load edited sprites sorted numerically
        sprite_files = sorted(
            [f for f in os.listdir(edited_sprites_folder) if f.lower().endswith('.png')],
            key=lambda x: int(x.split('_')[-1].split('.')[0])
        )
        
        for file in sprite_files:
            path = os.path.join(edited_sprites_folder, file)
            img = Image.open(path)
            self.edited_sprites.append(img)
            self.sprite_names.append(file)
        
        # Sprite preprocessing
        self.common_size = (64, 64)
        self.processed_sprites = [self.preprocess(sprite) for sprite in self.edited_sprites]
    
    def preprocess(self, image):
        """
        Preprocess an image for comparison:
        1. Crop the non-transparent area.
        2. Convert to grayscale on a white background.
        3. Resize to a common size.
        """
        # Crop the non-transparent area
        bbox = image.getbbox()
        if bbox:
            cropped = image.crop(bbox)
        else:
            cropped = image  # If there is no non-transparent area, use the full image
        
        # Convert to grayscale on a white background
        img = cropped.convert('RGBA')
        background = Image.new('RGBA', img.size, (255, 255, 255))
        composite = Image.alpha_composite(background, img).convert('L')
        
        # Resize to the common size
        resized = composite.resize(self.common_size)
        return np.array(resized)
    
    def compare_images(self, img1, img2):
        """
        Calculate similarity using SSIM, but only in non-transparent areas.
        """
        try:
            return ssim(img1, img2, data_range=255)
        except:
            return 0
    
    def match_group(self, group_frames):
        """
        Find the most similar sprites for each frame in the group.
        """
        matches = []
        for frame in group_frames:
            # Preprocess the frame (crop and normalize)
            processed_frame = self.preprocess(frame)
            best_match = None
            highest_score = -1
            
            # Compare with all edited sprites
            for i, sprite in enumerate(self.processed_sprites):
                score = self.compare_images(processed_frame, sprite)
                if score > highest_score:
                    highest_score = score
                    best_match = self.sprite_names[i]
            
            matches.append(best_match)
        return matches