#!/usr/bin/env python3
# run.py - Entry point for the Sprite Animation Tool

import sys
import os

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from main import MainApplication
from tkinter import Tk

if __name__ == "__main__":
    root = Tk()
    app = MainApplication(root)
    root.mainloop()
