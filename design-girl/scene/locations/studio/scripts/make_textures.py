#!/usr/bin/env python3
"""Flat PNG textures for the Designer's studio set (posters, screens, plaque, ribbon).

    python3 scripts/make_textures.py            # writes every texture
    python3 scripts/make_textures.py eyechart   # only names containing "eyechart"

Writes to ../textures/. File names and pixel sizes are a contract with the Blender
scene, which maps them onto flat planes: do not change them.

Needs Pillow and numpy, and the macOS system fonts below. A missing font is an error, never a
silent substitution (the eye chart must be in Comic Sans).
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parents[1] / "textures"

COMIC = "/System/Library/Fonts/Supplemental/Comic Sans MS.ttf"
HELVETICA_NEUE = "/System/Library/Fonts/HelveticaNeue.ttc"
# Face indices inside HelveticaNeue.ttc (checked with ImageFont.getname()).
HN_REGULAR, HN_BOLD, HN_LIGHT, HN_MEDIUM = 0, 1, 7, 10
# Helvetica Bold (index 1 of Helvetica.ttc) for the Cyrillic poster: its "б" is sturdier at
# poster size than Helvetica Neue Bold's, whose flag joins the bowl with a hairline.
HELVETICA = "/System/Library/Fonts/Helvetica.ttc"
HV_BOLD = 1

INK = (0x1E, 0x1E, 0x1E)
PAPER = (0xFD, 0xFC, 0xFA)  # near-white poster paper
BLUE = (0x17, 0x69, 0xFF)
WHITE = (255, 255, 255)

# Poster accents, from the studio's palette. One per poster, used sparingly (see POSTER_ACCENTS).
COBALT = BLUE
PINK = (0xEA, 0x4C, 0x89)
TERRACOTTA = (0xD9, 0x77, 0x57)
PEACH = (0xF5, 0xB3, 0x8A)
LILAC = (0xC9, 0xA7, 0xF0)

# poster file: (paper colour, accent colour, what carries the accent); read by check_textures.py.
POSTER_ACCENTS = {
    "poster_eyechart.png": (PAPER, COBALT, "last row DESIGNER"),
    "poster_lorem.png": (PEACH, PAPER, "opening quote mark, white on peach paper"),
    "poster_chtoby.png": (PAPER, PINK, "question mark"),
    "poster_kerning.png": (LILAC, PINK, "block filling the R-N hole, on lilac paper"),
    "poster_rams.png": (PAPER, TERRACOTTA, "comma in 'Less, but better'"),
}


def font(path, size, index=0):
    if not Path(path).exists():
        sys.exit(f"missing font: {path}")
    return ImageFont.truetype(path, size, index=index)


def cap_height_ratio(path, index=0):
    """Cap height of the face as a fraction of the font size, measured on 'H'."""
    f = font(path, 1000, index)
    l, t, r, b = f.getbbox("H", anchor="ls")
    return -t / 1000


def glyph_region(text, f, origin, size, grow=2):
    """Bool mask of where `text` (anchor "ls" at origin) puts ink, grown by `grow` px."""
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).text(origin, text, font=f, fill=255, anchor="ls")
    return np.asarray(m.filter(ImageFilter.MaxFilter(2 * grow + 1))) > 0


def recolour(img, region, accent):
    """Turns the ink inside `region` into `accent`, keeping each pixel's anti-aliased coverage."""
    a = np.asarray(img).astype(np.float32)
    paper, ink = np.array(PAPER, np.float32), np.array(INK, np.float32)
    t = np.clip((paper.mean() - a.mean(-1)) / (paper.mean() - ink.mean()), 0, 1)[..., None]
    a[region] = (paper + t * (np.array(accent, np.float32) - paper))[region]
    return Image.fromarray(np.round(a).astype(np.uint8), "RGB")


def last_glyph_origin(text, f, x):
    """x of the last glyph of `text` set from x, kerning included (same in basic and raqm layout)."""
    return x + f.getlength(text) - f.getlength(text[-1])


def save(img, name, size):
    assert img.size == size, (name, img.size, size)
    OUT.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(OUT / name, optimize=True)
    print(f"{name:28s} {size[0]} x {size[1]}")


