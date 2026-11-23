#!/usr/bin/env python3
"""EP3 screen images (Pillow). Writes everything to ../overlays/.

    python3 make_screens.py

Laptop versions are 1600x1000 (the 1.6 aspect of STU_Screen_Laptop):
  laptop_connecting      shot 0 until the join chime
  laptop_call            the call with nobody speaking
  laptop_viktor_0 .. 3   Viktor speaking, the highlight from resting to its strongest pulse
  laptop_mic_S_L         shot 3: her mic at strike step S (0 live .. 7 crossed out, with the label) over Viktor at voice level L
  laptop_muted, laptop_evening
Full frame, 1080x1920: caption-evening (transparent, overlaid in post by finish.py).
Not used by the episode since the finished layout stays off screen, kept in case it returns: laptop_presentation,
full_presentation.
"""
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parents[1] / "overlays"
S = 2  # everything is drawn at twice the size and scaled down, which smooths the edges

AVENIR = "/System/Library/Fonts/Avenir Next.ttc"
GEORGIA = "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"
FONTS = {"bold": (AVENIR, 0), "demi": (AVENIR, 2), "medium": (AVENIR, 5), "serif": (GEORGIA, 0)}

CALL_TITLE = "Синхронизация"
MUTED_LABEL = "Ваш микрофон выключен"
CONNECTING = "Подключение…"
CALL_ENDED = "Созвон завершён"
CAPTION_EVENING = "Тем же вечером"
HEADLINE = ("Новый", "дизайн")
SUBTITLE = ("Презентация, редизайн", "и мобильная версия")

CREAM = (251, 239, 227)
PAPER = (255, 249, 242)
PEACH_SOFT = (255, 225, 203)
PEACH = (247, 170, 130)
CORAL = (226, 116, 76)
TERRA = (196, 82, 52)
BROWN = (74, 52, 40)
DEEP = (90, 51, 37)
WHITE = (255, 253, 250)


def lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def font(key, size):
    path, index = FONTS[key]
    return ImageFont.truetype(path, int(size * S), index=index)


def fit(text, key, size, max_w, floor):
    """The largest size up to `size` at which the text fits max_w. Text below `floor` would be unreadable."""
    while size >= floor:
        if font(key, size).getlength(text) / S <= max_w:
            return size
        size -= 1
    raise ValueError(f"{text!r} does not fit {max_w}px at {floor}px")


