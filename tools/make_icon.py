"""Gera assets/icon.png e assets/icon.ico (rodar uma vez; os arquivos ficam no repositório)."""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT = sys.argv[1] if len(sys.argv) > 1 else "/usr/share/fonts/opentype/inter/Inter-BlackItalic.otf"
S = 1024
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
r = 210
d.rounded_rectangle((24, 24, S - 24, S - 24), r, fill=(12, 12, 15, 255))
# grade estilo caixa de Mega Drive
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle((24, 24, S - 24, S - 24), r, fill=255)
grid = Image.new("RGBA", (S, S), (0, 0, 0, 0))
g = ImageDraw.Draw(grid)
for i in range(24, S, 76):
    g.line((i, 0, i, S), fill=(255, 255, 255, 26), width=3)
    g.line((0, i, S, i), fill=(255, 255, 255, 26), width=3)
# faixa vermelha
g.rectangle((0, 742, S, 830), fill=(226, 35, 26, 255))
grid.putalpha(Image.composite(grid.getchannel("A"), Image.new("L", (S, S), 0), mask))
img = Image.alpha_composite(img, grid)
d = ImageDraw.Draw(img)
font = ImageFont.truetype(FONT, 470)
text = "MD"
bb = d.textbbox((0, 0), text, font=font)
x = (S - (bb[2] - bb[0])) / 2 - bb[0] - 10
y = 190 - bb[1]
d.text((x + 14, y + 14), text, font=font, fill=(0, 0, 0, 160))
d.text((x, y), text, font=font, fill=(255, 255, 255, 255))
d.rounded_rectangle((24, 24, S - 24, S - 24), r, outline=(255, 255, 255, 40), width=6)
out = Path(__file__).resolve().parent.parent / "assets"
out.mkdir(exist_ok=True)
img.resize((512, 512), Image.LANCZOS).save(out / "icon.png")
img.save(out / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("ok")