# ---------------------------------------------------------------- 1. eye chart (Sivtsev layout)

EYE_ROWS = [
    "CO", "MIC", "SANS", "ISTHE", "BESTF", "ONTINT",
    "HEWHOL", "EWORLD!", "IFYOUCA", "NREADTHI", "SYOUAREA", "DESIGNER",
]
EYE_D = ["50.0", "25.0", "16.67", "12.5", "10.0", "8.33", "7.14", "6.25", "5.55", "5.0", "3.33", "2.5"]
EYE_V = ["0.1", "0.2", "0.3", "0.4", "0.5", "0.6", "0.7", "0.8", "0.9", "1.0", "1.5", "2.0"]
EYE_COUNTS = [2, 3, 4, 5, 5, 6, 6, 7, 7, 8, 8, 8]


def poster_eyechart():
    W, H = 1200, 1800
    assert [len(r) for r in EYE_ROWS] == EYE_COUNTS
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    cap = cap_height_ratio(COMIC)

    # Caption, set small like the print line on a real chart.
    d.text((W / 2, 92), "Table for testing visual acuity  ·  read from 5 m",
           font=font(COMIC, 26), fill=INK, anchor="ms")
    d.line([(90, 118), (W - 90, 118)], fill=INK, width=2)

    # Cap heights shrink with acuity like the real chart (size ~ 1/V), softened by an exponent so
    # row 12 stays readable as letters on a 1200 px poster: 190 px at V=0.1 down to ~23 px at 2.0.
    vs = [float(v) for v in EYE_V]
    heights = [190 * (0.1 / v) ** 0.708 for v in vs]

    # Row gaps: a constant part plus a part proportional to the neighbouring rows' size, so big
    # rows breathe more without the small rows getting crammed together at the bottom.
    top, bottom, base_gap = 175, 1712, 44
    n_gaps = len(heights) - 1
    gaps_weight = sum((heights[i] + heights[i + 1]) / 2 for i in range(n_gaps))
    k = (bottom - top - sum(heights) - base_gap * n_gaps) / gaps_weight

    label_font = font(COMIC, 24)
    y = top
    for i, (row, h) in enumerate(zip(EYE_ROWS, heights)):
        baseline = y + h
        f = font(COMIC, round(h / cap))
        pitch = 1.55 * h
        x0 = W / 2 - pitch * (len(row) - 1) / 2
        for j, ch in enumerate(row):
            # The verdict row, DESIGNER, in cobalt: the one word on the chart that is about you.
            fill = COBALT if row == "DESIGNER" else INK
            d.text((x0 + j * pitch, baseline), ch, font=f, fill=fill, anchor="ms")
        mid = baseline - h / 2
        d.text((84, mid), f"D = {EYE_D[i]}", font=label_font, fill=INK, anchor="lm")
        d.text((W - 84, mid), f"V = {EYE_V[i]}", font=label_font, fill=INK, anchor="rm")
        if i + 1 < len(heights):
            y = baseline + base_gap + k * (h + heights[i + 1]) / 2
    save(img, "poster_eyechart.png", (W, H))


# ---------------------------------------------------------------- 2-4. Swiss type posters

def poster_lorem():
    W, H = 1200, 1800
    img = Image.new("RGB", (W, H), PEACH)   # warm "sunset" paper of a motivational poster
    d = ImageDraw.Draw(img)
    x = 110
    big = font(HELVETICA_NEUE, 176, HN_BOLD)
    small = font(HELVETICA_NEUE, 30, HN_REGULAR)
    # Small top line, then lots of air, then the quote low on the sheet, flush left.
    d.text((x, 150), "No. 01", font=small, fill=INK, anchor="ls")
    d.text((W - 110, 150), "Daily motivation", font=small, fill=INK, anchor="rs")
    # The oversized quote mark knocked out in white: pure decoration on a quote that says nothing.
    d.text((x - 8, 1010), "“", font=font(HELVETICA_NEUE, 260, HN_BOLD), fill=PAPER, anchor="ls")
    lines = ["Lorem", "ipsum", "dolor sit", "amet."]
    lead = 168
    base = 1080
    for n, line in enumerate(lines):
        d.text((x - 6, base + n * lead), line, font=big, fill=INK, anchor="ls")
    d.line([(x, 1660), (x + 120, 1660)], fill=INK, width=4)
    d.text((x, 1708), "Marcus Tullius Cicero, roughly", font=small, fill=INK, anchor="ls")
    save(img, "poster_lorem.png", (W, H))


