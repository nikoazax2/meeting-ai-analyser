"""Converts logo to multi-resolution app.ico + favicon.ico"""
import os
from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(SCRIPT_DIR, "images", "logo transparant.png")
DST_ICO = os.path.join(SCRIPT_DIR, "assets", "app.ico")
DST_FAVICON = os.path.join(SCRIPT_DIR, "images", "favicon.ico")

SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

os.makedirs(os.path.dirname(DST_ICO), exist_ok=True)

img = Image.open(SRC).convert("RGBA")
icons = [img.resize(s, Image.LANCZOS) for s in SIZES]

icons[0].save(DST_ICO, format="ICO", sizes=SIZES, append_images=icons[1:])
print(f"[OK] {DST_ICO} ({len(SIZES)} sizes)")

icons[0].save(DST_FAVICON, format="ICO", sizes=SIZES, append_images=icons[1:])
print(f"[OK] {DST_FAVICON} ({len(SIZES)} sizes)")
