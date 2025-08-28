# PMD Sprite Manager

## Overview

This manager is designed to simplify working with Pokémon Mystery Dungeon (PMD) sprites from [PMD Collab](https://sprites.pmdcollab.org/). It provides two main functionalities:
1. **Sprite Sheet Splitting**: Divide a master sprite sheet into a library of individual, numbered sprites.
2. **Animation Viewer**: Visualize animations from the game's data and assign your individual sprites to create new animation JSON files.

The manager automatically processes sprite sheets and animation data from PMD Collab, eliminating manual inspection of XML files while preserving transparency and animation timing information.

---

## Features

- 🖼️ **Sprite Sheet Processing**:
  - Split master sprite sheets into individual sprites with transparency.
  - Custom grid division (specify columns/rows) and limit the number of sprites saved.
  - Saves all individual sprites to a clean, generic **`Sprites/`** folder.

- 🎬 **Animation Viewer**:
  - Load animation data from PMD Collab's `AnimData.xml`.
  - Automatically identify and assign sprites to animation frames using AI-powered image matching.
  - Real-time preview of both original game animations and your custom-built animations.
  - Generate and save all animation data to JSON files with a single click.
  - "mirror & copy" support for efficiently handling directional animations.

---

## Getting Started

### 1. Obtain Required Files
1. Visit [PMD Collab](https://sprites.pmdcollab.org/)
2. Select a Pokémon and download:
   - **"Recolor sprites"** (the master sprite sheet PNG)
   - **"all sprites"** (ZIP file with animation data)

### 2. Create Folder Structure
Create a main project folder for your character. Inside, place the master spritesheet and unzip the "all sprites" download into a subfolder renamed to `Animations`.

```bash
YourPokemonFolder/
├── RecolorSprites.png    # The master spritesheet file
└── Animations/
    ├── AnimData.xml      # From the unzipped "all sprites"
    ├── [AnimationName]-Anim.png
    └── ...               # Other files from the ZIP
```

### Example Structure
```bash
PikachuProject/
├── RecolorSprites.png
└── Animations/
    ├── AnimData.xml
    ├── Walk-Anim.png
    ├── Idle-Anim.png
    └── Attack-Anim.png
```

---

## Usage

### For Windows Users
If you're on Windows, you can use the pre-built executable available in the [Releases section](https://github.com/netraular/PMDSpriteManager/releases). Download `PMDSpriteManager.exe` and run it directly—no Python installation required!

### For Other Platforms
1. **Run the Program**:
   ```bash
   python main.py
   ```

2. **Select Your Project Folder**:
   - Choose the main folder you created (e.g., `PikachuProject`).

3. **Main Menu Options**:
   - **Process Sprite Sheet**:
     1. The tool automatically loads `RecolorSprites.png`.
     2. Enter the number of sprites horizontally and vertically, and the total number to save.
     3. Click "Process and Save Sprites". This will create a new **`Sprites/`** subfolder containing all your individual `sprite_1.png`, `sprite_2.png`, etc.
     4. (Optional) You can then proceed to the animation preview screen.

   - **View Animations**:
     1. This screen loads the data from your `Animations/` folder.
     2. Sprites from your `Sprites/` folder are automatically assigned to animation frames.
     3. Use the "Load Preview" button on the right of any group to see a real-time preview of your custom animation.
     4. Use "Previous/Next" to navigate, and click "Save All Animations" to generate all JSON files at once.

---

## User Interface Walkthrough

### 1. Folder Selection Screen
The manager starts by prompting the user to select a folder containing the sprite sheet and animation data. This is the initial screen where users begin their workflow.

![Folder Selection Screen](readme/images/folder_select.png)  
*Caption: The initial screen where users select their main project folder.*

---

### 2. Main Menu
After selecting the folder, the main menu is displayed. From here, users can choose between processing their master sprite sheet or viewing animations.

![Main Menu](readme/images/main_menu.png)  
*Caption: The main menu with options to process the spritesheet or view animations.*

---

### 3. Sprite Sheet Processing
In this mode, users input the grid dimensions of their master sprite sheet. The manager then processes it and saves all the individual sprites into a new `Sprites/` folder.

#### Example of a Divided Sprite Sheet
![Divided Sprite Sheet](readme/images/divide_screen.png)  
*Caption: A sprite sheet being processed, which will result in individual sprites saved to the `Sprites/` folder.*

---

### 4. Animation Viewer
The animation viewer allows users to load, preview, and configure animations. It displays the original animation, the individual frames with their assigned sprite numbers, and a preview of the final result using your custom sprites.

#### Animation Viewer in Action
![Animation Viewer](readme/images/animation_screen.png)  
*Caption: The animation viewer showing the original animation (left), frame inputs (center), and the custom result preview (right).*

---

## How It Works

- **Sprite Processing**:
  - Uses Pillow (PIL) for image manipulation.
  - Handles transparency through alpha channels.

- **Animation System**:
  - Parses PMD Collab's XML animation data.
  - Uses `scikit-image` for Structural Similarity Index (SSIM) matching to automatically assign sprites.
  - Calculates frame timing from game ticks (approx. 30 ticks/second).
  - Uses Tkinter for real-time animation rendering.

---

## Requirements

- **For Windows**: Download the executable from the [Releases section](https://github.com/netraular/PMDSpriteManager/releases).
- **For Other Platforms**:
  - Python 3.7+
  - Libraries:
    ```bash
    pip install pillow scikit-image
    ```
  - Included in Python Standard Library:
    - `tkinter` (for GUI)
    - `xml.etree.ElementTree` (for parsing animation data)

---

## Contributing

Contributions are welcome! Please open an issue for:
- Bug reports
- Feature requests
- Compatibility issues with new PMD Collab formats

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

## Acknowledgments

- Sprites and animation data provided by [PMD Collab](https://sprites.pmdcollab.org/)
- Pokémon Mystery Dungeon © Nintendo/Creatures Inc./GAME FREAK inc.
- Developed for fans by PMD enthusiasts

---

**Happy spriting!** 🐾⚡️