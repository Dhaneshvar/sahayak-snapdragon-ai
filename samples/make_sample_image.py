"""Render samples/sample_kyc_form.txt to a PNG so OCR can be tested offline."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
lines = (HERE / "sample_kyc_form.txt").read_text(encoding="utf-8").splitlines()
try:
    font = ImageFont.truetype("arial.ttf", 22)
except OSError:
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 22)
    except OSError:
        font = ImageFont.load_default()

img = Image.new("RGB", (1400, 40 + 34 * len(lines)), "white")
draw = ImageDraw.Draw(img)
for i, line in enumerate(lines):
    draw.text((40, 20 + 34 * i), line, fill="black", font=font)
img.save(HERE / "sample_kyc_form.png")
print("wrote", HERE / "sample_kyc_form.png")
