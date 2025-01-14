# Sprite Sheet Handler

## Overview

This project is designed to simplify the handling of sprite sheets downloaded from [https://sprites.pmdcollab.org/](https://sprites.pmdcollab.org/). The website allows users to download a sprite sheet (a single image containing multiple sprites) and a `.zip` file containing metadata about the positions of sprites for animations. This tool aims to:

1. **Separate sprites from the sprite sheet**: Automatically split the sprite sheet into individual sprites.
2. **Generate an animation document**: Create a text-based document that describes how to animate the sprites, eliminating the need to manually inspect the `.zip` files provided by the website.

The goal is to make it easier to work with sprite sheets and animations by providing a streamlined workflow.

---

## Current Script: Visualize and Separate Sprites

The current script (`sprite_sheet_handler.py`) is a Python tool that allows users to:

1. **Select a folder**: The user selects a folder containing the sprite sheet (a `.png` file).
2. **Visualize the sprite sheet**: The script displays the sprite sheet for reference.
3. **Specify sprite dimensions**: The user inputs the number of sprites horizontally (`sprites_ancho`) and vertically (`sprites_alto`) in the sprite sheet.
4. **Separate sprites**: The script automatically crops and saves each individual sprite into a new folder named `[OriginalFolderName]Edited`.
5. **Preview sprites**: The script displays the separated sprites in a grid with a light gray background, ensuring transparency is preserved.

### How It Works
- The script uses `PIL` (Pillow) to handle image processing.
- It uses `matplotlib` to display the sprite sheet and separated sprites.
- The user is prompted to input the number of sprites in the sheet, and the script calculates the dimensions of each sprite.
- Each sprite is saved as a separate `.png` file in the output folder.

---

## Future Features
1. **Animation Document Generation**: The next version of the tool will generate a text-based document that describes how to animate the sprites using the separated sprite files. This will eliminate the need to manually inspect the `.zip` files provided by [https://sprites.pmdcollab.org/](https://sprites.pmdcollab.org/).
2. **Improved User Interface**: A graphical user interface (GUI) will be added to make the tool more user-friendly.
3. **Batch Processing**: Support for processing multiple sprite sheets at once.

---

## Requirements
To run the script, you need the following Python libraries:
- `Pillow` (for image processing)
- `matplotlib` (for visualization)
- `tkinter` (for file dialog)

You can install the required libraries using `pip`:
```bash
pip install pillow matplotlib
```

---

## Usage
1. Download a sprite sheet and its corresponding `.zip` file from [https://sprites.pmdcollab.org/](https://sprites.pmdcollab.org/).
2. Place the sprite sheet (`.png` file) in a folder.
3. Run the script:
   ```bash
   python sprite_sheet_handler.py
   ```
4. Select the folder containing the sprite sheet.
5. Input the number of sprites horizontally and vertically when prompted.
6. The script will:
   - Display the sprite sheet.
   - Separate the sprites and save them in a new folder.
   - Display the separated sprites in a grid for preview.

---

## Example
### Input
- A sprite sheet (`spritesheet.png`) with 4 sprites horizontally and 2 sprites vertically.
- Folder structure:
  ```
  /sprites
    spritesheet.png
  ```

### Output
- A new folder (`spritesEdited`) containing:
  ```
  /spritesEdited
    sprite1.png
    sprite2.png
    sprite3.png
    ...
    sprite8.png
  ```
- A preview of the separated sprites displayed in a grid.

---

## Contributing
Contributions are welcome! If you'd like to improve the tool or add new features, feel free to open an issue or submit a pull request.

---

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

## Acknowledgments
- Thanks to [PMD Collab](https://sprites.pmdcollab.org/) for providing the sprite sheets and metadata.
- Built with Python and love for pixel art! 🎨