def poster_chtoby():
    W, H = 1200, 1800
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    f = font(HELVETICA, 300, HV_BOLD)
    # Two stacked lines, flush left, sitting on the optical centre of the sheet.
    d.text((100, 860), "Чтобы", font=f, fill=INK, anchor="ls")
    d.text((100, 1150), "что?", font=f, fill=INK, anchor="ls")
    # The question is the whole poster: the question mark in pink.
    q = glyph_region("?", f, (last_glyph_origin("что?", f, 100), 1150), (W, H))
    img = recolour(img, q, PINK)
    save(img, "poster_chtoby.png", (W, H))


def poster_kerning():
    W, H = 1200, 1800
    img = Image.new("RGB", (W, H), LILAC)
    d = ImageDraw.Draw(img)
    f = font(HELVETICA_NEUE, 186, HN_BOLD)
    # Each letter placed by hand with deliberately wrong gaps (px, can be negative): K and E
    # collide, a hole between R and N (the "space"), N and I jammed, I and N too loose.
    letters = "KERNING"
    gaps = [-24, 4, 128, -10, 30, 2]  # after K, E, R, N, I, N
    widths = [f.getlength(c) for c in letters]
    total = sum(widths) + sum(gaps)
    assert total < W - 160, total
    x = (W - total) / 2
    baseline = 1000
    xs = []
    for n, c in enumerate(letters):
        xs.append(x)
        d.text((x, baseline), c, font=f, fill=INK, anchor="ls")
        x += widths[n] + (gaps[n] if n < len(gaps) else 0)
    # Expose the error the way a design tool shows spacing: fill the hole between R and N, ink
    # edge to ink edge, cap height tall, in pink.
    cap = round(-f.getbbox("H", anchor="ls")[1])
    band = np.asarray(img)[baseline - cap:baseline].astype(int)
    empty = (np.abs(band - np.array(LILAC)).max(-1) <= 8).all(0)   # columns with no ink at all
    r_end, n_start = int(xs[2] + widths[2] * 0.5), int(xs[3] + widths[3] * 0.5)
    hole = [c for c in range(r_end, n_start) if empty[c]]
    assert hole and hole[-1] - hole[0] + 1 == len(hole), "R-N hole is not one clean run"
    d.rectangle((hole[0], baseline - cap, hole[-1], baseline - 1), fill=PINK)
    save(img, "poster_kerning.png", (W, H))


# ---------------------------------------------------------------- 5. Rams portrait, pixel art

