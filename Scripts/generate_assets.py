import os
import zipfile
from pathlib import Path

# --- Constants ---
# Name of the file to read folder names from for the creation task.
FOLDER_NAMES_FILE = "names.txt"
# Name of the subfolder where zip files will be uncompressed.
UNCOMPRESS_DESTINATION_FOLDER = "Animations"
# URL for the asset download link.
ASSET_DOWNLOAD_URL = "https://sprites.pmdcollab.org/"


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


def create_folders_from_file(main_path: Path):
    """
    Reads folder names from a text file (names.txt) and creates a directory
    for each name in the specified main path.
    """
    print(f"--- 1. Create Folders from '{FOLDER_NAMES_FILE}' ---")
    names_file_path = main_path / FOLDER_NAMES_FILE
    print(f"Reading from: '{names_file_path}'\n")

    try:
        # Open the text file in read mode ('r').
        with open(names_file_path, 'r', encoding='utf-8') as file:
            # Read each line from the file.
            for line in file:
                # .strip() removes whitespace and newlines from the start/end.
                folder_name = line.strip()

                # Check if the line is not empty after stripping.
                if folder_name:
                    try:
                        # Create the folder inside the main path.
                        folder_path = main_path / folder_name
                        folder_path.mkdir(exist_ok=True)
                        print(f"-> Folder created (or already existed): '{folder_path.relative_to(main_path.parent)}'")
                    except OSError as e:
                        # Catch other potential errors, like invalid folder names.
                        print(f"!! Error creating folder '{folder_name}': {e}")
                else:
                    print("-> Found an empty line, skipping.")

    except FileNotFoundError:
        # Handle the error if the text file is not found.
        print(f"!! ERROR: Could not find the file '{names_file_path}'.")
        print("Please make sure the file exists in the directory you specified.")

    print("\nFolder creation process finished.")


def uncompress_zips(main_path: Path):
    """
    Looks for subfolders in the specified main path. If a subfolder contains
    a .zip file, it creates a destination folder (e.g., "Animations") inside
    it and uncompresses the .zip file's contents there.
    """
    print(f"--- 2. Uncompress ZIPs into '{UNCOMPRESS_DESTINATION_FOLDER}' subfolders ---")
    print(f"🚀 Starting process in directory: {main_path}\n")

    # Get a list of all subfolders in the specified directory.
    subfolders = [item for item in main_path.iterdir() if item.is_dir()]

    if not subfolders:
        print("😕 No subfolders found in this directory.")
        return

    # Loop through each of the found subfolders.
    for folder in subfolders:
        print(f"📂 Checking folder: {folder.name}")

        try:
            # Find the first file ending with .zip in this subfolder.
            zip_file = next(folder.glob('*.zip'))
        except StopIteration:
            # If no .zip is found, continue to the next folder.
            print("  -> No .zip file found in this folder. Skipping.")
            print("-" * 20)
            continue

        print(f"  -> Found zip file: {zip_file.name}")

        # Create the full path for the destination folder (e.g., /path/subfolder/Animations).
        destination_path = folder / UNCOMPRESS_DESTINATION_FOLDER

        try:
            # Create the destination folder. `exist_ok=True` prevents an error.
            destination_path.mkdir(exist_ok=True)

            # Open the zip file in read mode ('r').
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                # Extract all the contents into the destination folder.
                zip_ref.extractall(destination_path)

            print(f"  ✅ Success! File uncompressed to: '{destination_path.relative_to(main_path)}'")

        except zipfile.BadZipFile:
            print(f"  ❌ Error! The file '{zip_file.name}' is corrupt or not a valid zip file.")
        except Exception as e:
            print(f"  ❌ Error! An unexpected problem occurred: {e}")

        print("-" * 20)  # Separator for clarity

    print("\n🎉 Uncompress process finished.")