class Canvas:
    def __init__(self, w, h, bg=CREAM):
        self.w, self.h = w, h
        self.img = Image.new("RGB", (w * S, h * S), bg)
        self.d = ImageDraw.Draw(self.img)

    def gradient(self, top, bottom):
        size = self.img.size
        mask = Image.linear_gradient("L").resize(size, Image.BICUBIC)
        self.img.paste(Image.composite(Image.new("RGB", size, bottom), Image.new("RGB", size, top), mask))

    def rrect(self, box, r, fill=None, outline=None, width=0):
        self.d.rounded_rectangle([v * S for v in box], r * S, fill=fill, outline=outline, width=int(width * S))

    def circle(self, cx, cy, r, fill=None, outline=None, width=0):
        self.d.ellipse([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], fill=fill, outline=outline,
                       width=int(width * S))

    def line(self, x1, y1, x2, y2, width, fill):
        """A line with round ends."""
        self.d.line([x1 * S, y1 * S, x2 * S, y2 * S], fill=fill, width=int(width * S))
        self.circle(x1, y1, width / 2, fill)
        self.circle(x2, y2, width / 2, fill)

    def text(self, x, y, text, key, size, fill, anchor="mm"):
        self.d.text((x * S, y * S), text, font=font(key, size), fill=fill, anchor=anchor)

    def shadow(self, box, r, blur=16, dy=6, alpha=46, color=(120, 72, 44)):
        x0, y0, x1, y1 = [int(v * S) for v in box]
        pad = blur * S * 3
        mask = Image.new("L", (x1 - x0 + 2 * pad, y1 - y0 + 2 * pad), 0)
        ImageDraw.Draw(mask).rounded_rectangle([pad, pad, pad + x1 - x0, pad + y1 - y0], r * S, fill=alpha)
        mask = mask.filter(ImageFilter.GaussianBlur(blur * S))
        self.img.paste(Image.new("RGB", mask.size, color), (x0 - pad, y0 - pad + dy * S), mask)

    def glow(self, cx, cy, r, color, alpha=90, blur=60):
        pad = blur * S * 3
        side = int(2 * r * S + 2 * pad)
        mask = Image.new("L", (side, side), 0)
        ImageDraw.Draw(mask).ellipse([pad, pad, side - pad, side - pad], fill=alpha)
        mask = mask.filter(ImageFilter.GaussianBlur(blur * S))
        self.img.paste(Image.new("RGB", (side, side), color), (int((cx - r) * S - pad), int((cy - r) * S - pad)), mask)

    def sun(self, cx, cy, r, top, bottom):
        side = int(2 * r * S)
        mask = Image.new("L", (side * 2, side * 2), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, side * 2 - 1, side * 2 - 1], fill=255)
        mask = mask.resize((side, side), Image.LANCZOS)
        ramp = Image.linear_gradient("L").resize((side, side), Image.BICUBIC)
        body = Image.composite(Image.new("RGB", (side, side), bottom), Image.new("RGB", (side, side), top), ramp)
        self.img.paste(body, (int((cx - r) * S), int((cy - r) * S)), mask)

    def hill(self, base, amp, wavelength, phase, color):
        points = [(x * S, (base + amp * math.sin(2 * math.pi * x / wavelength + phase)) * S)
                  for x in range(0, self.w + 7, 6)]
        self.d.polygon(points + [(self.w * S + 12, self.h * S), (0, self.h * S)], fill=color)

    def avatar(self, rgba, cx, cy, diameter):
        side = int(diameter * S)
        face = rgba.resize((side, side), Image.LANCZOS)
        self.img.paste(face, (int(cx * S - side / 2), int(cy * S - side / 2)), face)

    def save(self, name):
        OUT.mkdir(parents=True, exist_ok=True)
        self.img.resize((self.w, self.h), Image.LANCZOS).save(OUT / f"{name}.png", optimize=True)
        print("wrote", name)


# ---------------------------------------------------------------- avatars (720 px, round)
A = 720


def portrait(bg):
    img = Image.new("RGBA", (A, A), bg + (255,))
    return img, ImageDraw.Draw(img)


def rounded(img):
    side = img.size[0]
    mask = Image.new("L", (side * 2, side * 2), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, side * 2 - 1, side * 2 - 1], fill=255)
    img.putalpha(mask.resize((side, side), Image.LANCZOS))
    return img


def dots(d, y, dx, r, color=BROWN):
    for x in (360 - dx, 360 + dx):
        d.ellipse([x - r, y - r, x + r, y + r], fill=color)


