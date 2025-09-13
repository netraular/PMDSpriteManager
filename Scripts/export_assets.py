from pathlib import Path
import shutil  # Module for high-level file operations (copying, removing folders)


def get_main_folder():
    """
    Prompts the user to enter the main folder path and validates it.

    Returns:
        Path: A Path object for the valid, existing directory, or None if the user cancels.
    """
    while True:
        try:
            input_path = input("Please enter the full path to the main folder to process (or press Enter to exit): ")
            if not input_path:
                return None

            main_path = Path(input_path).resolve()

            if not main_path.is_dir():
                print(f"❌ ERROR: The path '{main_path}' is not a valid directory. Please try again.")
                continue

            print(f"✅ Using directory: {main_path}\n")
            return main_path

        except (KeyboardInterrupt, EOFError):
            return None


def process_and_export_animations(main_path: Path):
    """
    Finds common .json animations across all characters and generates an 'output'
    folder with the corresponding assets (JSONs and unique PNG sprites).
    """
    print(f"Analyzing folder structure in: {main_path}\n")

    # --- PART 1: Find common animations ---

    animations_by_character = {}
    character_folders = [d for d in main_path.iterdir() if d.is_dir() and not d.name.startswith(('.', 'output'))]

    if not character_folders:
        print("Error: No character subfolders found in the specified directory.")
        return

    for character_folder in character_folders:
        animation_data_path = character_folder / "AnimationData"
        if not animation_data_path.is_dir():
            continue

        animation_names = {f.name for f in animation_data_path.rglob('*.json')}
        if animation_names:
            animations_by_character[character_folder.name] = animation_names
            print(f"-> Character '{character_folder.name}' found with {len(animation_names)} animations.")
        else:
            animations_by_character[character_folder.name] = set()

    if not animations_by_character:
        print("\nNo characters with valid 'AnimationData' folders were found.")
        return

    set_list = list(animations_by_character.values())
    common_animations = set_list[0].copy()
    for next_set in set_list[1:]:
        common_animations.intersection_update(next_set)

    if not common_animations:
        print("\n❌ No .json animation was found to be common to all characters. Process finished.")
        return

    print("\n-----------------------------------------------------")
    print("✅ Common .json animations found:")
    for file_name in sorted(list(common_animations)):
        print(f"   - {file_name}")
    print("-----------------------------------------------------\n")

    # --- PART 2: Create the output structure and copy the files ---

    print("Starting export process...")

    # Create or clean the 'output' folder
    output_dir = main_path / "output"
    if output_dir.exists():
        print(f"Deleting existing 'output' folder for a clean export...")
        shutil.rmtree(output_dir)
    output_dir.mkdir()

    # Iterate over each character to process their files
    for character_folder in character_folders:
        character_name = character_folder.name
        print(f"\n--- Processing character: {character_name} ---")

        source_animation_data_path = character_folder / "AnimationData"
        if not source_animation_data_path.is_dir():
            print(f"Warning: Character '{character_name}' has no 'AnimationData'. Skipping.")
            continue

        # Create destination folders for this character
        output_character_dir = output_dir / character_name
        output_character_dir.mkdir()
        output_sprites_dir = output_character_dir / "Sprites"
        output_sprites_dir.mkdir()

        # Set to keep track of already copied PNGs to avoid duplicates
        copied_png_names = set()

        # Iterate over each common JSON to copy it and find its sprites
        for json_name in sorted(list(common_animations)):
            # 1. Copy the JSON file
            try:
                # Find the full path of the original json
                source_json_path = next(source_animation_data_path.rglob(json_name))
                dest_json_path = output_character_dir / json_name
                shutil.copy2(source_json_path, dest_json_path)
                print(f"  ✅ Copied JSON: {json_name}")
            except StopIteration:
                print(f"  ❌ Error: Could not find the file '{json_name}' for '{character_name}'.")
                continue

            # 2. Derive animation name and copy the PNG sprites
            animation_name = json_name.removesuffix("-AnimData.json")
            source_sprites_path = source_animation_data_path / animation_name

            if not source_sprites_path.is_dir():
                print(f"  - Warning: Sprite folder '{animation_name}' for this JSON was not found.")
                continue

            print(f"  - Searching for sprites in: '{source_sprites_path.relative_to(main_path)}'")
            found_pngs = list(source_sprites_path.glob('*.png'))

            if not found_pngs:
                print("    - No .png files were found in this folder.")
                continue

            for source_png in found_pngs:
                if source_png.name not in copied_png_names:
                    # If the file name has not been copied before, copy it
                    shutil.copy2(source_png, output_sprites_dir)
                    copied_png_names.add(source_png.name)
                else:
                    # If it already exists, skip it
                    print(f"    - Skipping (duplicate file name): {source_png.name}")

    print("\n-----------------------------------------------------")
    print(f"✅ Process completed. Files have been generated in the folder: {output_dir}")
    print("-----------------------------------------------------")


if __name__ == "__main__":
    main_folder_path = get_main_folder()
    if main_folder_path:
        process_and_export_animations(main_folder_path)
    else:
        print("Operation cancelled. Exiting.")