def cleanup_zip_files(main_path: Path):
    """
    Recursively finds all .zip files in the specified path and its
    subdirectories, and asks for user confirmation before deleting them
    permanently.
    """
    print("--- 3. Clean-up Residual ZIP files ---")
    print(f"🚀 Searching for .zip files to delete in: {main_path}\n")

    # Use .rglob('*.zip') for a recursive search in all subfolders.
    zip_files_to_delete = list(main_path.rglob('*.zip'))

    if not zip_files_to_delete:
        print("✅ No residual .zip files found. The directory is already clean!")
        return

    # --- Confirmation Step ---
    print("ATTENTION! The following .zip files were found for deletion:")
    for file_path in zip_files_to_delete:
        # Show the relative path for easier reading.
        print(f"  -> {file_path.relative_to(main_path)}")

    print("\n-------------------------------------------------------------")
    print("⚠️  This action is IRREVERSIBLE. The files will be deleted forever.")
    print("-------------------------------------------------------------")

    try:
        # Ask for user confirmation.
        # .lower().strip() makes the response case-insensitive.
        confirmation = input("Are you sure you want to delete them all? (type 'y' for yes): ").lower().strip()
    except KeyboardInterrupt:
        # If the user presses Ctrl+C, cancel the operation.
        print("\n\nOperation cancelled by the user.")
        return

    if confirmation == 'y':
        print("\n✅ Confirmation received. Starting deletion...")
        deleted_count = 0
        error_count = 0

        # Proceed to delete the files one by one.
        for file_path in zip_files_to_delete:
            try:
                file_path.unlink()  # The method to delete a file in pathlib
                print(f"  🗑️  Deleted: {file_path.relative_to(main_path)}")
                deleted_count += 1
            except Exception as e:
                print(f"  ❌ Error! Could not delete {file_path.name}: {e}")
                error_count += 1

        print(f"\nSummary: {deleted_count} files deleted, {error_count} errors.")
    else:
        print("\n❌ Operation cancelled. No files have been deleted.")

    print("\n🎉 Clean-up process finished.")


def show_download_link():
    """
    Displays the URL for downloading assets.
    """
    print("--- 4. Download Assets ---")
    print("To download the assets, please visit the following website:")
    print(f"\n  -> {ASSET_DOWNLOAD_URL}\n")
    print("Copy and paste the link into your web browser.")


def main_menu():
    """
    Displays the main menu and handles user input to call the appropriate function.
    """
    main_folder_path = None

    while True:
        print("\n" + "=" * 40)
        print("          Asset Management Tool")
        print("=" * 40)
        if main_folder_path:
            print(f"Current Target Folder: {main_folder_path}")
        else:
            print("Current Target Folder: (Not set)")
        print("-" * 40)
        print("Please choose an action:")
        print("  1. Create Folders from 'names.txt'")
        print("  2. Uncompress ZIPs into 'Animations' subfolders")
        print("  3. Clean-up (Delete) all residual .zip files")
        print("  4. Show Asset Download Link")
        print("  5. Change Target Folder")
        print("  6. Exit")
        print("=" * 40)

        choice = input("Enter your choice (1-6): ")

        if choice in ['1', '2', '3'] and not main_folder_path:
            print("\n❌ You must set a target folder first (Option 5).")
            input("\nPress Enter to return to the main menu...")
            continue

        if choice == '1':
            create_folders_from_file(main_folder_path)
        elif choice == '2':
            uncompress_zips(main_folder_path)
        elif choice == '3':
            cleanup_zip_files(main_folder_path)
        elif choice == '4':
            show_download_link()
        elif choice == '5':
            main_folder_path = get_main_folder()
        elif choice == '6':
            print("👋 Exiting the program. Goodbye!")
            break
        else:
            print("\n❌ Invalid choice. Please enter a number between 1 and 6.")

        # Pause to allow the user to read the output before showing the menu again.
        if choice in ['1', '2', '3', '4']:
            input("\nPress Enter to return to the main menu...")


# --- Run the main program ---
if __name__ == "__main__":
    main_menu()