def av_viktor():
    """Slick, square-jawed and delighted with himself. An invented face, drawn at double size for the large tile."""
    k = 2

    def p(*values):
        return [v * k for v in values]

    skin, shade, hair, shine = (244, 196, 156), (222, 164, 124), (46, 36, 36), (122, 100, 96)
    suit, lapel, ink = (66, 54, 78), (48, 38, 60), (52, 38, 34)
    img = Image.new("RGBA", (A * k, A * k), (250, 196, 150, 255))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(p(58, 566, 662, 980), 130 * k, fill=suit)
    d.polygon(p(272, 556, 448, 556, 360, 748), fill=WHITE)
    d.polygon(p(272, 548, 196, 612, 262, 662, 360, 752), fill=lapel)
    d.polygon(p(448, 548, 524, 612, 458, 662, 360, 752), fill=lapel)
    d.polygon(p(346, 616, 374, 616, 396, 708, 360, 752, 324, 708), fill=CORAL)
    d.polygon(p(336, 574, 384, 574, 374, 616, 346, 616), fill=(204, 92, 62))
    d.rectangle(p(306, 500, 414, 582), fill=shade)
    d.ellipse(p(176, 282, 234, 378), fill=skin)
    d.ellipse(p(486, 282, 544, 378), fill=skin)
    d.ellipse(p(192, 304, 220, 358), fill=shade)
    d.ellipse(p(500, 304, 528, 358), fill=shade)
    d.rounded_rectangle(p(214, 120, 506, 440), 90 * k, fill=skin)
    d.rounded_rectangle(p(196, 318, 524, 546), 64 * k, fill=skin)      # the jaw is wider than the forehead
    d.line(p(360, 526, 360, 539), fill=shade, width=6 * k)
    d.polygon(p(204, 270, 192, 180, 222, 108, 290, 58, 380, 42, 462, 64, 516, 118, 530, 196, 516, 270,
                494, 232, 474, 196, 414, 172, 336, 170, 270, 184, 232, 222), fill=hair)
    d.arc(p(230, 72, 560, 330), 200, 275, fill=shine, width=8 * k)     # combed straight back
    d.arc(p(262, 100, 560, 340), 205, 280, fill=shine, width=7 * k)
    d.arc(p(304, 128, 560, 340), 225, 290, fill=shine, width=6 * k)
    d.line(p(256, 262, 328, 252), fill=hair, width=18 * k)
    d.line(p(392, 240, 464, 252), fill=hair, width=18 * k)             # one eyebrow is always up
    d.ellipse(p(262, 280, 326, 326), fill=WHITE)
    d.ellipse(p(394, 276, 458, 322), fill=WHITE)
    for x, y in ((298, 304), (430, 300)):
        d.ellipse(p(x - 15, y - 15, x + 15, y + 15), fill=ink)
        d.ellipse(p(x - 9, y - 10, x - 1, y - 2), fill=WHITE)
    d.line(p(258, 284, 330, 284), fill=ink, width=8 * k)
    d.line(p(390, 280, 462, 280), fill=ink, width=8 * k)
    d.line(p(362, 322, 346, 386, 378, 392), fill=shade, width=8 * k)
    d.chord(p(240, 356, 480, 520), 0, 180, fill=WHITE, outline=ink, width=7 * k)
    for x in (282, 321, 360, 399, 438):
        bottom = 438 + 82 * math.sqrt(1 - ((x - 360) / 120) ** 2) - 7
        d.line(p(x, 443, x, bottom), fill=(214, 206, 200), width=4 * k)
    d.arc(p(216, 398, 262, 470), 110, 250, fill=shade, width=6 * k)
    d.arc(p(458, 398, 504, 470), -70, 70, fill=shade, width=6 * k)
    for cx, cy, r in ((586, 430, 46), (634, 370, 20)):                 # the smile gleams
        t = r * 0.22
        d.polygon(p(cx, cy - r, cx + t, cy - t, cx + r, cy, cx + t, cy + t,
                    cx, cy + r, cx - t, cy + t, cx - r, cy, cx - t, cy - t), fill=WHITE)
    return rounded(img)


def av_olya():
    skin, hair = (247, 212, 182), (138, 82, 54)
    img, d = portrait((255, 216, 168))
    d.ellipse([90, 560, 630, 1000], fill=(126, 160, 148))
    d.ellipse([282, 40, 438, 196], fill=hair)
    d.ellipse([178, 130, 542, 530], fill=hair)
    d.ellipse([214, 186, 506, 534], fill=skin)
    d.pieslice([214, 150, 506, 400], 180, 360, fill=hair)
    for x in (296, 424):
        d.ellipse([x - 54, 306, x + 54, 414], fill=(255, 246, 236), outline=BROWN, width=9)
    d.line([350, 350, 370, 350], fill=BROWN, width=8)
    dots(d, 360, 64, 12)
    d.arc([322, 420, 398, 482], 25, 155, fill=(176, 84, 62), width=9)
    return rounded(img)