def rams_pixels():
    """64 x 64 greyscale pixel portrait: older man, grey swept-back hair, dark thick glasses."""
    g = Image.new("L", (64, 64), 0x84)  # mid-grey backdrop
    d = ImageDraw.Draw(g)
    HAIR, HAIR_HI, HAIR_SH = 0xDC, 0xF2, 0xB2
    SKIN, SKIN_SH, SKIN_HI = 0xB4, 0x9A, 0xC4
    RIM, JACKET, SHIRT = 0x10, 0x22, 0xEA

    # Jacket and shirt.
    d.ellipse((4, 51, 60, 92), fill=JACKET)
    d.rectangle((26, 42, 38, 54), fill=SKIN_SH)  # neck
    d.polygon([(25, 51), (39, 51), (32, 63)], fill=SHIRT)
    d.polygon([(28, 51), (36, 51), (32, 57)], fill=SKIN_SH)
    d.line([(24, 52), (31, 63)], fill=0x3A)
    d.line([(40, 52), (33, 63)], fill=0x3A)
    # Ears.
    d.ellipse((16, 26, 22, 37), fill=SKIN_SH)
    d.ellipse((42, 26, 48, 37), fill=SKIN_SH)
    # Head: slightly long face, narrower chin.
    d.ellipse((19, 9, 45, 49), fill=SKIN)
    d.polygon([(41, 20), (45, 28), (43, 42), (38, 48), (40, 30)], fill=SKIN_SH)  # shaded side
    # Hair: combed straight back, receding at the temples, short and grey over the ears.
    d.ellipse((18, 4, 46, 24), fill=HAIR)
    d.rectangle((18, 14, 20, 25), fill=HAIR)
    d.rectangle((44, 14, 46, 25), fill=HAIR_SH)
    d.polygon([(21, 25), (21, 18), (24, 14), (40, 14), (43, 18), (43, 25)], fill=SKIN)  # forehead
    d.rectangle((26, 16, 30, 17), fill=SKIN_HI)
    d.polygon([(41, 17), (43, 19), (43, 25), (41, 25)], fill=SKIN_SH)
    d.rectangle((29, 18, 35, 18), fill=0xA6)
    for x in (24, 28, 32, 36, 40):  # comb lines
        d.line([(x, 6), (x - 2, 12)], fill=HAIR_HI)
    d.line([(45, 11), (45, 20)], fill=HAIR_SH)
    # Forehead lines of an older face.
    d.rectangle((27, 21, 37, 21), fill=0xA6)
    # Brows.
    d.rectangle((23, 25, 30, 25), fill=0x7C)
    d.rectangle((34, 25, 41, 25), fill=0x7C)
    # Glasses: thick dark rims, square-ish, bridge and arms to the ears.
    for x0 in (21, 33):
        d.rectangle((x0, 27, x0 + 10, 33), fill=RIM)
        d.rectangle((x0 + 2, 29, x0 + 8, 32), fill=0xC2)
        d.point((x0 + 7, 29), fill=0xEE)  # glint
    d.rectangle((31, 28, 33, 29), fill=RIM)
    d.rectangle((18, 28, 21, 29), fill=RIM)
    d.rectangle((43, 28, 46, 29), fill=RIM)
    d.rectangle((25, 30, 27, 31), fill=0x30)  # eyes
    d.rectangle((37, 30, 39, 31), fill=0x30)
    # Nose, lines, mouth.
    d.line([(33, 34), (33, 38)], fill=SKIN_SH)
    d.rectangle((30, 39, 34, 39), fill=0x88)
    d.line([(27, 37), (26, 42)], fill=SKIN_SH)
    d.line([(38, 37), (39, 42)], fill=SKIN_SH)
    d.rectangle((28, 43, 36, 43), fill=0x66)
    d.rectangle((29, 46, 35, 46), fill=SKIN_SH)  # chin crease
    return g


def poster_rams():
    W, H = 1200, 1800
    img = Image.new("RGB", (W, H), PAPER)
    cell = 14
    pix = rams_pixels().resize((64 * cell, 64 * cell), Image.NEAREST).convert("RGB")
    x0 = (W - pix.width) // 2
    img.paste(pix, (x0, 250))
    d = ImageDraw.Draw(img)
    big = font(HELVETICA_NEUE, 112, HN_BOLD)
    d.text((x0, 1380), "Less, but better", font=big, fill=INK, anchor="ls")
    d.text((x0, 1450), "Dieter Rams", font=font(HELVETICA_NEUE, 34, HN_REGULAR), fill=INK, anchor="ls")
    # Braun grey with one small orange control: the comma, the pause in "Less, but", in terracotta.
    comma = glyph_region(",", big, (last_glyph_origin("Less,", big, x0), 1380), (W, H))
    img = recolour(img, comma, TERRACOTTA)
    save(img, "poster_rams.png", (W, H))


# ---------------------------------------------------------------- 6. Focus screens

def focus_screen(name, W, H, radius):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.hypot(xx - W / 2, yy - H / 2)
    # Soft-edged disc plus a wide exponential halo.
    core = 1 / (1 + np.exp(np.clip((r - radius) / (radius * 0.035), -60, 60)))
    halo = 0.55 * np.exp(-np.maximum(r - radius, 0) / (radius * 0.45))
    v = np.clip(core * 0.97 + halo * (1 - core), 0, 1)
    v = (v ** 1.15 * 255).round().astype(np.uint8)
    save(Image.fromarray(v, "L"), name, (W, H))


def screens_focus():
    focus_screen("screen_focus_tablet.png", 1200, 1600, 230)
    focus_screen("screen_focus_phone.png", 900, 1950, 190)


