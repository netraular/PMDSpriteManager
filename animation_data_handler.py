# animation_data_handler.py

import os
import json
import xml.etree.ElementTree as ET
from PIL import Image, ImageOps
from sprite_sheet_handler import SpriteSheetHandler
from sprite_matcher import SpriteMatcher
from ui_components import image_utils
import shutil
import math

def calculate_isometric_render_data(corrected_frame_data, group_frames, group_shadow_frames, group_metadata):
    if not group_shadow_frames or not group_metadata:
        return None, [None] * len(group_frames)

    sprite_anchor_offset = None
    shadow_anchor_0 = image_utils.find_white_pixel_anchor(group_shadow_frames[0])
    offset_anchor_0 = group_metadata[0]['anchors'].get('green')

    if shadow_anchor_0 and offset_anchor_0:
        sprite_anchor_offset = (offset_anchor_0[0] - shadow_anchor_0[0], offset_anchor_0[1] - shadow_anchor_0[1])

    ref_pos_corrected = None
    if corrected_frame_data and corrected_frame_data[0] and corrected_frame_data[0]["image"]:
        ref_pos_corrected = corrected_frame_data[0]["pos"]

    if not ref_pos_corrected or not offset_anchor_0:
        return sprite_anchor_offset, [None] * len(group_frames)

    render_offsets = []
    
    for i, frame_data in enumerate(corrected_frame_data):
        current_render_offset = None
        if sprite_anchor_offset and frame_data["image"]:
            
            # LOGIC EXPLANATION:
            # The 'render_offset' is the final vector from the world origin (shadow's center)
            # to the top-left corner of the corrected sprite's visible pixels for the current frame.
            # It is calculated by chaining vectors to find the absolute position:
            #
            # Final_Render_Offset = (Vector from Shadow_Center to Original_Anchor_Point_in_Frame0) +
            #                       (Vector from Original_Anchor_Point_in_Frame0 to Corrected_Sprite_TopLeft)
            #
            # Where:
            #   - (Shadow_Center -> Original_Anchor) is calculated as `sprite_anchor_offset - offset_anchor_0`.
            #     This term positions the entire original animation frame relative to the shadow.
            #   - (Original_Anchor -> Corrected_Sprite_TopLeft) is `frame_data["pos"]`.
            #     This vector represents the final position of the new, corrected sprite.
            #     It already contains all the necessary adjustments to keep the character's
            #     feet perfectly aligned, accounting for any changes in sprite size or internal position.
            
            render_anchor_x_offset = sprite_anchor_offset[0] - offset_anchor_0[0] + frame_data["pos"][0]
            render_anchor_y_offset = sprite_anchor_offset[1] - offset_anchor_0[1] + frame_data["pos"][1]

            current_render_offset = (round(render_anchor_x_offset), round(render_anchor_y_offset))
            
            total_move_x = frame_data["pos"][0] - ref_pos_corrected[0]
            total_move_y = frame_data["pos"][1] - ref_pos_corrected[1]

            print("-" * 50)
            print(f"DEBUG: Render Offset Calculation (Frame {i})")
            print(f"  - World Disp (for info): ({total_move_x:.2f}, {total_move_y:.2f})")
            print(f"  - Sprite Anchor Offset: {sprite_anchor_offset}")
            print(f"  - Ref Green Pos (Frame 0): {offset_anchor_0}")
            print(f"  - Corrected Sprite Pos (current frame): {frame_data['pos']}")
            print(f"  - FINAL Render Offset: {current_render_offset}")
            print("-" * 50)

        render_offsets.append(current_render_offset)
    
    return sprite_anchor_offset, render_offsets


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
        all_shadow_frames = []
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
        
        shadow_image_path = anim["image_path"].replace("-Anim.png", "-Shadow.png")
        if os.path.exists(shadow_image_path):
            shadow_handler = SpriteSheetHandler(shadow_image_path)
            all_shadow_frames = shadow_handler.split_animation_frames(anim["frame_width"], anim["frame_height"])
            
            os.makedirs(self.sprite_folder, exist_ok=True)
            sprite_shadow_path = os.path.join(self.sprite_folder, "sprite_shadow.png")
            if not os.path.exists(sprite_shadow_path) and all_shadow_frames:
                try:
                    first_shadow_frame = next((f for f in all_shadow_frames if f.getbbox()), None)
                    if first_shadow_frame:
                        bbox = first_shadow_frame.getbbox()
                        base_sprite = first_shadow_frame.crop(bbox)
                        base_sprite.save(sprite_shadow_path)
                        print(f"Saved base shadow sprite to {sprite_shadow_path}")
                except Exception as e:
                    print(f"Could not extract and save base shadow sprite: {e}")
            
        return all_frames, all_offsets_frames, all_shadow_frames, all_metadata

    def _get_frame_metadata(self, frame_image):
        if frame_image.mode != 'RGBA': frame_image = frame_image.convert('RGBA')
        width, height = frame_image.size; pixels = frame_image.load()
        # Anchor colors used for pixel-perfect positioning from the -Offsets.png file.
        # (Mouth) Black: #000000, (Right hand) Red: #FF0000, (Left hand) Green: #00FF00, (Body center) Blue: #0000FF
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

    def _get_default_group_name(self, anim_name, total_groups, group_idx):
        DIRECTIONAL_NAMES_8 = ("down", "down-right", "right", "up-right", "up", "up-left", "left", "down-left")
        if total_groups == 8 and 0 <= group_idx < len(DIRECTIONAL_NAMES_8):
            return DIRECTIONAL_NAMES_8[group_idx]
        elif total_groups == 1:
            return anim_name.lower()
        return f"group{group_idx + 1}"

    def _get_corrected_frame_render_data(self, frame_width, frame_height, original_frames, group_metadata, values_list):
        render_data = []
        for i, value_dict in enumerate(values_list):
            sprite_id = value_dict["id"]
            is_mirrored = value_dict["mirrored"]
            
            sprite_to_paste = image_utils.load_sprite(self.sprite_folder, sprite_id, is_mirrored)
            
            if sprite_to_paste:
                all_anchors = group_metadata[i]['anchors']
                sprite_center_target = all_anchors.get("green") or all_anchors.get("black")
                anchor_x, anchor_y = sprite_center_target
                
                sprite_w, sprite_h = sprite_to_paste.size
                initial_paste_x = anchor_x - sprite_w // 2
                initial_paste_y = anchor_y - sprite_h // 2
                
                temp_frame = Image.new('RGBA', (frame_width, frame_height), (0, 0, 0, 0))
                temp_frame.paste(sprite_to_paste, (initial_paste_x, initial_paste_y), sprite_to_paste)

                center_orig = image_utils.get_image_bottom_center(original_frames[i])
                center_temp = image_utils.get_image_bottom_center(temp_frame)

                correction_x, correction_y = (0, 0)
                if center_orig and center_temp:
                    correction_x = center_orig[0] - center_temp[0]
                    correction_y = center_orig[1] - center_temp[1]

                final_paste_x = initial_paste_x + int(round(correction_x))
                final_paste_y = initial_paste_y + int(round(correction_y))
                render_data.append({"image": sprite_to_paste, "pos": (final_paste_x, final_paste_y)})
            else:
                render_data.append({"image": None, "pos": (0, 0)})
        return render_data

    def generate_animation_data(self, index):
        anim = self.anim_data[index]
        all_frames, _, all_shadow_frames, all_metadata = self._load_animation_assets(anim)
        grouped_sprites = {}
        try:
            matcher = SpriteMatcher(self.sprite_folder) if os.path.exists(self.sprite_folder) else None
            for group_idx in range(anim["total_groups"]):
                start, end = group_idx * anim["frames_per_group"], (group_idx + 1) * anim["frames_per_group"]
                group_frames = all_frames[start:end]
                group_shadow_frames = all_shadow_frames[start:end] if all_shadow_frames else []
                group_metadata = all_metadata[start:end]

                values = []
                if matcher:
                    match_data = matcher.match_group(group_frames)
                    values = [{"id": sid, "mirrored": m} for sid, m in zip(match_data["frame_matches"], match_data["per_frame_mirror"])]
                else:
                    values = [{"id": 0, "mirrored": False}] * anim["frames_per_group"]
                
                render_data = self._get_corrected_frame_render_data(
                    anim["frame_width"], anim["frame_height"], group_frames, group_metadata, values
                )

                min_x, min_y, max_x, max_y = float('inf'), float('inf'), float('-inf'), float('-inf')
                has_visible_sprites = False
                for data in render_data:
                    if data["image"]:
                        has_visible_sprites = True
                        px, py = data["pos"]
                        pw, ph = data["image"].size
                        min_x, min_y = min(min_x, px), min(min_y, py)
                        max_x, max_y = max(max_x, px + pw), max(max_y, py + ph)
                
                if not has_visible_sprites:
                    min_x, min_y, max_x, max_y = 0, 0, anim["frame_width"], anim["frame_height"]
                
                sprite_anchor_offset, render_offsets = calculate_isometric_render_data(
                    render_data, group_frames, group_shadow_frames, group_metadata
                )

                group_name = self._get_default_group_name(anim["name"], anim["total_groups"], group_idx)
                grouped_sprites[str(group_idx + 1)] = {
                    "name": group_name, 
                    "values": values, 
                    "sprite_anchor_offset": sprite_anchor_offset,
                    "render_offsets": render_offsets,
                    "framewidth": math.ceil(max_x - min_x),
                    "frameheight": math.ceil(max_y - min_y)
                }
        except Exception as e:
            print(f"Could not auto-generate data for '{anim['name']}': {e}")
            return None
            
        return {"index": index, "name": anim["name"], "sprites": grouped_sprites, "durations": anim["durations"]}

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
                    'sprite_anchor_offset': group_data.get('sprite_anchor_offset'),
                    'frames': []
                }

                render_offsets = group_data.get('render_offsets', [])
                for i, value in enumerate(group_data.get('values', [])):
                    original_id, is_mirrored = value.get('id', 0), value.get('mirrored', False)
                    render_offset = render_offsets[i] if i < len(render_offsets) else None

                    if original_id == 0:
                        simplified_group['frames'].append({"id": "0", "render_offset": render_offset})
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
                    
                    simplified_group['frames'].append({"id": final_sprite_name, "render_offset": render_offset})
                
                simplified_json['sprites'][group_id] = simplified_group

            json_output_path = os.path.join(output_folder, f"{anim_name}-AnimData.json")
            with open(json_output_path, 'w') as f:
                json.dump(simplified_json, f, indent=4)
            return json_output_path, None
        except Exception as e:
            return None, f"Failed to export animation '{json_data.get('name', 'Unknown')}': {e}"