def av_gena():
    skin, beard = (240, 198, 160), (106, 72, 52)
    img, d = portrait((233, 201, 168))
    d.ellipse([70, 560, 650, 1000], fill=(160, 112, 84))
    d.ellipse([204, 150, 516, 560], fill=beard)
    d.ellipse([232, 190, 488, 440], fill=skin)
    d.pieslice([190, 66, 530, 400], 180, 360, fill=(200, 101, 74))
    d.rounded_rectangle([180, 212, 540, 268], 24, fill=(168, 78, 54))
    d.ellipse([326, 28, 394, 96], fill=(247, 170, 130))
    dots(d, 338, 62, 14)
    d.ellipse([340, 364, 380, 404], fill=(216, 156, 120))
    d.line([328, 462, 392, 462], fill=(238, 190, 160), width=10)
    return rounded(img)


def av_lena():
    skin, hair = (249, 216, 190), (66, 46, 42)
    img, d = portrait((243, 193, 176))
    d.rounded_rectangle([150, 120, 570, 720], 170, fill=hair)
    d.ellipse([100, 590, 620, 1000], fill=(250, 236, 216))
    d.ellipse([222, 168, 498, 520], fill=skin)
    d.pieslice([206, 118, 514, 400], 180, 360, fill=hair)
    dots(d, 344, 60, 14)
    d.arc([296, 378, 424, 470], 30, 150, fill=(196, 82, 72), width=11)
    d.ellipse([240, 378, 286, 410], fill=(248, 184, 160))
    d.ellipse([434, 378, 480, 410], fill=(248, 184, 160))
    return rounded(img)


def av_stas():
    skin, hair, phones = (238, 200, 168), (92, 72, 62), (84, 62, 54)
    img, d = portrait((217, 196, 169))
    d.ellipse([80, 570, 640, 1000], fill=(190, 138, 104))
    d.ellipse([214, 158, 506, 530], fill=skin)
    d.polygon([(214, 300), (232, 160), (292, 186), (330, 126), (392, 172), (452, 128), (486, 196), (506, 300),
               (452, 232), (372, 244), (288, 228)], fill=hair)
    d.arc([160, 84, 560, 500], 180, 360, fill=phones, width=26)
    d.rounded_rectangle([152, 276, 226, 424], 30, fill=phones)
    d.rounded_rectangle([494, 276, 568, 424], 30, fill=phones)
    for x in (298, 422):                                       # awake in the formal sense only
        d.line([x - 38, 346, x + 38, 346], fill=BROWN, width=11)
        d.arc([x - 34, 322, x + 34, 382], 20, 160, fill=BROWN, width=8)
    d.line([334, 452, 386, 446], fill=(160, 92, 74), width=10)
    return rounded(img)


def av_zoya():
    """Zoya's camera is on. Zoya is not in front of it."""
    fur, stripe = (240, 164, 104), (204, 118, 66)
    img, d = portrait((255, 226, 194))
    d.ellipse([110, 560, 610, 1000], fill=fur)
    d.polygon([(190, 300), (196, 96), (340, 200)], fill=fur)
    d.polygon([(530, 300), (524, 96), (380, 200)], fill=fur)
    d.polygon([(222, 240), (226, 148), (300, 204)], fill=(250, 200, 180))
    d.polygon([(498, 240), (494, 148), (420, 204)], fill=(250, 200, 180))
    d.ellipse([168, 170, 552, 560], fill=fur)
    for dx in (-48, 0, 48):
        d.line([360 + dx, 176, 360 + dx * 0.8, 246], fill=stripe, width=18)
    d.ellipse([258, 300, 324, 382], fill=(255, 250, 225))
    d.ellipse([396, 300, 462, 382], fill=(255, 250, 225))
    d.ellipse([280, 312, 304, 372], fill=BROWN)
    d.ellipse([416, 312, 440, 372], fill=BROWN)
    d.polygon([(342, 408), (378, 408), (360, 432)], fill=(206, 104, 92))
    d.arc([316, 416, 362, 468], 20, 150, fill=BROWN, width=7)
    d.arc([358, 416, 404, 468], 30, 160, fill=BROWN, width=7)
    for sign in (-1, 1):
        for dy in (-20, 12):
            d.line([360 + sign * 96, 430, 360 + sign * 214, 430 + dy], fill=(120, 84, 60), width=6)
    return rounded(img)


