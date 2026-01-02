# ui_components/esp32_asset_exporter.py

import os
import json
import shutil
import pathlib
import xml.etree.ElementTree as ET
from collections import Counter
from PIL import Image

class ESP32AssetExporter:
    def __init__(self, search_path):
        self.search_path = search_path
        self.animation_counts = Counter()

    def _scan_folders(self):
        """Scans folders and populates the animation_counts Counter."""
        for item_name in os.listdir(self.search_path):
            item_path = os.path.join(self.search_path, item_name)

            if os.path.isdir(item_path):
                anim_xml_path = os.path.join(item_path, 'Animations', 'AnimData.xml')

                if os.path.isfile(anim_xml_path):
                    try:
                        tree = ET.parse(anim_xml_path)
                        root = tree.getroot()
                        
                        for anim_node in root.findall('.//Anims/Anim'):
                            name_node = anim_node.find('Name')
                            if name_node is not None and name_node.text:
                                name = name_node.text.strip()
                                self.animation_counts[name] += 1
                    
                    except ET.ParseError as e:
                        print(f"    [ERROR] Could not parse XML file '{anim_xml_path}': {e}")
                    except Exception as e:
                        print(f"    [ERROR] An unexpected error occurred while processing '{anim_xml_path}': {e}")

    def get_most_common_animations(self):
        """
        Counts animations and returns a list of animations with the highest frequency.
        
        Returns:
            tuple: A tuple containing (list_of_animations, highest_count).
                   Returns ([], 0) if no animations are found.
        """
        self.animation_counts.clear()
        self._scan_folders()

        if not self.animation_counts:
            return [], 0

        most_common_list = self.animation_counts.most_common()
        if not most_common_list:
            return [], 0
            
        highest_count = most_common_list[0][1]
        result_animations = [name for name, count in most_common_list if count == highest_count]
        
        return sorted(result_animations), highest_count

    def export(self, log_callback):
        """
        Performs the full export process for ESP32.
        - Finds most common animations.
        - Creates an 'esp32_output' folder.
        - Copies a single 'sprite_shadow.png' to the root.
        - Copies relevant JSONs and sprites from 'output x2' for each character.
        """
        parent_path = pathlib.Path(self.search_path)
        source_dir = parent_path / "output x2"
        dest_dir = parent_path / "esp32_output"

        if not source_dir.is_dir():
            log_callback(f"❌ ERROR: Source folder '{source_dir}' does not exist. Please run 'Export Final Assets (x2)' first.")
            return False

        log_callback("--- Starting ESP32 Export ---")
        log_callback("1. Finding most common animations...")
        common_anims, count = self.get_most_common_animations()

        if not common_anims:
            log_callback("❌ ERROR: No common animations found across all characters.")
            return False
        
        log_callback(f"  -> Found {len(common_anims)} common animations appearing {count} times each.")
        for anim in common_anims:
            log_callback(f"     - {anim}")

        log_callback("\n2. Preparing output directory...")
        if dest_dir.exists():
            log_callback(f"  -> Deleting existing '{dest_dir.name}' folder.")
            shutil.rmtree(dest_dir)
        dest_dir.mkdir()
        log_callback(f"  -> Created clean '{dest_dir.name}' folder.")

        log_callback("\n3. Copying base shadow sprite...")
        shadow_copied = False
        character_folders = [d for d in source_dir.iterdir() if d.is_dir()]
        
        # First, try to find the pre-made 2x shadow in the 'output x2' folder
        for char_folder in character_folders:
            source_shadow_path = char_folder / "sprite_shadow.png"
            if source_shadow_path.is_file():
                try:
                    shutil.copy2(source_shadow_path, dest_dir)
                    log_callback(f"  -> Found and copied 'sprite_shadow.png' from '{char_folder.name}'.")
                    shadow_copied = True
                    break 
                except Exception as e:
                    log_callback(f"  -> ERROR: Could not copy shadow from '{char_folder.name}': {e}")
        
        # If not found in 'output x2', search the original project folders for a 1x version and resize it
        if not shadow_copied:
            log_callback(f"  - INFO: Shadow not found in '{source_dir.name}'. Searching original project folders...")
            project_folders = [d for d in parent_path.iterdir() if d.is_dir() and not d.name.startswith(('.', 'output', 'esp32_output'))]
            for project_folder in project_folders:
                search_paths = [
                    project_folder / "Sprites" / "sprite_shadow.png",
                    project_folder / "Animations" / "sprite_shadow.png",
                    project_folder / "sprite_shadow.png"
                ]
                found_1x_path = next((p for p in search_paths if p.is_file()), None)
                if found_1x_path:
                    try:
                        with Image.open(found_1x_path) as img:
                            img_2x = img.resize((img.width * 2, img.height * 2), Image.NEAREST)
                            img_2x.save(dest_dir / "sprite_shadow.png")
                        log_callback(f"  -> Found 1x shadow in '{project_folder.name}', resized and copied.")
                        shadow_copied = True
                        break
                    except Exception as e:
                        log_callback(f"  -> ERROR: Could not process shadow from '{project_folder.name}': {e}")

        if not shadow_copied:
            log_callback("  - WARNING: 'sprite_shadow.png' not found in any character folder within 'output x2' or source projects.")

        log_callback("\n4. Processing characters and copying assets...")
        
        for char_folder in character_folders:
            char_name = char_folder.name
            log_callback(f"\n--- Processing '{char_name}' ---")
            
            dest_char_dir = dest_dir / char_name
            dest_char_dir.mkdir()
            
            dest_sprites_dir = dest_char_dir / "sprites"
            dest_sprites_dir.mkdir()
            
            copied_sprites = set()

            for anim_name in common_anims:
                json_filename = f"{anim_name}-AnimData.json"
                source_json_path = char_folder / json_filename
                
                if not source_json_path.exists():
                    log_callback(f"  - WARNING: JSON for '{anim_name}' not found for '{char_name}'. Skipping.")
                    continue
                
                shutil.copy2(source_json_path, dest_char_dir)
                log_callback(f"  -> Copied {json_filename}")

                with open(source_json_path, 'r') as f:
                    anim_data = json.load(f)
                
                source_anim_sprites_dir = char_folder / anim_name
                if not source_anim_sprites_dir.is_dir():
                    log_callback(f"  - WARNING: Sprite source folder '{source_anim_sprites_dir.name}' not found. Cannot copy sprites for this animation.")
                    continue

                for group in anim_data.get('sprites', {}).values():
                    for frame in group.get('frames', []):
                        sprite_id = frame.get('id')
                        if sprite_id and sprite_id != '0' and sprite_id not in copied_sprites:
                            sprite_filename = f"sprite_{sprite_id}.png"
                            source_sprite_path = source_anim_sprites_dir / sprite_filename
                            if source_sprite_path.exists():
                                shutil.copy2(source_sprite_path, dest_sprites_dir)
                                copied_sprites.add(sprite_id)
                            else:
                                log_callback(f"  - WARNING: Sprite '{sprite_filename}' not found for '{char_name}'.")
            
            log_callback(f"  -> Finished '{char_name}'. Copied {len(copied_sprites)} unique sprites.")

        log_callback("\n" + "="*50)
        log_callback("✅ ESP32 Export completed successfully!")
        log_callback(f"Assets are located in: {dest_dir}")
        log_callback("="*50)
        return True