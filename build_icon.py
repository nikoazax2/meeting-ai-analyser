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
# Pad to square so PIL doesn't squish non-square logos
w, h = img.size
side = max(w, h)
square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
square.paste(img, ((side - w) // 2, (side - h) // 2))

square.save(DST_ICO, format="ICO", sizes=SIZES)
print(f"[OK] {DST_ICO} ({len(SIZES)} sizes, {os.path.getsize(DST_ICO)} bytes)")

square.save(DST_FAVICON, format="ICO", sizes=SIZES)
print(f"[OK] {DST_FAVICON} ({len(SIZES)} sizes, {os.path.getsize(DST_FAVICON)} bytes)")