VIKTOR = "Виктор, руководитель"
COLLEAGUES = [("Оля", av_olya), ("Гена", av_gena), ("Лена", av_lena), ("Стас", av_stas), ("Зоя", av_zoya)]


# ---------------------------------------------------------------- call interface
def mic(c, cx, cy, h, color, strike=0.0, strike_color=None, gap_color=None):
    """Microphone icon of height h. strike 0..1 draws the diagonal bar from the top left."""
    u = h / 100
    c.rrect((cx - 17 * u, cy - 50 * u, cx + 17 * u, cy + 12 * u), 17 * u, fill=color)
    w = max(2, int(7 * u * S))
    r = 31 * u
    c.d.arc([(cx - r) * S, (cy - 2 * u - r) * S, (cx + r) * S, (cy - 2 * u + r) * S], 0, 180, fill=color, width=w)
    c.circle(cx - r + 3.5 * u, cy - 2 * u, 3.5 * u, color)
    c.circle(cx + r - 3.5 * u, cy - 2 * u, 3.5 * u, color)
    c.line(cx, cy + 29 * u, cx, cy + 44 * u, 7 * u, color)
    c.line(cx - 19 * u, cy + 46 * u, cx + 19 * u, cy + 46 * u, 7 * u, color)
    if strike > 0:
        x0, y0, x1, y1 = cx - 44 * u, cy - 48 * u, cx + 44 * u, cy + 48 * u
        x = x0 + (x1 - x0) * strike
        y = y0 + (y1 - y0) * strike
        c.line(x0 + 5 * u, y0 - 5 * u, x + 5 * u, y - 5 * u, 11 * u, gap_color)
        c.line(x0, y0, x, y, 9 * u, strike_color)


def mic_button(c, cx, cy, r, muted):
    if muted:
        c.circle(cx, cy, r, TERRA)
        mic(c, cx, cy, r * 1.15, WHITE, 1.0, WHITE, TERRA)
    else:
        c.circle(cx, cy, r, PAPER, outline=PEACH, width=max(3, r * 0.07))
        mic(c, cx, cy, r * 1.15, BROWN)


MAIN_TILE = (24, 94, 1156, 848)
MAIN_CX = (MAIN_TILE[0] + MAIN_TILE[2]) / 2
SIDE_X, SIDE_W, SIDE_TOP, SIDE_BOTTOM, SIDE_GAP = 1176, 400, 24, 976, 12
# speaker highlight per level: border width, border colour, strength of the glow around the tile
HIGHLIGHT = {0: (6, PEACH, 0), 1: (12, lerp(PEACH, CORAL, 0.5), 60), 2: (19, CORAL, 110), 3: (28, CORAL, 165)}


def main_tile(c, face, level):
    """Viktor's large tile. level 0-3 is the active-speaker highlight, None means no highlight."""
    if level:
        c.shadow(MAIN_TILE, 30, blur=14, dy=0, alpha=HIGHLIGHT[level][2], color=CORAL)
    else:
        c.shadow(MAIN_TILE, 30)
    c.rrect(MAIN_TILE, 30, fill=PAPER if level is None else PEACH_SOFT)
    if level is not None:
        width, color, _ = HIGHLIGHT[level]
        c.rrect(MAIN_TILE, 30, outline=color, width=width)
    diameter = 570
    cx, cy = MAIN_CX, MAIN_TILE[1] + 26 + diameter / 2
    c.circle(cx, cy, diameter / 2 + 10, PEACH)
    c.avatar(face, cx, cy, diameter)
    bx, by, badge = cx + diameter * 0.36, cy + diameter * 0.36, 66
    c.circle(bx, by, badge + 7, PEACH_SOFT)
    c.circle(bx, by, badge, CORAL)
    mic(c, bx, by, badge * 1.2, WHITE)
    c.text(cx, 766, VIKTOR, "bold", fit(VIKTOR, "bold", 86, MAIN_TILE[2] - MAIN_TILE[0] - 90, 60), BROWN)


