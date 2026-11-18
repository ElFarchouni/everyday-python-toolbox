"""
image_to_icon.py: Convert an image (PNG, JPEG, BMP, GIF, WebP...) to a Windows .ico icon.

The image is padded to a square (transparent background) so it is not
distorted, then saved as a multi-size .ico file. A multi-size icon looks
sharp everywhere Windows uses it: taskbar, desktop, Explorer, title bar.

Requirements:
    pip install Pillow

Usage:
    python image_to_icon.py input.png [output.ico] [--sizes 16,32,48,256]

Examples:
    python image_to_icon.py logo.png                   # creates logo.ico
    python image_to_icon.py photo.jpg app.ico           # custom output name
    python image_to_icon.py logo.png --sizes 32,64,128  # custom sizes

Default sizes: 16, 32, 48, 64, 128, 256 (256 is the maximum for .ico).
Tip: start from a square PNG with a transparent background for best results.
"""

import argparse
import sys
from pathlib import Path

from PIL import Image

DEFAULT_SIZES = [16, 32, 48, 64, 128, 256]
MAX_ICO_SIZE = 256

parser = argparse.ArgumentParser(description="Convert an image to a Windows .ico icon.")
parser.add_argument("input", help="image to convert (png, jpg, jpeg, bmp, gif, webp...)")
parser.add_argument("output", nargs="?", help="output .ico path (default: same name as input)")
parser.add_argument(
    "--sizes",
    default=",".join(str(s) for s in DEFAULT_SIZES),
    help="comma-separated icon sizes in pixels (default: %(default)s)",
)
args = parser.parse_args()

source = Path(args.input)
if not source.is_file():
    print(f"File not found: {source}")
    sys.exit(1)

output = Path(args.output) if args.output else source.with_suffix(".ico")

# Parse and validate the requested sizes
try:
    sizes = sorted({int(s) for s in args.sizes.split(",") if s.strip()})
except ValueError:
    print("Sizes must be whole numbers, e.g. --sizes 16,32,48")
    sys.exit(1)

if not sizes or any(s < 1 or s > MAX_ICO_SIZE for s in sizes):
    print(f"Sizes must be between 1 and {MAX_ICO_SIZE} pixels.")
    sys.exit(1)

# Open the image and convert to RGBA so transparency is preserved
# (JPEGs have no alpha channel; converting adds a fully opaque one).
image = Image.open(source).convert("RGBA")
print(f"Loaded {source} ({image.width}x{image.height})")

# Pad to a square so the icon is not stretched, centering the original image
side = max(image.width, image.height)
if image.width != image.height:
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(image, ((side - image.width) // 2, (side - image.height) // 2))
    image = square
    print(f"Padded to a {side}x{side} square")

if side < max(sizes):
    print(f"Note: the source is only {side}px wide, so larger icon sizes will be upscaled.")

# Pillow builds every requested size from this one image and packs them into a single .ico
image.save(output, format="ICO", sizes=[(s, s) for s in sizes])

print(f"\nDone! Created {output} with sizes: {', '.join(str(s) for s in sizes)}")
