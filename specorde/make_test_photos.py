from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import random

folder = Path.home() / "Desktop" / "specorde_test"
folder.mkdir(parents=True, exist_ok=True)

try:
    big_font = ImageFont.load_default(size=90)
except TypeError:
    big_font = None

def make(name, moment, subsec, camera_make, camera_model, number):
    random.seed(number)
    color = (random.randint(40, 200), random.randint(40, 200), random.randint(40, 200))
    img = Image.new("RGB", (900, 600), color)
    draw = ImageDraw.Draw(img)
    draw.text((40, 40), name, fill="white", font=big_font)
    exif = Image.Exif()
    if camera_model:
        exif[271] = camera_make
        exif[272] = camera_model
    if moment:
        exif[0x8769] = {36867: moment.strftime("%Y:%m:%d %H:%M:%S"), 37521: subsec}
    img.save(folder / name, "JPEG", exif=exif)

start = datetime(2026, 6, 14, 15, 0, 0)
number = 1

for i in range(6):
    make(f"IMG_{number:04d}.jpg", start + timedelta(seconds=i // 2), str(500 * (i % 2)).zfill(3), "NIKON CORPORATION", "NIKON D850", number)
    number += 1

for i in range(4):
    make(f"IMG_{number:04d}.jpg", start + timedelta(seconds=90 + i * 2), "000", "NIKON CORPORATION", "NIKON D850", number)
    number += 1

make(f"IMG_{number:04d}.jpg", start + timedelta(seconds=300), "000", "NIKON CORPORATION", "NIKON D850", number)
number += 1

for i in range(3):
    make(f"IMG_{number:04d}.jpg", start + timedelta(seconds=400 + i * 5), "000", "NIKON CORPORATION", "NIKON D850", number)
    number += 1

for i in range(3):
    make(f"IMG_{number:04d}.jpg", start + timedelta(seconds=600 + i * 12), "000", "NIKON CORPORATION", "NIKON D850", number)
    number += 1

for i in range(5):
    make(f"IMG_{number:04d}.jpg", start + timedelta(seconds=92 + i), "000", "SONY", "ILCE-7M4", number)
    number += 1

for i in range(3):
    make(f"IMG_{number:04d}.jpg", None, "", None, None, number)
    number += 1

print("made", number - 1, "photos in", folder)