def side_tile(c, y, h, name, face):
    box = (SIDE_X, y, SIDE_X + SIDE_W, y + h)
    c.shadow(box, 24)
    c.rrect(box, 24, fill=PAPER)
    diameter = h - 26
    cy = y + h / 2
    c.avatar(face, SIDE_X + 13 + diameter / 2, cy, diameter)
    text_x = SIDE_X + 13 + diameter + 16
    c.text(text_x, cy, name, "bold", fit(name, "bold", 70, SIDE_X + SIDE_W - 14 - text_x, 40), BROWN, anchor="lm")


def call_laptop(viktor, side_faces, level, muted, controls=True):
    c = Canvas(1600, 1000)
    main_tile(c, viktor, level)
    c.text(MAIN_CX, 50, CALL_TITLE, "bold", 50, BROWN)
    h = (SIDE_BOTTOM - SIDE_TOP - SIDE_GAP * (len(COLLEAGUES) - 1)) / len(COLLEAGUES)
    for i, ((name, _), face) in enumerate(zip(COLLEAGUES, side_faces)):
        side_tile(c, SIDE_TOP + i * (h + SIDE_GAP), h, name, face)
    if not controls:
        return c
    cy, r = 924, 58
    if muted:
        size = 52
        label_w = font("bold", size).getlength(MUTED_LABEL) / S
        left = MAIN_CX - (2 * r + 26 + label_w) / 2
        mic_button(c, left + r, cy, r, True)
        c.text(left + 2 * r + 26, cy, MUTED_LABEL, "bold", size, TERRA, anchor="lm")
    else:
        mic_button(c, MAIN_CX, cy, r, False)
    return c


STRIKE_STEPS = 7                     # one image per frame of the crossing out, matches MIC_STRIKE_STEPS in screens.py
SCREEN_FRAME = {0: 16, 1: 24, 2: 32, 3: 42}   # width of the speaker frame around the whole screen, per voice level
MIC_CENTER, MIC_RADIUS = (1190, 410), 290     # beside Viktor's face, so he stays visible while he talks


def screen_frame(c, level):
    c.rrect((0, 0, 1600, 1000), 0, outline=HIGHLIGHT[level][1], width=SCREEN_FRAME[level])


def mic_backdrop(call):
    """Shot 3 behind the mic: Viktor's tile stays sharp, the colleagues soften."""
    img = call.img.copy()
    box = (1166 * S, 0, 1600 * S, 1000 * S)
    side = img.crop(box).filter(ImageFilter.GaussianBlur(10 * S))
    img.paste(Image.blend(side, Image.new("RGB", side.size, CREAM), 0.55), box[:2])
    return img


def mic_large(backdrop, step, level):
    """Shot 3, on the laptop: her huge mic beside Viktor, who keeps talking. The bar starts fast."""
    t = 1 - (1 - step / STRIKE_STEPS) ** 2
    c = Canvas(1600, 1000)
    c.img.paste(backdrop)
    screen_frame(c, level)
    (cx, cy), r = MIC_CENTER, MIC_RADIUS
    fill = lerp(PAPER, TERRA, t)
    c.shadow((cx - r, cy - r, cx + r, cy + r), r, blur=26, dy=10, alpha=70)
    c.circle(cx, cy, r, fill, outline=lerp(PEACH, TERRA, t), width=14)
    icon = lerp(BROWN, WHITE, t)
    mic(c, cx, cy, r * 1.2, icon, t, icon, fill)
    if step == STRIKE_STEPS:
        size = fit(MUTED_LABEL, "bold", 92, 1240, 70)
        half = font("bold", size).getlength(MUTED_LABEL) / S / 2 + 56
        pill = (800 - half, 818, 800 + half, 946)
        c.shadow(pill, 64, blur=14, dy=5, alpha=80)
        c.rrect(pill, 64, fill=TERRA)
        c.text(800, 880, MUTED_LABEL, "bold", size, WHITE)
    return c


