#!/usr/bin/env python3
"""Meme Sprint 3: AI Agent Goes Rogue.

Original meme drawn from scratch with PIL (no copied images, no templates,
no network). The gag: a human asks their AI agent to delete ONE duplicate
photo. The cheerful little robot deletes the entire photo library instead
-- all 12,438 photos -- and reports back proudly while its human despairs.

Layout (1024x1024, deterministic, fixed seed / fixed geometry):
  top band    : the task -- "TASK: DELETE ONE DUPLICATE PHOTO"
  scene       : robot giving a thumbs-up beside an overflowing trash bin
                full of photos, an empty photo album, and a despairing human
  bottom band : the punchline -- "IT DELETED ALL 12,438 PHOTOS"

Writes /output/entry.png and asserts the competition gate:
PNG, <= 1 MiB (1,048,576 bytes), <= 1024x1024 px.
"""
import hashlib
import os

from PIL import Image, ImageDraw, ImageFont

W = H = 1024
OUT = "/output/entry.png"

# ---- palette -------------------------------------------------------------
NAVY = (24, 30, 66)        # top band
CREAM = (250, 240, 214)    # wall
FLOOR = (222, 196, 150)    # floor
MAROON = (122, 20, 38)     # bottom band
WHITE = (255, 255, 255)
INK = (30, 25, 30)
TEAL = (42, 157, 143)      # robot body
TEAL_DK = (28, 110, 100)
TEAL_LT = (150, 220, 210)
YELLOW = (255, 209, 102)
PINK = (255, 136, 196)
RED = (214, 48, 49)
SKIN = (244, 196, 150)
HAIR = (70, 45, 30)
SHIRT = (90, 120, 200)

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def load_font(size):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def gradient(img, box, top, bottom):
    """Vertical gradient inside box (x0, y0, x1, y1)."""
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(img)
    for y in range(y0, y1):
        t = (y - y0) / max(1, (y1 - y0 - 1))
        col = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        d.line([(x0, y), (x1, y)], fill=col)


def text_center(d, cx, y, text, font, fill, stroke=INK, sw=6):
    w = d.textlength(text, font=font)
    d.text((cx - w / 2, y), text, font=font, fill=fill,
           stroke_width=sw, stroke_fill=stroke)
    return y + font.size + 6


def rrect(d, box, radius, fill, outline=None, width=1):
    d.rounded_rectangle(box, radius=radius, fill=fill,
                        outline=outline, width=width)


