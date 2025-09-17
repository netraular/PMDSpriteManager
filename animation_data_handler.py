# animation_data_handler.py

import os
import json
import xml.etree.ElementTree as ET
from PIL import Image, ImageOps
from sprite_sheet_handler import SpriteSheetHandler
from sprite_matcher import SpriteMatcher
import shutil
import math

class AnimationDataHandler:
    def __init__(self, project_path):
        self.project_path = project_path
        self.sprite_folder = os.path.join(project_path, "Sprites")
        self.animations_folder = os.path.join(project_path, "Animations")
        self.anim_data = self._load_anim_data()

    def _load_anim_data(self):
        anim_data_path = os.path.join(self.animations_folder, "AnimData.xml")
        if not os.path.exists(anim_data_path):
            print(f"Warning: XML file not found in: {self.animations_folder}")
            return []
        tree = ET.parse(anim_data_path)
        return self._process_xml(tree)

    def _get_source_anim_info(self, anim_name, xml_anims_map, visited=None):
        """Recursively finds the base properties and source name for an animation, avoiding cycles."""
        if visited is None:
            visited = set()
        
        if anim_name in visited:
            print(f"Warning: Circular dependency detected in CopyOf for animation '{anim_name}'.")
            return None
        
        if anim_name not in xml_anims_map:
            return None

        visited.add(anim_name)
        anim_xml = xml_anims_map[anim_name]
        copy_of_tag = anim_xml.find('CopyOf')

        if copy_of_tag is not None:
            source_name = copy_of_tag.text
            return self._get_source_anim_info(source_name, xml_anims_map, visited)

        fw_tag = anim_xml.find("FrameWidth")
        fh_tag = anim_xml.find("FrameHeight")
        if fw_tag is not None and fh_tag is not None:
            return {
                "source_name": anim_name,
                "properties": {
                    "frame_width": int(fw_tag.text),
                    "frame_height": int(fh_tag.text),
                    "durations": [int(d.text) for d in anim_xml.findall("Durations/Duration")]
                }
            }
        
        return None

    def _process_xml(self, tree):
        animations = []
        anims_root = tree.getroot().find("Anims")
        if not anims_root: return []

        xml_anims_map = {anim.find('Name').text: anim for anim in anims_root.findall('Anim')}
        
        for anim_name in xml_anims_map:
            try:
                source_info = self._get_source_anim_info(anim_name, xml_anims_map)

                if source_info is None:
                    continue
                
                image_source_name = source_info["source_name"]
                base_properties = source_info["properties"]
                
                anim_data = {
                    "name": anim_name,
                    **base_properties,
                    "image_path": os.path.join(self.animations_folder, f"{image_source_name}-Anim.png")
                }

                if not os.path.exists(anim_data["image_path"]):
                    continue

                with Image.open(anim_data["image_path"]) as img:
                    anim_data["total_groups"] = img.height // anim_data["frame_height"]
                    anim_data["frames_per_group"] = img.width // anim_data["frame_width"]

                animations.append(anim_data)
            except Exception as e:
                print(f"Error processing XML for animation '{anim_name}': {e}. Skipping.")
        
        return animations

    def _load_animation_assets(self, anim):
        handler = SpriteSheetHandler(anim["image_path"])
        all_frames = handler.split_animation_frames(anim["frame_width"], anim["frame_height"])
        
        all_offsets_frames = []
        all_metadata = []
        offsets_image_path = anim["image_path"].replace("-Anim.png", "-Offsets.png")
        if os.path.exists(offsets_image_path):
            offsets_handler = SpriteSheetHandler(offsets_image_path)
            all_offsets_frames = offsets_handler.split_animation_frames(anim["frame_width"], anim["frame_height"])
            all_metadata = [self._get_frame_metadata(f) for f in all_offsets_frames]
        else:
            default_anchor = (anim["frame_width"] // 2, anim["frame_height"] // 2 - 1)
            num_frames = anim["total_groups"] * anim["frames_per_group"]
            all_metadata = [{"anchors": {"black": default_anchor}}] * num_frames
            
        return all_frames, all_offsets_frames, all_metadata

    def _get_frame_metadata(self, frame_image):
        if frame_image.mode != 'RGBA': frame_image = frame_image.convert('RGBA')
        width, height = frame_image.size; pixels = frame_image.load()
        anchor_colors = {"black": (0, 0, 0, 255), "red": (255, 0, 0, 255), "green": (0, 255, 0, 255), "blue": (0, 0, 255, 255)}
        found_anchors = {color: None for color in anchor_colors}
        for x in range(width):
            for y in range(height):
                for color_name, color_value in anchor_colors.items():
                    if pixels[x, y] == color_value: found_anchors[color_name] = (x, y)
        for color, coords in found_anchors.items():
            if coords: found_anchors[color] = (coords[0], coords[1] - 1)
        if found_anchors["black"] is None:
            found_anchors["black"] = (width // 2, height // 2 - 1)
        return {"anchors": found_anchors}

    def _get_image_bottom_center(self, image):
        """Calculates the bottom-center of the visible pixels in an image."""
        bbox = image.getbbox()
        if not bbox:
            return None
        center_x = (bbox[0] + bbox[2]) / 2
        bottom_y = bbox[3]
        return (center_x, bottom_y)
    
    def _get_default_group_name(self, anim_name, total_groups, group_idx):
        DIRECTIONAL_NAMES_8 = ("down", "down-right", "right", "up-right", "up", "up-left", "left", "down-left")
        if total_groups == 8 and 0 <= group_idx < len(DIRECTIONAL_NAMES_8):
            return DIRECTIONAL_NAMES_8[group_idx]
        elif total_groups == 1:
            return anim_name.lower()
        return f"group{group_idx + 1}"

    def calculate_corrected_offsets(self, frame_width, frame_height, original_frames, group_metadata, values_list):
        corrected_offsets = []
        for i, value_dict in enumerate(values_list):
            sprite_id = value_dict["id"]
            is_mirrored = value_dict["mirrored"]
            original_anchor = group_metadata[i]['anchors']['black']
            if not original_anchor:
                corrected_offsets.append((0, 0)); continue
            
            sprite_to_paste = None
            if sprite_id > 0:
                try:
                    path = os.path.join(self.sprite_folder, f"sprite_{sprite_id}.png")
                    sprite_to_paste = Image.open(path).convert('RGBA')
                except FileNotFoundError: pass
            
            if sprite_to_paste:
                if is_mirrored: sprite_to_paste = ImageOps.mirror(sprite_to_paste)
                anchor_x, anchor_y = original_anchor
                sprite_w, sprite_h = sprite_to_paste.size
                initial_paste_x = anchor_x - sprite_w // 2
                initial_paste_y = anchor_y - sprite_h // 2
                
                temp_frame = Image.new('RGBA', (frame_width, frame_height), (0, 0, 0, 0))
                temp_frame.paste(sprite_to_paste, (initial_paste_x, initial_paste_y), sprite_to_paste)

                center_orig = self._get_image_bottom_center(original_frames[i])
                center_temp = self._get_image_bottom_center(temp_frame)

                correction_x, correction_y = (0, 0)
                if center_orig and center_temp:
                    correction_x = center_orig[0] - center_temp[0]
                    correction_y = center_orig[1] - center_temp[1]

                corrected_offsets.append((anchor_x + int(round(correction_x)), anchor_y + int(round(correction_y))))
            else:
                corrected_offsets.append(original_anchor)
        return corrected_offsets

    def generate_animation_data(self, index):
        anim = self.anim_data[index]
        all_frames, _, all_metadata = self._load_animation_assets(anim)
        grouped_sprites = {}
        try:
            matcher = SpriteMatcher(self.sprite_folder) if os.path.exists(self.sprite_folder) else None
            for group_idx in range(anim["total_groups"]):
                start, end = group_idx * anim["frames_per_group"], (group_idx + 1) * anim["frames_per_group"]
                group_frames = all_frames[start:end]
                group_metadata = all_metadata[start:end]

                values = []
                if matcher:
                    match_data = matcher.match_group(group_frames)
                    values = [{"id": sid, "mirrored": m} for sid, m in zip(match_data["frame_matches"], match_data["per_frame_mirror"])]
                else:
                    values = [{"id": 0, "mirrored": False}] * anim["frames_per_group"]
                
                corrected_offsets = self.calculate_corrected_offsets(
                    anim["frame_width"], anim["frame_height"], group_frames, group_metadata, values
                )
                
                group_name = self._get_default_group_name(anim["name"], anim["total_groups"], group_idx)
                grouped_sprites[str(group_idx + 1)] = {"name": group_name, "values": values, "offsets": corrected_offsets}
        except Exception as e:
            print(f"Could not auto-generate data for '{anim['name']}': {e}")
            return None
            
        return {"index": index, "name": anim["name"], "framewidth": anim["frame_width"], "frameheight": anim["frame_height"], "sprites": grouped_sprites, "durations": anim["durations"]}

    def export_optimized_animation(self, json_data):
        if not json_data: return None, "No JSON data provided."
        try:
            base_folder_name = "AnimationData"
            output_folder = os.path.join(self.project_path, base_folder_name)
            os.makedirs(output_folder, exist_ok=True)
            
            anim_name = json_data['name']
            sprites_subfolder = os.path.join(output_folder, anim_name)

            if os.path.exists(sprites_subfolder):
                shutil.rmtree(sprites_subfolder)
            os.makedirs(sprites_subfolder)

            processed_sprites = set()
            simplified_json = {k: json_data[k] for k in ["name", "durations"] if k in json_data}
            simplified_json['sprites'] = {}
            
            for group_id, group_data in json_data.get('sprites', {}).items():
                simplified_group = {
                    'name': group_data.get('name'),
                    'framewidth': group_data.get('framewidth', 2),
                    'frameheight': group_data.get('frameheight', 2),
                    'frames': []
                }

                offsets = group_data.get('offsets', [])
                for i, value in enumerate(group_data.get('values', [])):
                    original_id, is_mirrored = value.get('id', 0), value.get('mirrored', False)
                    offset = offsets[i] if i < len(offsets) else [0, 0]

                    if original_id == 0:
                        simplified_group['frames'].append({"id": "0", "offset": offset})
                        continue

                    final_sprite_name = f"{original_id}_mirrored" if is_mirrored else str(original_id)
                    
                    if final_sprite_name not in processed_sprites:
                        try:
                            source_path = os.path.join(self.sprite_folder, f"sprite_{original_id}.png")
                            img = Image.open(source_path).convert('RGBA')
                            if is_mirrored: img = ImageOps.mirror(img)
                            img_8bit = img.convert('P', palette=Image.ADAPTIVE, colors=256)
                            img_8bit.save(os.path.join(sprites_subfolder, f"sprite_{final_sprite_name}.png"))
                            processed_sprites.add(final_sprite_name)
                        except FileNotFoundError: print(f"Warning: sprite_{original_id}.png not found.")
                        except Exception as e: print(f"Error processing sprite {original_id}: {e}")
                    
                    simplified_group['frames'].append({"id": final_sprite_name, "offset": offset})
                
                simplified_json['sprites'][group_id] = simplified_group

            json_output_path = os.path.join(output_folder, f"{anim_name}-AnimData.json")
            with open(json_output_path, 'w') as f:
                json.dump(simplified_json, f, indent=4)
            return json_output_path, None
        except Exception as e:
            return None, f"Failed to export animation '{json_data.get('name', 'Unknown')}': {e}"