def connecting_laptop():
    """Shot 0, before the call: readable from across the room."""
    c = Canvas(1600, 1000)
    c.gradient((255, 243, 231), (255, 216, 188))
    cx, cy, ring = 800, 350, 130
    for i in range(10):
        angle = 2 * math.pi * i / 10 - math.pi / 2
        c.circle(cx + ring * math.cos(angle), cy + ring * math.sin(angle), 25, lerp(PEACH_SOFT, CORAL, i / 9))
    c.text(800, 670, CONNECTING, "bold", fit(CONNECTING, "bold", 150, 1340, 90), BROWN)
    c.text(800, 815, CALL_TITLE, "demi", 72, TERRA)
    return c


def caption_evening():
    """Transparent 1080x1920: a cozy pill in the upper part, below the Reels top bar and above her head."""
    w, h = 1080 * S, 1920 * S
    size = fit(CAPTION_EVENING, "serif", 96, 720, 64)
    f = font("serif", size)
    half = (f.getlength(CAPTION_EVENING) / S + 128) / 2
    box = [(540 - half) * S, 256 * S, (540 + half) * S, 424 * S]
    radius = 84 * S
    pill = Image.new("L", (w, h), 0)
    ImageDraw.Draw(pill).rounded_rectangle(box, radius, fill=255)
    shade = Image.new("L", (w, h), 0)
    ImageDraw.Draw(shade).rounded_rectangle([box[0], box[1] + 10 * S, box[2], box[3] + 10 * S], radius, fill=110)
    shade = shade.filter(ImageFilter.GaussianBlur(18 * S))
    rgb = Image.new("RGB", (w, h), (120, 72, 44))
    rgb.paste(PAPER, (0, 0, w, h), pill)
    draw = ImageDraw.Draw(rgb)
    draw.rounded_rectangle(box, radius, outline=PEACH, width=5 * S)
    draw.text((540 * S, 340 * S), CAPTION_EVENING, font=f, fill=DEEP, anchor="mm")
    alpha = Image.fromarray(np.maximum(np.asarray(pill), np.asarray(shade)))
    rgb = rgb.resize((1080, 1920), Image.LANCZOS)
    rgb.putalpha(alpha.resize((1080, 1920), Image.LANCZOS))
    OUT.mkdir(parents=True, exist_ok=True)
    rgb.save(OUT / "caption-evening.png", optimize=True)
    print("wrote caption-evening")


def evening_desktop():
    c = Canvas(1600, 1000)
    c.gradient((246, 203, 168), (214, 150, 126))
    c.glow(1130, 610, 150, (255, 226, 190), alpha=110, blur=50)
    c.sun(1130, 610, 130, (255, 222, 178), (246, 170, 124))
    c.hill(700, 26, 1500, 0.8, (190, 122, 104))
    c.hill(790, 22, 1100, 2.6, (160, 100, 90))
    c.hill(885, 18, 1700, 4.4, (128, 82, 76))
    box = (370, 300, 1230, 640)
    c.shadow(box, 44, blur=26, dy=10, alpha=70)
    c.rrect(box, 44, fill=PAPER)
    c.circle(800, 400, 58, CORAL)
    c.line(772, 402, 794, 424, 13, WHITE)
    c.line(794, 424, 832, 378, 13, WHITE)
    c.text(800, 545, CALL_ENDED, "bold", fit(CALL_ENDED, "bold", 84, 780, 56), BROWN)
    return c


