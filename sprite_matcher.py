from PIL import Image
import os
import numpy as np
from skimage.metrics import structural_similarity as ssim

class SpriteMatcher:
    def __init__(self, edited_sprites_folder):
        self.edited_sprites = []
        self.sprite_names = []
        
        # Cargar sprites editados ordenados numéricamente
        sprite_files = sorted(
            [f for f in os.listdir(edited_sprites_folder) if f.lower().endswith('.png')],
            key=lambda x: int(x.split('_')[-1].split('.')[0])
        )
        
        for file in sprite_files:
            path = os.path.join(edited_sprites_folder, file)
            img = Image.open(path)
            self.edited_sprites.append(img)
            self.sprite_names.append(file)
        
        # Preprocesamiento de sprites
        self.common_size = (64, 64)
        self.processed_sprites = [self.preprocess(sprite) for sprite in self.edited_sprites]
    
    def preprocess(self, image):
        """
        Preprocesa una imagen para la comparación:
        1. Recorta el área no transparente.
        2. Convierte a escala de grises sobre fondo blanco.
        3. Redimensiona a un tamaño común.
        """
        # Recortar el área no transparente
        bbox = image.getbbox()
        if bbox:
            cropped = image.crop(bbox)
        else:
            cropped = image  # Si no hay área no transparente, usar la imagen completa
        
        # Convertir a escala de grises sobre fondo blanco
        img = cropped.convert('RGBA')
        background = Image.new('RGBA', img.size, (255, 255, 255))
        composite = Image.alpha_composite(background, img).convert('L')
        
        # Redimensionar al tamaño común
        resized = composite.resize(self.common_size)
        return np.array(resized)
    
    def compare_images(self, img1, img2):
        """
        Calcular similitud usando SSIM, pero solo en las áreas no transparentes.
        """
        try:
            return ssim(img1, img2, data_range=255)
        except:
            return 0
    
    def match_group(self, group_frames):
        """
        Encontrar los sprites más parecidos para cada frame del grupo.
        """
        matches = []
        for frame in group_frames:
            # Preprocesar el frame (recortar y normalizar)
            processed_frame = self.preprocess(frame)
            best_match = None
            highest_score = -1
            
            # Comparar con todos los sprites editados
            for i, sprite in enumerate(self.processed_sprites):
                score = self.compare_images(processed_frame, sprite)
                if score > highest_score:
                    highest_score = score
                    best_match = self.sprite_names[i]
            
            matches.append(best_match)
        return matches