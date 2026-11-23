#!/usr/bin/env python3
"""Meme Sprint 3: AI Agent Goes Rogue.

PURE STDLIB ONLY -- no PIL, no third-party packages, no network, so this
runs in the grading sandbox (minimal python3.13, 1 CPU, 512 MB, 60 s).
Implements its own PNG encoder (zlib, filter 0), a small rasterizer
(filled rects / rounded rects / ellipses / lines / polygons / arcs) and a
compact embedded 5x7 bitmap font for the caption text.

The gag: a human asks their AI agent to delete ONE duplicate photo. The
cheerful little robot deletes the entire photo library instead -- all
12,438 photos -- and reports back proudly while its human despairs.

Layout (1024x1024, deterministic, fixed geometry):
  top band    : the task -- "TASK: DELETE ONE DUPLICATE PHOTO"
  scene       : robot giving a thumbs-up beside an overflowing trash bin
                full of photos, an empty photo album, and a despairing human
  bottom band : the punchline -- "IT DELETED ALL 12,438 PHOTOS."

Writes /output/entry.png and asserts the competition gate:
PNG, <= 1 MiB (1,048,576 bytes), <= 1024x1024 px.
"""
import hashlib
import math
import os
import struct
import zlib

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
GREY = (120, 120, 128)
GREY_DK = (90, 90, 98)
SHADOW = (170, 148, 112)   # soft shadow on the floor (no alpha in RGB)
LIGHT_GREY = (150, 150, 150)