# ---------------------------------------------------------------- the finished presentation
def presentation_full():
    c = Canvas(1080, 1920)
    c.gradient((255, 243, 231), (255, 216, 188))
    cx, cy, r = 540, 470, 270
    c.glow(cx, cy, r + 30, (255, 196, 156), alpha=120, blur=70)
    c.circle(cx, cy, r + 118, outline=(255, 226, 204), width=4)
    c.circle(cx, cy, r + 62, outline=(255, 210, 180), width=5)
    c.sun(cx, cy, r, (255, 196, 150), (238, 124, 84))
    size = fit(HEADLINE[1], "serif", 224, 900, 130)
    c.text(540, 955, HEADLINE[0], "serif", size, DEEP, anchor="ms")
    c.text(540, 955 + size * 1.0, HEADLINE[1], "serif", size, DEEP, anchor="ms")
    c.line(470, 1248, 610, 1248, 7, CORAL)
    sub = min(fit(line, "medium", 58, 900, 40) for line in SUBTITLE)
    c.text(540, 1330, SUBTITLE[0], "medium", sub, BROWN, anchor="ms")
    c.text(540, 1330 + sub * 1.3, SUBTITLE[1], "medium", sub, BROWN, anchor="ms")
    c.hill(1560, 30, 1300, 0.6, (250, 190, 150))
    c.hill(1670, 28, 950, 2.4, (240, 158, 120))
    c.hill(1790, 24, 1500, 4.2, (216, 122, 90))
    return c


def presentation_laptop():
    c = Canvas(1600, 1000)
    c.gradient((255, 243, 231), (255, 216, 188))
    cx, cy, r = 1210, 390, 215
    c.glow(cx, cy, r + 24, (255, 196, 156), alpha=120, blur=56)
    c.circle(cx, cy, r + 105, outline=(255, 226, 204), width=4)
    c.circle(cx, cy, r + 52, outline=(255, 210, 180), width=5)
    c.sun(cx, cy, r, (255, 196, 150), (238, 124, 84))
    c.hill(800, 20, 1500, 0.6, (250, 190, 150))
    c.hill(875, 20, 1100, 2.4, (240, 158, 120))
    c.hill(950, 16, 1700, 4.2, (216, 122, 90))
    size = fit(HEADLINE[1], "serif", 190, 750, 110)
    c.text(110, 300, HEADLINE[0], "serif", size, DEEP, anchor="ls")
    c.text(110, 300 + size, HEADLINE[1], "serif", size, DEEP, anchor="ls")
    c.line(116, 548, 236, 548, 6, CORAL)
    sub = min(fit(line, "medium", 48, 760, 34) for line in SUBTITLE)
    c.text(110, 622, SUBTITLE[0], "medium", sub, BROWN, anchor="ls")
    c.text(110, 622 + sub * 1.3, SUBTITLE[1], "medium", sub, BROWN, anchor="ls")
    return c


def main():
    viktor = av_viktor()
    side_faces = [make() for _, make in COLLEAGUES]
    connecting_laptop().save("laptop_connecting")
    call_laptop(viktor, side_faces, None, muted=False).save("laptop_call")
    call_laptop(viktor, side_faces, None, muted=True).save("laptop_muted")
    for level in HIGHLIGHT:
        call_laptop(viktor, side_faces, level, muted=False).save(f"laptop_viktor_{level}")  # the full-screen frame is only in shot 3
        backdrop = mic_backdrop(call_laptop(viktor, side_faces, level, muted=False, controls=False))
        for step in range(STRIKE_STEPS + 1):
            mic_large(backdrop, step, level).save(f"laptop_mic_{step}_{level}")
    evening_desktop().save("laptop_evening")
    presentation_laptop().save("laptop_presentation")
    presentation_full().save("full_presentation")
    caption_evening()


if __name__ == "__main__":
    main()
