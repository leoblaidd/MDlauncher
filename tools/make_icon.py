"""Gera assets/icon.png e assets/icon.ico: caixa prata com "MD" preto."""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT = sys.argv[1] if len(sys.argv) > 1 else "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
S = 1024
M, R = 40, 210
box = (M, M, S - M, S - M)

mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle(box, R, fill=255)

# gradiente prata com leve tom azulado + reflexo na metade (cromado)
grad = Image.new("RGBA", (S, S))
gd = ImageDraw.Draw(grad)
stops = [(0.0, (246, 248, 251)), (0.47, (205, 214, 225)), (0.53, (178, 191, 207)), (1.0, (140, 155, 175))]
for y in range(S):
    t = y / (S - 1)
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        if a <= t <= b:
            k = (t - a) / (b - a)
            c = tuple(int(ca[i] + (cb[i] - ca[i]) * k) for i in range(3))
            break
    gd.line((0, y, S, y), fill=c + (255,))

shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
ImageDraw.Draw(shadow).rounded_rectangle((M, M + 14, S - M, S - M + 14), R, fill=(0, 0, 0, 110))
shadow = shadow.filter(ImageFilter.GaussianBlur(14))

img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
img = Image.alpha_composite(img, shadow)
silver = Image.new("RGBA", (S, S), (0, 0, 0, 0))
silver.paste(grad, (0, 0), mask)
img = Image.alpha_composite(img, silver)

d = ImageDraw.Draw(img)
d.rounded_rectangle(box, R, outline=(255, 255, 255, 170), width=6)
font = ImageFont.truetype(FONT, 480)
bb = d.textbbox((0, 0), "MD", font=font)
x = (S - (bb[2] - bb[0])) / 2 - bb[0]
y = (S - (bb[3] - bb[1])) / 2 - bb[1]
d.text((x, y + 6), "MD", font=font, fill=(255, 255, 255, 90))  # brilho embaixo (gravado)
d.text((x, y), "MD", font=font, fill=(10, 12, 16, 255))

out = Path(__file__).resolve().parent.parent / "assets"
out.mkdir(exist_ok=True)
img.save(out / "icon-1024.png")
img.resize((512, 512), Image.LANCZOS).save(out / "icon.png")
img.save(out / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("ok")