# ---------------------------------------------------------------- 7. laptop placeholder

def supersampled(W, H, bg, draw_fn, s=4):
    big = Image.new("RGB", (W * s, H * s), bg)
    draw_fn(ImageDraw.Draw(big), s)
    return big.resize((W, H), Image.LANCZOS)


def screen_laptop():
    W, H = 1600, 1000
    LINE, PANEL, BAR, SHAPE, SHAPE2 = (0xE4, 0xE4, 0xE4), (0xF6, 0xF6, 0xF6), (0xE2, 0xE2, 0xE2), (0xE9, 0xE9, 0xE9), (0xDD, 0xDD, 0xDD)

    def draw(d, s):
        S = lambda *v: [c * s for c in v]
        # Toolbar strip.
        d.rectangle(S(0, 0, W, 56), fill=PANEL)
        d.line(S(0, 56, W, 56), fill=LINE, width=2 * s)
        for i in range(6):
            d.rounded_rectangle(S(24 + i * 44, 16, 24 + i * 44 + 26, 40), radius=6 * s, fill=BAR)
        d.rounded_rectangle(S(W - 140, 16, W - 24, 40), radius=12 * s, fill=BAR)
        # Left layers panel.
        d.rectangle(S(0, 57, 280, H), fill=PANEL)
        d.line(S(280, 57, 280, H), fill=LINE, width=2 * s)
        for i in range(9):
            y = 90 + i * 40
            indent = 24 if i in (0, 4) else 48
            d.rounded_rectangle(S(indent, y, indent + 14, y + 14), radius=3 * s, fill=BAR)
            d.rounded_rectangle(S(indent + 26, y + 2, indent + 26 + (150 - (i * 37) % 70), y + 12),
                                radius=5 * s, fill=BAR)
        # Right properties panel.
        d.rectangle(S(W - 260, 57, W, H), fill=PANEL)
        d.line(S(W - 260, 57, W - 260, H), fill=LINE, width=2 * s)
        for i in range(7):
            y = 92 + i * 56
            d.rounded_rectangle(S(W - 236, y, W - 236 + 70, y + 10), radius=5 * s, fill=BAR)
            d.rounded_rectangle(S(W - 236, y + 20, W - 24, y + 38), radius=6 * s, fill=(0xEE, 0xEE, 0xEE))
        # Canvas: one blank artboard with two pale shapes.
        d.rectangle(S(281, 57, W - 261, H), fill=(0xFB, 0xFB, 0xFB))
        ax0, ay0, ax1, ay1 = 420, 140, 1200, 900
        d.rectangle(S(ax0, ay0, ax1, ay1), fill=WHITE, outline=LINE, width=2 * s)
        d.ellipse(S(500, 230, 760, 490), fill=SHAPE)
        d.rounded_rectangle(S(820, 300, 1110, 560), radius=28 * s, fill=SHAPE2)
        d.rounded_rectangle(S(500, 620, 1110, 660), radius=20 * s, fill=SHAPE)
        d.rounded_rectangle(S(500, 690, 860, 720), radius=15 * s, fill=(0xF0, 0xF0, 0xF0))

    save(supersampled(W, H, WHITE, draw), "screen_laptop.png", (W, H))


# ---------------------------------------------------------------- 8. plaque

