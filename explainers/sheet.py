"""Contact sheets: python -m explainers.sheet OUT.png a.png b.png ...

A grid of tiles, each under a caption strip.
"""
import sys

from PIL import Image, ImageDraw, ImageFont

from explainers.draw import FONT_DIR, FONTS


def contact_sheet(tiles, out, cols=3, tile=(640, 360)):
    """`tiles` is [(path, PIL image or (h, w, 3) array, caption), ...]."""
    tw, th = tile
    strip = 22
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * (th + strip)), (30, 30, 34))
    d = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(str(FONT_DIR / FONTS["medium"]), 14)
    for i, (src, caption) in enumerate(tiles):
        im = Image.open(src) if isinstance(src, (str, bytes)) or hasattr(src, "__fspath__") else src
        if not isinstance(im, Image.Image):
            im = Image.fromarray(im)
        x, y = (i % cols) * tw, (i // cols) * (th + strip)
        sheet.paste(im.convert("RGB").resize((tw, th), Image.LANCZOS), (x, y + strip))
        d.text((x + 6, y + 3), caption, fill=(255, 226, 90), font=font)
    sheet.save(out)
    return out


if __name__ == "__main__":
    contact_sheet([(f, f.split("/")[-1]) for f in sys.argv[2:]], sys.argv[1])
