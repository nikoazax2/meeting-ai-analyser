"""Convertit logo2.png en app.ico multi-resolution"""
import os
from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(SCRIPT_DIR, "logo2.png")
DST = os.path.join(SCRIPT_DIR, "assets", "app.ico")

SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

img = Image.open(SRC).convert("RGBA")
icons = [img.resize(s, Image.LANCZOS) for s in SIZES]
icons[0].save(DST, format="ICO", sizes=SIZES, append_images=icons[1:])
print(f"[OK] {DST} ({len(SIZES)} tailles)")