def plaque_awwwards():
    W, H = 1200, 300
    rng = np.random.default_rng(7)
    # Brushed light metal: vertical gradient plus horizontal streaks.
    base = np.linspace(222, 196, H)[:, None] * np.ones((1, W))
    streaks = rng.normal(0, 1, (H, 1)) * 3.0 + rng.normal(0, 1, (H, W)) * 1.2
    metal = np.clip(base + streaks, 0, 255)
    rgb = np.stack([metal, metal, metal * 0.985], -1).astype(np.uint8)
    img = Image.fromarray(rgb, "RGB")
    d = ImageDraw.Draw(img)
    # Bevel and an engraved inner border.
    d.rectangle((0, 0, W - 1, H - 1), outline=(0xF2, 0xF2, 0xF0), width=3)
    d.line([(0, H - 2), (W - 1, H - 2)], fill=(0x9A, 0x9A, 0x96), width=3)
    d.line([(W - 2, 0), (W - 2, H - 1)], fill=(0x9A, 0x9A, 0x96), width=3)
    d.rectangle((30, 30, W - 31, H - 31), outline=(0x6E, 0x6E, 0x6A), width=2)
    d.rectangle((31, 32, W - 30, H - 29), outline=(0xF0, 0xF0, 0xEC), width=1)
    d.rectangle((30, 30, W - 31, H - 31), outline=(0x6E, 0x6E, 0x6A), width=2)
    # Screws.
    for cx in (62, W - 62):
        d.ellipse((cx - 13, H / 2 - 13, cx + 13, H / 2 + 13), fill=(0xB8, 0xB8, 0xB4), outline=(0x80, 0x80, 0x7C), width=2)
        d.line([(cx - 8, H / 2 + 5), (cx + 8, H / 2 - 5)], fill=(0x70, 0x70, 0x6C), width=3)
    # Engraved text: light highlight below, dark cut on top.
    text = "reserved for Awwwards SOTD"
    f = font(HELVETICA_NEUE, 66, HN_MEDIUM)
    c = (W / 2, H / 2 + 2)
    d.text((c[0], c[1] + 2), text, font=f, fill=(0xF4, 0xF4, 0xF0), anchor="mm")
    d.text(c, text, font=f, fill=(0x2A, 0x2A, 0x28), anchor="mm")
    save(img, "plaque_awwwards.png", (W, H))


# ---------------------------------------------------------------- 9. ribbon

def ribbon_featured():
    W, H = 800, 1000
    DARK = (0x0F, 0x52, 0xD1)
    LIGHT = (0x4A, 0x8B, 0xFF)
    cx, cy = 400, 400

    def draw(d, s):
        S = lambda pts: [(x * s, y * s) for x, y in pts]
        # Tails behind the rosette, V-notched ends.
        for m in (1, -1):  # left tail, then its mirror
            X = lambda x: cx + m * (x - cx)
            tail = [(X(305), 470), (X(395), 490), (X(305), 905), (X(266), 852), (X(215), 885)]
            d.polygon(S(tail), fill=BLUE)
            fold = [(X(305), 470), (X(395), 490), (X(380), 600), (X(282), 570)]
            d.polygon(S(fold), fill=DARK)  # shadow where the tail tucks under the rosette
        # Pleated outer ring: a many-pointed star.
        n, r0, r1 = 36, 300, 270
        pts = []
        for i in range(2 * n):
            a = math.pi * i / n
            r = r0 if i % 2 == 0 else r1
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        d.polygon(S(pts), fill=BLUE)
        for i in range(0, 2 * n, 2):  # pleat shading
            a0, a1 = math.pi * i / n, math.pi * (i + 1) / n
            d.polygon(S([(cx + r1 * 0.78 * math.cos(a1), cy + r1 * 0.78 * math.sin(a1)),
                         (cx + r0 * math.cos(a0), cy + r0 * math.sin(a0)),
                         (cx + r1 * math.cos(a1), cy + r1 * math.sin(a1))]), fill=DARK)
        # Inner medallion with a white rule.
        d.ellipse([(cx - 215) * s, (cy - 215) * s, (cx + 215) * s, (cy + 215) * s], fill=BLUE)
        d.ellipse([(cx - 195) * s, (cy - 195) * s, (cx + 195) * s, (cy + 195) * s], outline=WHITE, width=6 * s)
        d.ellipse([(cx - 180) * s, (cy - 180) * s, (cx + 180) * s, (cy + 180) * s], outline=LIGHT, width=3 * s)

    img = supersampled(W, H, WHITE, draw)
    d = ImageDraw.Draw(img)
    d.text((cx, cy + 4), "Featured", font=font(HELVETICA_NEUE, 70, HN_BOLD), fill=WHITE, anchor="mm")
    save(img, "ribbon_featured.png", (W, H))


ALL = [poster_eyechart, poster_lorem, poster_chtoby, poster_kerning, poster_rams,
       screens_focus, screen_laptop, plaque_awwwards, ribbon_featured]

if __name__ == "__main__":
    only = sys.argv[1:]
    for fn in ALL:
        if not only or any(o in fn.__name__ for o in only):
            fn()