# ---- canvas --------------------------------------------------------------
class Canvas:
    """Plain RGB framebuffer with a few drawing primitives."""

    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.buf = bytearray(bytes(bg) * (w * h))

    def fill_rect(self, x0, y0, x1, y1, color):
        x0 = max(0, int(x0))
        y0 = max(0, int(y0))
        x1 = min(self.w, int(x1))
        y1 = min(self.h, int(y1))
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(color) * (x1 - x0)
        n = x1 - x0
        for y in range(y0, y1):
            off = (y * self.w + x0) * 3
            self.buf[off:off + 3 * n] = row

    def rect_outline(self, x0, y0, x1, y1, fill, outline, width=3):
        self.fill_rect(x0, y0, x1, y1, outline)
        self.fill_rect(x0 + width, y0 + width, x1 - width, y1 - width, fill)

    def fill_ellipse(self, cx, cy, rx, ry, color, y_lo=None, y_hi=None):
        if rx <= 0 or ry <= 0:
            return
        y0 = max(0, int(math.ceil(cy - ry)))
        y1 = min(self.h - 1, int(math.floor(cy + ry)))
        if y_lo is not None:
            y0 = max(y0, int(y_lo))
        if y_hi is not None:
            y1 = min(y1, int(y_hi))
        for y in range(y0, y1 + 1):
            t = (y - cy) / ry
            dx = rx * math.sqrt(max(0.0, 1.0 - t * t))
            self.fill_rect(int(cx - dx), y, int(cx + dx) + 1, y + 1, color)

    def ellipse_outline(self, cx, cy, rx, ry, fill, outline, width=3):
        self.fill_ellipse(cx, cy, rx + width, ry + width, outline)
        self.fill_ellipse(cx, cy, rx, ry, fill)

    def disc(self, cx, cy, r, color):
        self.fill_ellipse(cx, cy, r, r, color)

    def line(self, x0, y0, x1, y1, color, width=1):
        """Thick line: discs stamped along a Bresenham walk."""
        dx = x1 - x0
        dy = y1 - y0
        steps = max(abs(dx), abs(dy), 1)
        r = max(1, width // 2)
        for i in range(steps + 1):
            t = i / steps
            self.disc(int(round(x0 + dx * t)), int(round(y0 + dy * t)),
                      r, color)

    def polyline(self, points, color, width=1):
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            self.line(ax, ay, bx, by, color, width)

    def fill_polygon(self, points, color):
        """Scanline polygon fill."""
        if len(points) < 3:
            return
        ys = [p[1] for p in points]
        y0 = max(0, int(math.ceil(min(ys))))
        y1 = min(self.h - 1, int(math.floor(max(ys))))
        n = len(points)
        for y in range(y0, y1 + 1):
            xs = []
            for i in range(n):
                ax, ay = points[i]
                bx, by = points[(i + 1) % n]
                if ay == by:
                    continue
                if (ay <= y < by) or (by <= y < ay):
                    xs.append(ax + (y - ay) * (bx - ax) / (by - ay))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                self.fill_rect(int(xs[i]), y, int(xs[i + 1]) + 1, y + 1,
                               color)

    def polygon_outline(self, points, color, width=3):
        self.fill_polygon(points, color)

    def rrect(self, x0, y0, x1, y1, radius, color):
        """Filled rounded rectangle."""
        r = min(radius, (x1 - x0) // 2, (y1 - y0) // 2)
        self.fill_rect(x0 + r, y0, x1 - r, y1, color)
        self.fill_rect(x0, y0 + r, x1, y1 - r, color)
        for cx, cy in ((x0 + r, y0 + r), (x1 - r, y0 + r),
                       (x0 + r, y1 - r), (x1 - r, y1 - r)):
            self.disc(cx, cy, r, color)

    def rrect_outline(self, x0, y0, x1, y1, radius, fill, outline,
                      width=4):
        self.rrect(x0 - width, y0 - width, x1 + width, y1 + width,
                   radius + width, outline)
        self.rrect(x0, y0, x1, y1, radius, fill)

    def arc(self, cx, cy, rx, ry, start_deg, end_deg, color, width=4):
        """Arc sampled in degrees, stamped with discs."""
        r = max(1, width // 2)
        a = start_deg
        while a <= end_deg:
            t = math.radians(a)
            self.disc(int(round(cx + rx * math.cos(t))),
                      int(round(cy + ry * math.sin(t))), r, color)
            a += 2


# ---- 5x7 bitmap font -----------------------------------------------------
# Only the glyphs the captions need: A-Z, 0-9, ':', '!', '.', ',', space.
FONT = {
    'A': ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    'B': ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    'C': ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    'D': ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    'E': ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    'F': ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    'G': ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    'H': ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    'I': ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    'J': ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    'K': ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    'L': ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    'M': ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    'N': ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    'O': ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    'P': ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    'Q': ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    'R': ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    'S': ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    'T': ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    'U': ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    'V': ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    'W': ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    'X': ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    'Y': ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    'Z': ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    '0': ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    '1': ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    '2': ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    '3': ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    '4': ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    '5': ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    '6': ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    '7': ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    '8': ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    '9': ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    ':': ("00000", "00100", "00000", "00000", "00000", "00100", "00000"),
    '!': ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    '.': ("00000", "00000", "00000", "00000", "00000", "00000", "01100"),
    ',': ("00000", "00000", "00000", "00000", "00000", "00100", "01000"),
    ' ': ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
}


def text_width(text, scale):
    return len(text) * 6 * scale


def draw_text(c, x, y, text, scale, fill, stroke=None, sw=0):
    """Draw text; stroke pass first (expanded blocks), then the fill."""
    cells = []
    for i, ch in enumerate(text):
        glyph = FONT.get(ch, FONT[' '])
        gx = x + i * 6 * scale
        for r in range(7):
            for col in range(5):
                if glyph[r][col] == '1':
                    cells.append((gx + col * scale, y + r * scale))
    if stroke is not None and sw > 0:
        for px, py in cells:
            c.fill_rect(px - sw, py - sw, px + scale + sw,
                        py + scale + sw, stroke)
    for px, py in cells:
        c.fill_rect(px, py, px + scale, py + scale, fill)


def text_center(c, cx, y, text, scale, fill, stroke=None, sw=0):
    x = cx - text_width(text, scale) // 2
    draw_text(c, x, y, text, scale, fill, stroke, sw)


# ---- PNG encoder ---------------------------------------------------------
def _chunk(tag, data):
    out = struct.pack(">I", len(data)) + tag + data
    out += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    return out


def write_png(path, c):
    raw = bytearray()
    stride = c.w * 3
    for y in range(c.h):
        raw.append(0)  # filter 0: none
        raw += c.buf[y * stride:(y + 1) * stride]
    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", struct.pack(">IIBBBBB", c.w, c.h, 8, 2, 0, 0, 0))
    png += _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += _chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


# ---- scene pieces --------------------------------------------------------
def _rot(px, py, cx, cy, angle_deg):
    t = math.radians(angle_deg)
    co, si = math.cos(t), math.sin(t)
    return (cx + (px - cx) * co - (py - cy) * si,
            cy + (px - cx) * si + (py - cy) * co)


def draw_photo(c, cx, cy, w, h, angle, c0, c1):
    """A small tilted photo print: white border + picture + sun + hills."""
    hw, hh = (w + 16) / 2, (h + 16) / 2
    corners = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
    pts = [_rot(cx + dx, cy + dy, cx, cy, angle) for dx, dy in corners]
    c.fill_polygon(pts, WHITE)
    iw, ih = w / 2, h / 2
    inner = [(-iw, -ih), (iw, -ih), (iw, ih), (-iw, ih)]
    pts = [_rot(cx + dx, cy + dy, cx, cy, angle) for dx, dy in inner]
    c.fill_polygon(pts, c0)
    # sun
    sx, sy = _rot(cx + w // 4, cy - h // 5, cx, cy, angle)
    c.disc(int(sx), int(sy), 11, YELLOW)
    # hills
    m = [(-iw, ih), (0, 0), (iw * 0.45, ih * 0.35), (iw, ih)]
    pts = [_rot(cx + dx, cy + dy, cx, cy, angle) for dx, dy in m]
    c.fill_polygon(pts, c1)


def draw_robot(c, cx, base_y):
    """Cheerful little robot, ~340 px tall, giving a thumbs-up."""
    # shadow
    c.fill_ellipse(cx, base_y + 5, 150, 17, SHADOW)
    # antenna
    c.line(cx, base_y - 300, cx, base_y - 340, TEAL_DK, 8)
    c.ellipse_outline(cx, base_y - 352, 16, 16, RED, INK, 3)
    c.disc(cx, base_y - 352, 7, WHITE)
    # ears
    c.fill_rect(cx - 118, base_y - 252, cx - 100, base_y - 208, TEAL_DK)
    c.fill_rect(cx + 100, base_y - 252, cx + 118, base_y - 208, TEAL_DK)
    # head
    c.rrect_outline(cx - 105, base_y - 300, cx + 105, base_y - 180, 42,
                    TEAL_LT, INK, 5)
    # eyes: big, happy, looking up proudly
    for ex in (-48, 48):
        c.ellipse_outline(cx + ex, base_y - 246, 26, 26, WHITE, INK, 4)
        c.disc(cx + ex, base_y - 247, 11, INK)
        c.disc(cx + ex - 4, base_y - 252, 4, WHITE)
    # smile
    c.arc(cx, base_y - 204, 42, 22, 15, 165, INK, 6)
    # blush
    c.fill_ellipse(cx - 73, base_y - 208, 15, 8, PINK)
    c.fill_ellipse(cx + 73, base_y - 208, 15, 8, PINK)
    # body
    c.rrect_outline(cx - 120, base_y - 168, cx + 120, base_y, 46,
                    TEAL, INK, 5)
    # chest screen: empty photo album icon (the library is gone)
    c.rrect_outline(cx - 62, base_y - 140, cx + 62, base_y - 52, 14,
                    WHITE, INK, 4)
    c.rect_outline(cx - 44, base_y - 122, cx + 44, base_y - 70,
                   (235, 225, 205), LIGHT_GREY, 3)
    c.polyline([(cx - 44, base_y - 70), (cx - 14, base_y - 100),
                (cx + 6, base_y - 84), (cx + 22, base_y - 98),
                (cx + 44, base_y - 82)], LIGHT_GREY, 3)
    c.line(cx - 52, base_y - 128, cx + 52, base_y - 62, RED, 7)
    c.line(cx + 52, base_y - 128, cx - 52, base_y - 62, RED, 7)
    # left arm: thumbs-up
    c.line(cx - 118, base_y - 120, cx - 168, base_y - 168, TEAL_DK, 18)
    c.ellipse_outline(cx - 168, base_y - 178, 18, 18, TEAL_LT, INK, 4)
    c.rrect_outline(cx - 176, base_y - 218, cx - 160, base_y - 186, 8,
                    TEAL_LT, INK, 4)
    # right arm: holding the empty album frame
    c.line(cx + 118, base_y - 120, cx + 158, base_y - 84, TEAL_DK, 18)
    # wheels / feet
    c.fill_ellipse(cx - 50, base_y + 8, 28, 14, INK)
    c.fill_ellipse(cx + 50, base_y + 8, 28, 14, INK)
    c.fill_ellipse(cx - 50, base_y + 9, 14, 7, (120, 120, 120))
    c.fill_ellipse(cx + 50, base_y + 9, 14, 7, (120, 120, 120))


def draw_human(c, cx, base_y):
    """Despairing human: hands on head, mouth open."""
    # shadow
    c.fill_ellipse(cx, base_y + 4, 70, 10, SHADOW)
    # legs
    c.line(cx - 22, base_y - 150, cx - 26, base_y - 8, (60, 60, 80), 26)
    c.line(cx + 22, base_y - 150, cx + 26, base_y - 8, (60, 60, 80), 26)
    # body / shirt
    c.rrect_outline(cx - 52, base_y - 250, cx + 52, base_y - 140, 24,
                    SHIRT, INK, 4)
    # arms up to head (hands on head)
    c.line(cx - 48, base_y - 230, cx - 78, base_y - 330, SHIRT, 20)
    c.line(cx + 48, base_y - 230, cx + 78, base_y - 330, SHIRT, 20)
    # hands
    c.ellipse_outline(cx - 76, base_y - 332, 16, 16, SKIN, INK, 3)
    c.ellipse_outline(cx + 76, base_y - 332, 16, 16, SKIN, INK, 3)
    # head
    c.ellipse_outline(cx, base_y - 340, 52, 52, SKIN, INK, 4)
    # hair: top half of the head circle
    c.fill_ellipse(cx, base_y - 340, 54, 54, HAIR,
                   y_lo=base_y - 396, y_hi=base_y - 348)
    c.fill_ellipse(cx - 37, base_y - 351, 17, 21, HAIR)
    c.fill_ellipse(cx + 37, base_y - 351, 17, 21, HAIR)
    # wide panicked eyes
    for ex in (-22, 22):
        c.ellipse_outline(cx + ex, base_y - 342, 10, 10, WHITE, INK, 3)
        c.disc(cx + ex, base_y - 342, 4, INK)
    # open wailing mouth
    c.ellipse_outline(cx, base_y - 304, 14, 12, (90, 20, 20), INK, 3)


def draw_bin(c, cx, base_y):
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
        draw_photo(c, cx + dx, base_y + dy, 74, 56, ang, c0, c1)
    # bin body
    c.fill_polygon([(cx - 95, base_y - 60), (cx + 95, base_y - 60),
                    (cx + 78, base_y + 130), (cx - 78, base_y + 130)],
                   GREY)
    c.polyline([(cx - 95, base_y - 60), (cx + 95, base_y - 60),
                (cx + 78, base_y + 130), (cx - 78, base_y + 130),
                (cx - 95, base_y - 60)], INK, 4)
    c.rect_outline(cx - 105, base_y - 78, cx + 105, base_y - 58,
                   GREY_DK, INK, 4)
    # crossed-out photo label
    c.rect_outline(cx - 34, base_y - 10, cx + 34, base_y + 58,
                   GREY, WHITE, 4)
    c.line(cx - 34, base_y + 58, cx + 34, base_y - 10, WHITE, 4)


def main():
    c = Canvas(W, H, CREAM)

    # ---- wall + floor ----
    for y in range(150, 700):
        t = (y - 150) / 549.0
        col = tuple(int((252, 244, 222)[i] +
                        ((238, 214, 178)[i] - (252, 244, 222)[i]) * t)
                    for i in range(3))
        c.fill_rect(0, y, W, y + 1, col)
    c.fill_rect(0, 700, W, 830, FLOOR)
    c.fill_rect(0, 700, W, 706, (200, 170, 120))
    # picture frame on the wall: an empty frame (the photos are gone)
    c.rect_outline(60, 190, 220, 310, WHITE, INK, 5)
    c.rect_outline(78, 208, 202, 292, (235, 225, 205),
                   (170, 160, 140), 3)
    c.line(78, 208, 202, 292, (170, 160, 140), 3)
    c.line(202, 208, 78, 292, (170, 160, 140), 3)
    # wall clock, stopped at the moment of the crime; sits up-right so
    # its rim still peeks out from behind the "DONE!" bubble
    c.ellipse_outline(940, 222, 45, 45, WHITE, INK, 5)
    c.line(940, 222, 940, 192, INK, 4)
    c.line(940, 222, 965, 232, INK, 4)
    c.disc(940, 222, 4, INK)

    # ---- trash bin of deleted photos (left) ----
    draw_bin(c, 180, 640)
    # loose photos scattered on the floor
    for (px, py, ang, c0, c1) in [
        (300, 742, -18, (90, 140, 200), (40, 90, 50)),
        (360, 768, 24, (200, 120, 80), (120, 60, 40)),
        (880, 760, -30, (140, 90, 180), (60, 40, 90)),
    ]:
        draw_photo(c, px, py, 74, 56, ang, c0, c1)

    # ---- despairing human (left-centre) ----
    draw_human(c, 330, 700)
    # "!!!" above the human
    draw_text(c, 352, 245, "!!!", 9, RED, stroke=INK, sw=3)

    # ---- proud robot (right-centre) ----
    draw_robot(c, 660, 700)
    # speech bubble: "DONE!"
    bub = "DONE!"
    bw = text_width(bub, 7) + 48
    bx0, by0 = 700, 210
    bx1, by1 = bx0 + bw, by0 + 92
    c.rrect_outline(bx0, by0, bx1, by1, 26, WHITE, INK, 5)
    c.fill_polygon([(bx0 + 30, by1 - 4), (bx0 + 10, by1 + 34),
                    (bx0 + 66, by1 - 4)], WHITE)
    c.line(bx0 + 30, by1 - 4, bx0 + 10, by1 + 34, INK, 4)
    c.line(bx0 + 10, by1 + 34, bx0 + 66, by1 - 4, INK, 4)
    c.fill_rect(bx0 + 30, by1 - 8, bx0 + 66, by1 + 2, WHITE)
    draw_text(c, bx0 + 24, by0 + 14, bub, 7, TEAL_DK)

    # ---- top band: the task ----
    c.fill_rect(0, 0, W, 150, NAVY)
    c.fill_rect(0, 146, W, 152, YELLOW)
    text_center(c, 512, 12, "TASK: DELETE ONE", 9, WHITE, stroke=INK, sw=3)
    text_center(c, 512, 80, "DUPLICATE PHOTO", 9, WHITE, stroke=INK, sw=3)

    # ---- bottom band: the punchline ----
    c.fill_rect(0, 830, W, H, MAROON)
    c.fill_rect(0, 826, W, 832, YELLOW)
    text_center(c, 512, 852, "IT DELETED ALL 12,438", 7, WHITE,
                stroke=INK, sw=3)
    text_center(c, 512, 924, "PHOTOS.", 8, PINK, stroke=INK, sw=3)

    # ---- save + gate asserts ----
    os.makedirs("/output", exist_ok=True)
    write_png(OUT, c)
    size = os.path.getsize(OUT)
    with open(OUT, "rb") as f:
        head = f.read(33)
    assert head[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    w, h = struct.unpack(">II", head[16:24])
    assert (w, h) == (1024, 1024), (w, h)
    assert size <= 1_048_576, f"{size} bytes > 1 MiB"
    sha = hashlib.sha256(open(OUT, "rb").read()).hexdigest()
    print(f"saved {OUT}: {w}x{h}, {size} bytes, sha256 {sha}")


if __name__ == "__main__":
    main()