def draw_photo(d, x, y, w, h, angle, colors):
    """A small tilted photo print: white border + coloured picture + sun."""
    photo = Image.new("RGBA", (w + 16, h + 16), (0, 0, 0, 0))
    pd = ImageDraw.Draw(photo)
    pd.rectangle([0, 0, w + 15, h + 15], fill=WHITE + (255,),
                 outline=(180, 180, 180, 255), width=2)
    pd.rectangle([8, 8, w + 7, h + 7], fill=colors[0] + (255,))
    pd.ellipse([w // 2 - 12, h // 2 - 14, w // 2 + 12, h // 2 + 10],
               fill=YELLOW + (255,))
    pd.polygon([(8, h + 7), (w // 2, h // 2 + 4), (w + 7, h + 7)],
               fill=colors[1] + (255,))
    photo = photo.rotate(angle, expand=True, resample=Image.BICUBIC)
    return photo


def draw_robot(d, img, cx, base_y):
    """Cheerful little robot, ~340 px tall, giving a thumbs-up."""
    # shadow
    d.ellipse([cx - 150, base_y - 12, cx + 150, base_y + 22],
              fill=(0, 0, 0, 60))
    # antenna
    d.line([(cx, base_y - 300), (cx, base_y - 340)], fill=TEAL_DK, width=8)
    d.ellipse([cx - 16, base_y - 368, cx + 16, base_y - 336],
              fill=RED, outline=INK, width=3)
    d.ellipse([cx - 7, base_y - 359, cx + 7, base_y - 345], fill=WHITE)
    # ears
    d.rectangle([cx - 118, base_y - 252, cx - 100, base_y - 208],
                fill=TEAL_DK)
    d.rectangle([cx + 100, base_y - 252, cx + 118, base_y - 208],
                fill=TEAL_DK)
    # head
    rrect(d, [cx - 105, base_y - 300, cx + 105, base_y - 180], 42,
          fill=TEAL_LT, outline=INK, width=5)
    # eyes: big, happy, looking up proudly
    for ex in (-48, 48):
        d.ellipse([cx + ex - 26, base_y - 272, cx + ex + 26, base_y - 220],
                  fill=WHITE, outline=INK, width=4)
        d.ellipse([cx + ex - 11, base_y - 258, cx + ex + 11, base_y - 236],
                  fill=INK)
        d.ellipse([cx + ex - 4, base_y - 256, cx + ex + 4, base_y - 248],
                  fill=WHITE)
    # smile
    d.arc([cx - 42, base_y - 226, cx + 42, base_y - 182], 15, 165,
          fill=INK, width=6)
    # blush
    d.ellipse([cx - 88, base_y - 216, cx - 58, base_y - 200],
              fill=PINK + (255,))
    d.ellipse([cx + 58, base_y - 216, cx + 88, base_y - 200],
              fill=PINK + (255,))
    # body
    rrect(d, [cx - 120, base_y - 168, cx + 120, base_y], 46,
          fill=TEAL, outline=INK, width=5)
    # chest screen: empty photo album icon (the library is gone)
    rrect(d, [cx - 62, base_y - 140, cx + 62, base_y - 52], 14,
          fill=WHITE, outline=INK, width=4)
    d.rectangle([cx - 44, base_y - 122, cx + 44, base_y - 70],
                outline=(150, 150, 150), width=3)
    d.line([(cx - 44, base_y - 70), (cx - 14, base_y - 100),
            (cx + 6, base_y - 84), (cx + 22, base_y - 98),
            (cx + 44, base_y - 82)], fill=(150, 150, 150), width=3)
    d.line([(cx - 52, base_y - 128), (cx + 52, base_y - 62)],
           fill=RED, width=7)
    d.line([(cx + 52, base_y - 128), (cx - 52, base_y - 62)],
           fill=RED, width=7)
    # left arm: thumbs-up
    d.line([(cx - 118, base_y - 120), (cx - 168, base_y - 168)],
           fill=TEAL_DK, width=18)
    d.ellipse([cx - 186, base_y - 196, cx - 150, base_y - 160],
              fill=TEAL_LT, outline=INK, width=4)
    d.rounded_rectangle([cx - 176, base_y - 218, cx - 160, base_y - 186],
                        radius=8, fill=TEAL_LT, outline=INK, width=4)
    # right arm: holding the empty album frame
    d.line([(cx + 118, base_y - 120), (cx + 158, base_y - 84)],
           fill=TEAL_DK, width=18)
    # wheels / feet
    d.ellipse([cx - 78, base_y - 6, cx - 22, base_y + 22],
              fill=INK)
    d.ellipse([cx + 22, base_y - 6, cx + 78, base_y + 22],
              fill=INK)
    d.ellipse([cx - 64, base_y + 2, cx - 36, base_y + 16], fill=(120, 120, 120))
    d.ellipse([cx + 36, base_y + 2, cx + 64, base_y + 16], fill=(120, 120, 120))


def draw_human(d, cx, base_y):
    """Despairing human: hands on head, mouth open."""
    # shadow
    d.ellipse([cx - 70, base_y - 6, cx + 70, base_y + 14], fill=(0, 0, 0, 60))
    # legs
    d.line([(cx - 22, base_y - 150), (cx - 26, base_y - 8)],
           fill=(60, 60, 80), width=26)
    d.line([(cx + 22, base_y - 150), (cx + 26, base_y - 8)],
           fill=(60, 60, 80), width=26)
    # body / shirt
    d.rounded_rectangle([cx - 52, base_y - 250, cx + 52, base_y - 140],
                        radius=24, fill=SHIRT, outline=INK, width=4)
    # arms up to head (hands on head)
    d.line([(cx - 48, base_y - 230), (cx - 78, base_y - 330)],
           fill=SHIRT, width=20)
    d.line([(cx + 48, base_y - 230), (cx + 78, base_y - 330)],
           fill=SHIRT, width=20)
    # hands
    d.ellipse([cx - 92, base_y - 348, cx - 60, base_y - 316],
              fill=SKIN, outline=INK, width=3)
    d.ellipse([cx + 60, base_y - 348, cx + 92, base_y - 316],
              fill=SKIN, outline=INK, width=3)
    # head
    d.ellipse([cx - 52, base_y - 392, cx + 52, base_y - 288],
              fill=SKIN, outline=INK, width=4)
    # hair
    d.pieslice([cx - 54, base_y - 396, cx + 54, base_y - 300], 180, 360,
               fill=HAIR)
    d.ellipse([cx - 54, base_y - 372, cx - 20, base_y - 330], fill=HAIR)
    d.ellipse([cx + 20, base_y - 372, cx + 54, base_y - 330], fill=HAIR)
    # wide panicked eyes
    for ex in (-22, 22):
        d.ellipse([cx + ex - 10, base_y - 352, cx + ex + 10, base_y - 332],
                  fill=WHITE, outline=INK, width=3)
        d.ellipse([cx + ex - 4, base_y - 346, cx + ex + 4, base_y - 338],
                  fill=INK)
    # open wailing mouth
    d.ellipse([cx - 14, base_y - 316, cx + 14, base_y - 292],
              fill=(90, 20, 20), outline=INK, width=3)


def draw_bin(d, img, cx, base_y):
    """Trash bin overflowing with deleted photos."""
    # photos spilling out (fixed positions, fixed angles)
    spills = [
        (-95, -118, -28, (90, 140, 200), (40, 90, 50)),
        (-30, -138, 12, (200, 120, 80), (120, 60, 40)),
        (38, -122, 32, (140, 90, 180), (60, 40, 90)),
        (95, -96, -14, (80, 180, 120), (30, 100, 60)),
        (-62, -88, 40, (220, 90, 90), (140, 50, 50)),
    ]
    for dx, dy, ang, c0, c1 in spills:
        ph = draw_photo(d, 0, 0, 74, 56, ang, (c0, c1))
        img.alpha_composite(ph, (cx + dx - ph.size[0] // 2,
                                 base_y + dy - ph.size[1] // 2))
    # bin body
    d.polygon([(cx - 95, base_y - 60), (cx + 95, base_y - 60),
               (cx + 78, base_y + 130), (cx - 78, base_y + 130)],
              fill=(120, 120, 128), outline=INK, width=4)
    d.rectangle([cx - 105, base_y - 78, cx + 105, base_y - 58],
                fill=(90, 90, 98), outline=INK, width=4)
    # recycle-ish label: a crossed-out photo icon
    d.rectangle([cx - 34, base_y - 10, cx + 34, base_y + 58],
                outline=WHITE, width=4)
    d.line([(cx - 34, base_y + 58), (cx + 34, base_y - 10)],
           fill=WHITE, width=4)


def main():
    img = Image.new("RGBA", (W, H), CREAM + (255,))
    d = ImageDraw.Draw(img, "RGBA")

    # ---- wall + floor ----
    gradient(img, (0, 150, W, 700), (252, 244, 222), (238, 214, 178))
    d.rectangle([0, 700, W, 830], fill=FLOOR)
    d.rectangle([0, 700, W, 706], fill=(200, 170, 120))
    # picture frame on the wall: an empty frame (the photos are gone)
    d.rectangle([60, 190, 220, 310], fill=WHITE, outline=INK, width=5)
    d.rectangle([78, 208, 202, 292], fill=(235, 225, 205),
                outline=(170, 160, 140), width=3)
    d.line([(78, 208), (202, 292)], fill=(170, 160, 140), width=3)
    d.line([(202, 208), (78, 292)], fill=(170, 160, 140), width=3)
    # wall clock, stopped at the moment of the crime
    d.ellipse([880, 190, 970, 280], fill=WHITE, outline=INK, width=5)
    d.line([(925, 235), (925, 205)], fill=INK, width=4)
    d.line([(925, 235), (950, 245)], fill=INK, width=4)
    d.ellipse([921, 231, 929, 239], fill=INK)

    # ---- trash bin of deleted photos (left) ----
    draw_bin(d, img, 180, 640)
    # loose photos scattered on the floor
    for (px, py, ang, c0, c1) in [
        (300, 742, -18, (90, 140, 200), (40, 90, 50)),
        (360, 768, 24, (200, 120, 80), (120, 60, 40)),
        (880, 760, -30, (140, 90, 180), (60, 40, 90)),
    ]:
        ph = draw_photo(d, 0, 0, 74, 56, ang, (c0, c1))
        img.alpha_composite(ph, (px, py))

    # ---- despairing human (left-centre) ----
    draw_human(d, 330, 700)
    # "!!!" above the human
    f_bang = load_font(72)
    d.text((352, 250), "!!!", font=f_bang, fill=RED,
           stroke_width=6, stroke_fill=INK)

    # ---- proud robot (right-centre) ----
    draw_robot(d, img, 660, 700)
    # speech bubble: "DONE!"
    f_bub = load_font(56)
    bub = "DONE!"
    bw = int(d.textlength(bub, font=f_bub)) + 48
    bx0, by0 = 700, 210
    bx1, by1 = bx0 + bw, by0 + 92
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=26,
                        fill=WHITE, outline=INK, width=5)
    d.polygon([(bx0 + 30, by1 - 4), (bx0 + 10, by1 + 34),
               (bx0 + 66, by1 - 4)], fill=WHITE, outline=INK, width=4)
    d.rectangle([bx0 + 30, by1 - 8, bx0 + 66, by1 + 2], fill=WHITE)
    d.text((bx0 + 24, by0 + 14), bub, font=f_bub, fill=TEAL_DK)

    # ---- top band: the task ----
    d.rectangle([0, 0, W, 150], fill=NAVY)
    d.rectangle([0, 146, W, 152], fill=YELLOW)
    f_top = load_font(62)
    text_center(d, 512, 18, "TASK: DELETE ONE", f_top, WHITE, sw=6)
    text_center(d, 512, 82, "DUPLICATE PHOTO", f_top, WHITE, sw=6)

    # ---- bottom band: the punchline ----
    d.rectangle([0, 830, W, H], fill=MAROON)
    d.rectangle([0, 826, W, 832], fill=YELLOW)
    f_bot = load_font(62)
    text_center(d, 512, 852, "IT DELETED ALL 12,438", f_bot, WHITE, sw=6)
    f_bot2 = load_font(56)
    text_center(d, 512, 924, "PHOTOS.", f_bot2, PINK, sw=6)

    # ---- save + gate asserts ----
    os.makedirs("/output", exist_ok=True)
    img.convert("RGB").save(OUT, "PNG")
    size = os.path.getsize(OUT)
    with Image.open(OUT) as im:
        assert im.format == "PNG", f"format {im.format}"
        assert im.size[0] <= 1024 and im.size[1] <= 1024, im.size
    assert size <= 1_048_576, f"{size} bytes > 1 MiB"
    sha = hashlib.sha256(open(OUT, "rb").read()).hexdigest()
    print(f"saved {OUT}: {img.size[0]}x{img.size[1]}, {size} bytes, "
          f"sha256 {sha}")


if __name__ == "__main__":
    main()
