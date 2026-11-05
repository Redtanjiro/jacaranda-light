"""Draw the link-preview image (what WhatsApp, iMessage, Slack etc. show when the site is shared).

Usage:  python3 scripts/make_og_image.py PATH/TO/Silkscreen-Bold.ttf PATH/TO/Silkscreen-Regular.ttf
        (fonts: https://github.com/google/fonts/tree/main/ofl/silkscreen)
Writes: data/og.png  1200x630, copied to docs/ by build.py
Requires: pip install pillow
"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
W, H = 1200, 630
FRAME, FRAME_HI, FRAME_LO, EDGE, LAND, WATER = "#5bb8ec", "#a9dcf7", "#2a6fa8", "#14244f", "#22308a", "#141d57"
FLOWER = ["..p.p..", ".ppppp.", "ppPyPpp", ".pyyyp.", "ppPyPpp", ".ppppp.", "..p.p.."]
FMAP = {"p": "#c3a1ff", "P": "#8b5cf6", "y": "#f7e27a"}
CLOUD = ["....ooo.........", "...offfo.ooo....", "..offffooffo....", ".offfffffffffo..", "offffgffffgfffo.",
         "offggggffgggggfo", ".oggggggggggggo.", "..oooooooooooo.."]
CMAP = {"o": "#3a6e86", "f": "#ecf5f8", "g": "#c3cbd0"}

img = Image.new("RGB", (W, H), FRAME)
d = ImageDraw.Draw(img)
d.fontmode = "1"  # no antialiasing, keeps the pixel font crisp
reg = ImageFont.truetype(sys.argv[2], 34)

def sprite(rows, cmap, x, y, s):
    for j, row in enumerate(rows):
        for i, c in enumerate(row):
            if c in cmap: d.rectangle([x+i*s, y+j*s, x+(i+1)*s-1, y+(j+1)*s-1], fill=cmap[c])

# night-map screen with scattered jacaranda dots, framed like the app
d.rectangle([40, 40, W-41, H-41], fill=WATER, outline=EDGE, width=8)
for k in range(260):
    x = 60 + (k*389) % (W-120); y = 60 + (k*233) % (H-120)
    d.rectangle([x, y, x+5, y+5], fill="#9b6cff" if k % 3 else "#e4d4ff")
sprite(CLOUD, CMAP, 830, 90, 14)
sprite(CLOUD, CMAP, 120, 420, 10)
sprite(CLOUD, CMAP, 930, 470, 9)

# title plate: flower + name, like the app header
px, py, pw, ph = 150, 200, 900, 170
d.rectangle([px, py, px+pw, py+ph], fill=LAND, outline=EDGE, width=8)
d.rectangle([px+10, py+10, px+pw-10, py+ph-10], outline=FRAME_HI, width=3)
sprite(FLOWER, FMAP, px+50, py+(ph-7*16)//2, 16)
size = 92  # largest bold size that fits beside the flower
while d.textlength("JACARANDA BAE", font=ImageFont.truetype(sys.argv[1], size)) > pw-250: size -= 2
bold = ImageFont.truetype(sys.argv[1], size)
tx, ty = px+200, py+ph//2
d.text((tx+5, ty+5), "JACARANDA BAE", font=bold, fill=EDGE, anchor="lm")
d.text((tx, ty), "JACARANDA BAE", font=bold, fill=FRAME_HI, anchor="lm")
d.text((W//2, py+ph+60), "JACARANDA SEASON IS HERE", font=reg, fill="#f7c98f", anchor="mm")

out = ROOT/"data/og.png"
img.save(out, optimize=True)
print(out, out.stat().st_size//1024, "KB")
