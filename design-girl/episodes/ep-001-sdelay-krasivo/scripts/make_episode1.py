#!/usr/bin/env python3
"""Images and sounds for Episode 1 "Сделай красиво" (timeline: episode1_timeline.py).

    python3 scripts/make_episode1.py           # writes everything, then runs the checks
    python3 scripts/make_episode1.py --check   # checks only

Writes overlays/ here and the shared sounds to scene/audio/:
  screens/screen_<hash>.png  laptop screen states, 1600 x 1000 (same aspect as the laptop screen)
  overlay_caption.png, overlay_bubble.png, overlay_card.png   1080 x 1920 RGBA, full-frame overlays
  sounds/*.wav               48 kHz mono: tick, enter, chime, pop, disco (the disco cuts hard at 13 s)
  screen_timeline.json       [[first frame, last frame, file], ...] read by scripts/episode1.py
"""
import colorsys
import json
import math
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scene" / "locations" / "studio" / "scripts"))
import episode1_timeline as TL  # noqa: E402
from make_textures import HELVETICA_NEUE, HN_BOLD, HN_MEDIUM, HN_REGULAR, INK, PAPER, PEACH, font  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "overlays"
SCREENS = OUT / "screens"
AUDIO = Path(__file__).resolve().parents[3] / "scene" / "audio"


def sound_path(name):
    """Shared sounds: the disco loop is music, the rest are effects."""
    return AUDIO / ("music" if name == "disco.wav" else "sfx") / name

SW, SH = 1600, 1000          # screen
VW, VH = 1080, 1920          # video frame (overlays)
SAFE = (70, 260, VW - 70, VH - 420)   # x0, y0, x1, y1 kept clear of phone UI in vertical feeds
TERRA = (0xD9, 0x77, 0x57)
PEACH_LIGHT = (0xFB, 0xE6, 0xD6)
CHAT_BG = (0xFA, 0xF8, 0xF5)
LINE = (0xE2, 0xDE, 0xD8)
GREY_TXT = (0x8A, 0x86, 0x80)

SITE = (0, 56, 1040, SH)     # site preview area
CHAT = (1040, 56, SW, SH)    # chat panel
INPUT = (1062, 840, SW - 22, SH - 22)


# ---------------------------------------------------------------- text helpers
def wrap(text, f, width):
    words, lines, cur = text.split(" "), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if f.getlength(t) <= width:
            cur = t
        else:
            assert cur, ("word too long", w)
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def missing_glyphs(text, f):
    """Characters the font draws as its .notdef box."""
    def raster(c):
        im = Image.new("L", (240, 240), 0)
        ImageDraw.Draw(im).text((20, 200), c, font=f, fill=255, anchor="ls")
        return np.asarray(im).tobytes()
    ref = raster("￿")
    return [c for c in set(text) if c.strip() and raster(c) == ref]


# ---------------------------------------------------------------- sites (1040 x 944)
def site_grey(d):
    x0, y0, x1, y1 = SITE
    d.rectangle(SITE, fill=(0xE4, 0xE4, 0xE4))
    d.rectangle((x0, y0, x1, y0 + 70), fill=(0xC8, 0xC8, 0xC8))
    for i in range(4):
        d.rectangle((x1 - 90 - i * 110, y0 + 28, x1 - 30 - i * 110, y0 + 42), fill=(0xA8, 0xA8, 0xA8))
    d.rectangle((x0 + 60, y0 + 130, x1 - 60, y0 + 420), fill=(0xCF, 0xCF, 0xCF))
    d.rectangle((x0 + 60, y0 + 460, x0 + 600, y0 + 490), fill=(0xA8, 0xA8, 0xA8))
    for i in range(3):
        d.rectangle((x0 + 60, y0 + 520 + i * 34, x1 - 120 - i * 90, y0 + 536 + i * 34), fill=(0xBC, 0xBC, 0xBC))
    for i in range(3):
        cx = x0 + 60 + i * 316
        d.rectangle((cx, y0 + 660, cx + 288, y0 + 880), fill=(0xD2, 0xD2, 0xD2))


def site_clean(d):
    x0, y0, x1, y1 = SITE
    d.rectangle(SITE, fill=(0xFF, 0xFF, 0xFF))
    d.ellipse((x0 + 60, y0 + 34, x0 + 92, y0 + 66), fill=PEACH)                      # logo
    for i in range(3):
        d.rectangle((x1 - 120 - i * 120, y0 + 46, x1 - 60 - i * 120, y0 + 52), fill=INK)
    d.line((x0 + 60, y0 + 100, x1 - 60, y0 + 100), fill=LINE, width=2)
    d.ellipse((x0 + 600, y0 + 170, x0 + 940, y0 + 510), fill=PEACH)                  # hero shape
    d.rectangle((x0 + 60, y0 + 210, x0 + 520, y0 + 262), fill=INK)                   # headline
    d.rectangle((x0 + 60, y0 + 284, x0 + 420, y0 + 336), fill=INK)
    for i in range(3):
        d.rectangle((x0 + 60, y0 + 380 + i * 28, x0 + 500 - i * 60, y0 + 390 + i * 28), fill=(0xB8, 0xB4, 0xAE))
    d.rounded_rectangle((x0 + 60, y0 + 480, x0 + 250, y0 + 536), radius=28, fill=PEACH)  # button
    for i in range(3):
        cx = x0 + 60 + i * 316
        d.rectangle((cx, y0 + 640, cx + 288, y0 + 642), fill=INK)
        d.rectangle((cx, y0 + 670, cx + 200, y0 + 680), fill=(0xB8, 0xB4, 0xAE))
        d.rectangle((cx, y0 + 700, cx + 240, y0 + 710), fill=(0xB8, 0xB4, 0xAE))
        if i == 1:
            d.ellipse((cx + 250, y0 + 600, cx + 280, y0 + 630), fill=PEACH)


def site_rainbow(img, k):
    """Acid rainbow: hue-cycling gradient, bouncing neon blocks, glitter and blinking stars."""
    x0, y0, x1, y1 = SITE
    w, h = x1 - x0, y1 - y0
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    hue = ((xx + yy) / (w + h) * 1.5 + k * 0.25) % 1.0
    rgb = np.zeros((h, w, 3), np.float32)
    i = np.floor(hue * 6).astype(int) % 6
    f = hue * 6 - np.floor(hue * 6)
    q, t = 1 - f, f
    for n, (r, g, b) in enumerate([(1, t, 0), (q, 1, 0), (0, 1, t), (0, q, 1), (t, 0, 1), (1, 0, q)]):
        m = i == n
        for c, v in enumerate((r, g, b)):
            rgb[..., c][m] = (v if isinstance(v, (int, float)) else v[m])
    rgb = 0.25 + 0.75 * rgb
    img.paste(Image.fromarray((rgb * 255).astype(np.uint8), "RGB"), (x0, y0))
    d = ImageDraw.Draw(img)
    neon = [(0xFF, 0x2B, 0xD6), (0x2B, 0xFF, 0x88), (0xFF, 0xF2, 0x2B), (0x2B, 0xC8, 0xFF), (0xFF, 0x6A, 0x00)]
    rnd = np.random.default_rng(11)
    for b in range(9):                                     # bouncing blocks
        bx = x0 + 40 + (b % 3) * 330
        by = y0 + 120 + (b // 3) * 270 + int(28 * math.sin(k * math.pi / 2 + b))
        c = neon[(b + k) % len(neon)]
        d.rounded_rectangle((bx, by, bx + 280, by + 200), radius=30, fill=c, outline=(255, 255, 255), width=8)
    rnd2 = np.random.default_rng(100 + k)
    for _ in range(260):                                    # glitter
        gx, gy = int(rnd2.integers(x0, x1)), int(rnd2.integers(y0, y1))
        d.rectangle((gx, gy, gx + 5, gy + 5), fill=(255, 255, 255))
    for s in range(14):                                     # stars, every other one blinks
        if (s + k) % 2:
            continue
        cx, cy = int(rnd.integers(x0 + 40, x1 - 40)), int(rnd.integers(y0 + 40, y1 - 40))
        r0, r1 = 46, 18
        pts = [(cx + (r0 if j % 2 == 0 else r1) * math.cos(math.pi * j / 5 - math.pi / 2),
                cy + (r0 if j % 2 == 0 else r1) * math.sin(math.pi * j / 5 - math.pi / 2)) for j in range(10)]
        d.polygon(pts, fill=(0xFF, 0xF6, 0x6B), outline=(255, 255, 255))


def reference_thumb(w, h):
    """The reference the designer drags in: a mini clean site."""
    big = Image.new("RGB", (SITE[2] - SITE[0], SITE[3] - SITE[1]), (255, 255, 255))
    full = Image.new("RGB", (SW, SH), (255, 255, 255))
    site_clean(ImageDraw.Draw(full))
    big.paste(full.crop(SITE), (0, 0))
    return big.resize((w, h), Image.LANCZOS)


def clawd_mark(d, x, y, s):
    """Tiny Clawd sprite (terracotta), top-left at x, y, pixel size s."""
    d.rectangle((x + s, y, x + 11 * s, y + 4 * s), fill=TERRA)
    d.rectangle((x, y + 2 * s, x + 12 * s, y + 3 * s), fill=TERRA)
    for lx in (2, 4, 7, 9):
        d.rectangle((x + lx * s, y + 4 * s, x + (lx + 1) * s, y + 5 * s), fill=TERRA)
    for ex in (3, 8):
        d.rectangle((x + ex * s, y + s, x + (ex + 1) * s, y + 2 * s), fill=INK)


# ---------------------------------------------------------------- chat panel
F_MSG = None


def fonts():
    global F_MSG
    if F_MSG is None:
        F_MSG = dict(msg=font(HELVETICA_NEUE, 36, HN_REGULAR), input=font(HELVETICA_NEUE, 34, HN_REGULAR),
                     head=font(HELVETICA_NEUE, 34, HN_BOLD), ui=font(HELVETICA_NEUE, 26, HN_MEDIUM))
    return F_MSG


def chat_panel(img, s):
    F = fonts()
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = CHAT
    d.rectangle(CHAT, fill=CHAT_BG)
    d.line((x0, y0, x0, y1), fill=LINE, width=2)
    clawd_mark(d, x0 + 24, y0 + 24, 4)
    d.text((x0 + 86, y0 + 50), "Claude", font=F["head"], fill=INK, anchor="ls")
    d.line((x0, y0 + 80, x1, y0 + 80), fill=LINE, width=2)
    # messages, top down
    y = y0 + 110
    bw = x1 - x0 - 120
    for who, text in s["chat"]:
        lines = wrap(text, F["msg"], bw - 48)
        hgt = 46 * len(lines) + 30
        if who == "user":
            if text == TL.PROMPT_2:                     # the reference travels with the prompt
                th = reference_thumb(180, 117)
                img.paste(th, (x1 - 24 - 180, y))
                d.rounded_rectangle((x1 - 24 - 180, y, x1 - 24, y + 117), radius=10, outline=LINE, width=2)
                y += 117 + 10
            wmax = max(F["msg"].getlength(l) for l in lines) + 48
            d.rounded_rectangle((x1 - 24 - wmax, y, x1 - 24, y + hgt), radius=22, fill=PEACH_LIGHT)
            for n, l in enumerate(lines):
                d.text((x1 - 24 - wmax + 24, y + 50 + 46 * n), l, font=F["msg"], fill=INK, anchor="ls")
        else:
            clawd_mark(d, x0 + 24, y + 22, 3)
            for n, l in enumerate(lines):
                d.text((x0 + 76, y + 50 + 46 * n), l, font=F["msg"], fill=INK, anchor="ls")
        y += hgt + 22
    assert y < INPUT[1] - 90, ("chat overflows", y)
    # attachment chip above the input
    if s["attach"]:
        th = reference_thumb(120, 78)
        img.paste(th, (INPUT[0], INPUT[1] - 90))
        d.rounded_rectangle((INPUT[0], INPUT[1] - 90, INPUT[0] + 120, INPUT[1] - 12), radius=8, outline=TERRA, width=3)
    # input box
    d.rounded_rectangle(INPUT, radius=22, fill=(255, 255, 255), outline=LINE, width=2)
    lines = wrap(s["input"], F["input"], INPUT[2] - INPUT[0] - 48) if s["input"] else [""]
    assert len(lines) <= 3, ("input overflows", s["input"])
    for n, l in enumerate(lines):
        d.text((INPUT[0] + 24, INPUT[1] + 46 + 40 * n), l, font=F["input"], fill=INK, anchor="ls")
    cx = INPUT[0] + 24 + F["input"].getlength(lines[-1]) + 3
    cy = INPUT[1] + 46 + 40 * (len(lines) - 1)
    d.rectangle((cx, cy - 30, cx + 3, cy + 6), fill=TERRA)                                     # caret
    d.ellipse((INPUT[2] - 64, INPUT[3] - 64, INPUT[2] - 16, INPUT[3] - 16), fill=TERRA)        # send button
    d.polygon([(INPUT[2] - 40, INPUT[3] - 54), (INPUT[2] - 28, INPUT[3] - 38), (INPUT[2] - 52, INPUT[3] - 38)],
              fill=(255, 255, 255))


def cursor(d, x, y):
    pts = [(0, 0), (0, 44), (11, 33), (19, 52), (27, 48), (19, 30), (34, 30)]
    d.polygon([(x + px, y + py) for px, py in pts], fill=(255, 255, 255), outline=INK)
    d.line([(x + px, y + py) for px, py in pts + [pts[0]]], fill=INK, width=3)


def screen_image(s):
    img = Image.new("RGB", (SW, SH), (255, 255, 255))
    d = ImageDraw.Draw(img)
    site = s["site"]
    if site == "grey":
        site_grey(d)
    elif site == "clean":
        site_clean(d)
    elif site.startswith("rainbow"):
        site_rainbow(img, int(site[-1]))
    elif site.startswith("wipe"):              # clean sweeps in from the top over the frozen rainbow
        site_rainbow(img, 0)
        clean = Image.new("RGB", (SW, SH), (255, 255, 255))
        site_clean(ImageDraw.Draw(clean))
        cut = SITE[1] + int((SITE[3] - SITE[1]) * int(site[-1]) / 4)
        img.paste(clean.crop((SITE[0], SITE[1], SITE[2], cut)), (SITE[0], SITE[1]))
        d = ImageDraw.Draw(img)
        d.rectangle((SITE[0], cut - 3, SITE[2], cut + 3), fill=PEACH)
    d = ImageDraw.Draw(img)
    # browser chrome
    d.rectangle((0, 0, SW, 56), fill=(0xEC, 0xEA, 0xE6))
    for i, c in enumerate([(0xEE, 0x6A, 0x5F), (0xF5, 0xBD, 0x4F), (0x61, 0xC5, 0x54)]):
        d.ellipse((22 + i * 30, 19, 40 + i * 30, 37), fill=c)
    d.rounded_rectangle((150, 12, 900, 44), radius=16, fill=(255, 255, 255))
    chat_panel(img, s)
    if s["drag"] is not None:                   # reference + cursor travelling to the chat input
        p = s["drag"]
        e = p * p * (3 - 2 * p)
        sx, sy, ex, ey = 260, 560, INPUT[0] + 40, INPUT[1] - 60
        x, y = sx + (ex - sx) * e, sy + (ey - sy) * e
        d = ImageDraw.Draw(img)
        th = reference_thumb(200, 130)
        d.rectangle((x - 4, y - 4, x + 204, y + 134), fill=TERRA)
        img.paste(th, (int(x), int(y)))
        cursor(ImageDraw.Draw(img), int(x + 150), int(y + 90))
    return img


# ---------------------------------------------------------------- overlays (1080 x 1920)
def overlay_caption():
    img = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = font(HELVETICA_NEUE, 76, HN_BOLD)
    w = f.getlength(TL.CAPTION_1)
    cy = 1380
    box = (VW / 2 - w / 2 - 44, cy - 74, VW / 2 + w / 2 + 44, cy + 50)
    d.rounded_rectangle(box, radius=34, fill=INK + (235,))
    d.text((VW / 2, cy), TL.CAPTION_1, font=f, fill=PAPER + (255,), anchor="ms")
    return img, [box], [(PAPER, INK, 4.5)]


def overlay_bubble():
    img = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = font(HELVETICA_NEUE, 80, HN_BOLD)
    w = f.getlength(TL.CLAUDE_1)
    cy = 560
    box = (VW / 2 - w / 2 - 56, cy - 100, VW / 2 + w / 2 + 56, cy + 60)
    tail = [(VW / 2 - 60, box[3] - 4), (VW / 2 + 20, box[3] - 4), (VW / 2 - 90, box[3] + 110)]
    d.polygon(tail, fill=INK + (255,))
    d.rounded_rectangle((box[0] - 7, box[1] - 7, box[2] + 7, box[3] + 7), radius=56, fill=INK + (255,))
    d.rounded_rectangle(box, radius=50, fill=(255, 255, 255, 255))
    d.polygon([(x, y - 9) for x, y in tail[:2]] + [(tail[2][0] + 6, tail[2][1] - 22)], fill=(255, 255, 255, 255))
    d.text((VW / 2, cy + 8), TL.CLAUDE_1, font=f, fill=INK + (255,), anchor="ms")
    return img, [(box[0] - 7, box[1] - 7, box[2] + 7, tail[2][1])], [(INK, (255, 255, 255), 4.5)]


def overlay_card():
    img = Image.new("RGBA", (VW, VH), PAPER + (255,))
    d = ImageDraw.Draw(img)
    fl = font(HELVETICA_NEUE, 64, HN_BOLD)
    fb = font(HELVETICA_NEUE, 78, HN_BOLD)
    x0 = 110
    lines = wrap(TL.CARD_TEXT, fb, VW - 2 * x0)
    lead = 96
    total = 90 + lead * len(lines)
    y = (VH - total) / 2 - 60
    d.rectangle((x0, y - 70, x0 + 120, y - 58), fill=PEACH + (255,))
    d.text((x0, y), TL.CARD_LABEL, font=fl, fill=TERRA + (255,), anchor="ls")
    for n, l in enumerate(lines):
        d.text((x0, y + 90 + lead * n), l, font=fb, fill=INK + (255,), anchor="ls")
    box = (x0, y - 70, VW - x0, y + 90 + lead * (len(lines) - 1) + 24)
    return img, [box], [(INK, PAPER, 4.5), (TERRA, PAPER, 3.0)]   # label: 64 px bold = large text


OVERLAYS = {"overlay_caption.png": overlay_caption, "overlay_bubble.png": overlay_bubble,
            "overlay_card.png": overlay_card}


# ---------------------------------------------------------------- sounds
RATE = 48000


def write_wav(path, x):
    x = np.clip(x, -1, 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((x * 32767).astype("<i2").tobytes())


def env(n, tau):
    return np.exp(-np.arange(n) / (tau * RATE))


def snd_tick():
    n = int(0.03 * RATE)
    rng = np.random.default_rng(1)
    t = np.arange(n) / RATE
    return 0.35 * (rng.normal(0, 1, n) * 0.6 + np.sin(2 * np.pi * 3800 * t)) * env(n, 0.006)


def snd_enter():
    n = int(0.16 * RATE)
    rng = np.random.default_rng(2)
    t = np.arange(n) / RATE
    thump = np.sin(2 * np.pi * (140 - 300 * t) * t) * env(n, 0.03)
    clack = rng.normal(0, 1, n) * env(n, 0.008)
    x = 0.7 * thump + 0.5 * clack
    return 0.8 * x / np.abs(x).max()


def snd_chime():
    n = int(1.0 * RATE)
    x = np.zeros(n)
    for i, hz in enumerate((1046.5, 1318.5, 1568.0, 2093.0)):
        s = int(i * 0.09 * RATE)
        t = np.arange(n - s) / RATE
        x[s:] += np.sin(2 * np.pi * hz * t) * np.exp(-t / 0.35) * 0.22
    return x


def snd_pop():
    n = int(0.09 * RATE)
    t = np.arange(n) / RATE
    return 0.6 * np.sin(2 * np.pi * (650 - 4000 * t) * t) * env(n, 0.025)


def snd_disco():
    """Four-on-the-floor loop, exactly the rainbow's length; no fade: it stops dead."""
    n = int(round(TL.DISCO_FRAMES / TL.FPS * RATE))
    x = np.zeros(n)
    beat = 60 / 124
    rng = np.random.default_rng(3)
    t_all = np.arange(n) / RATE
    k = 0
    while k * beat < n / RATE:
        s = int(k * beat * RATE)
        m = min(n - s, int(0.25 * RATE))
        t = np.arange(m) / RATE
        x[s:s + m] += 0.9 * np.sin(2 * np.pi * (110 * np.exp(-t * 18) + 45) * t) * np.exp(-t / 0.12)   # kick
        h = int((k + 0.5) * beat * RATE)
        if h < n:
            mh = min(n - h, int(0.06 * RATE))
            hat = np.diff(rng.normal(0, 1, mh + 1)) * np.exp(-np.arange(mh) / (0.015 * RATE))
            x[h:h + mh] += 0.18 * hat
        k += 1
    bass_notes = [55.0, 55.0, 65.4, 49.0]
    for i in range(int(n / RATE / (beat / 2)) + 1):                  # offbeat octave bass
        s = int(i * beat / 2 * RATE)
        m = min(n - s, int(beat / 2 * RATE))
        if m <= 0:
            break
        hz = bass_notes[(i // 4) % 4] * (2 if i % 2 else 1)
        t = np.arange(m) / RATE
        x[s:s + m] += 0.22 * np.sign(np.sin(2 * np.pi * hz * t)) * np.exp(-t / 0.09)
    chord = [523.3, 659.3, 784.0]
    for k2 in range(1, int(n / RATE / beat) + 1, 2):                 # stabs on 2 and 4
        s = int(k2 * beat * RATE)
        m = min(n - s, int(0.18 * RATE))
        if m <= 0:
            break
        t = np.arange(m) / RATE
        saw = sum(2 * ((hz * t) % 1) - 1 for hz in chord) / 3
        x[s:s + m] += 0.25 * saw * np.exp(-t / 0.08)
    x += 0.04 * np.sin(2 * np.pi * 7 * t_all) * np.sin(2 * np.pi * 1318.5 * t_all)   # sparkle shimmer
    return 0.85 * x / np.abs(x).max()


SOUND_FNS = {"tick.wav": snd_tick, "enter.wav": snd_enter, "chime.wav": snd_chime, "pop.wav": snd_pop,
             "disco.wav": snd_disco}


# ---------------------------------------------------------------- build + checks
def build():
    SCREENS.mkdir(parents=True, exist_ok=True)
    (AUDIO / "music").mkdir(parents=True, exist_ok=True)
    (AUDIO / "sfx").mkdir(parents=True, exist_ok=True)
    keep = set()
    for f, s in TL.screen_states():
        name = TL.state_key(s) + ".png"
        if name not in keep:
            screen_image(s).save(SCREENS / name, optimize=True)
            keep.add(name)
    for old in SCREENS.glob("screen_*.png"):
        if old.name not in keep:
            old.unlink()
    for name, fn in OVERLAYS.items():
        fn()[0].save(OUT / name, optimize=True)
    for name, fn in SOUND_FNS.items():
        write_wav(sound_path(name), fn())
    (OUT / "screen_timeline.json").write_text(json.dumps(TL.screen_timeline()))
    print(f"{len(keep)} screen states, {len(OVERLAYS)} overlays, {len(SOUND_FNS)} sounds -> {OUT}")


def lum(c):
    c = np.array(c[:3], float) / 255
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return float(c @ [0.2126, 0.7152, 0.0722])


def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def check():
    ok = True

    def req(cond, msg):
        nonlocal ok
        print(("OK   " if cond else "FAIL ") + msg)
        ok &= bool(cond)

    # timing against the scenario
    shots = TL.SHOTS
    req(shots[0][2] == 1 and shots[-1][3] == TL.FRAME_END and
        all(a[3] + 1 == b[2] for a, b in zip(shots, shots[1:])), f"shots contiguous 1..{TL.FRAME_END}")
    starts = {}
    for sc, cam, a, b in shots:
        starts.setdefault(sc, a)
    want = {1: 0, 2: 4, 3: 7, 4: 10, 5: 13, 6: 15, 7: 19, 8: 22}
    got = {sc: (f - 1) / TL.FPS for sc, f in starts.items()}
    req(got == {k: float(v) for k, v in want.items()}, f"scene starts (s) {got}")
    req(TL.FRAME_END / TL.FPS == 25.0, "length 25.0 s at 24 fps")

    def within(frames, sc_cam, label):
        rng = [(a, b) for sc, cam, a, b in shots if cam == sc_cam[1] and sc == sc_cam[0]]
        req(all(any(a <= f <= b for a, b in rng) for f in frames), f"{label} inside scene {sc_cam[0]} ({sc_cam[1]})")

    within(TL.KEYS_1 + [TL.ENTER_1], (2, "S2_Keys"), "typing + Enter")
    within([TL.CLAUDE_GLOW, TL.CLAUDE_REPLY], (3, "S3_Claude"), "Clawd glow + reply")
    within(TL.ERASE + TL.TYPE_2 + TL.DRAG + [TL.DROP, TL.ENTER_2], (6, "S6_Shoulder"), "erase, retype, drag, send")
    within(TL.WIPE + [TL.CLEAN], (7, "S4_Screen"), "site turns clean")
    within(list(TL.THUMB) + [TL.SMILE], (7, "S7_Front"), "smile + thumbs up")

    # screen states
    st = TL.screen_states()
    req(all(a[0] < b[0] for a, b in zip(st, st[1:])), "screen states strictly in time order")
    typed1 = [s["input"] for f, s in st if TL.KEYS_1[0] <= f <= TL.KEYS_1[-1]]
    typed2 = [s["input"] for f, s in st if TL.TYPE_2[0] <= f <= TL.TYPE_2[-1]]
    req(typed1[-1] == TL.PROMPT_1 and all(TL.PROMPT_1.startswith(t) for t in typed1), "prompt 1 typed to the letter")
    req(typed2[-1] == TL.PROMPT_2 and all(TL.PROMPT_2.startswith(t) for t in typed2), "prompt 2 typed to the letter")
    runs = TL.screen_timeline()
    req(runs[0][0] == 1 and runs[-1][1] == TL.FRAME_END and all(a[1] + 1 == b[0] for a, b in zip(runs, runs[1:])),
        f"screen timeline covers 1..{TL.FRAME_END} in {len(runs)} runs")
    files = {r[2] for r in runs}
    sizes = {Image.open(SCREENS / n).size for n in files if (SCREENS / n).exists()}
    req(all((SCREENS / n).exists() for n in files) and sizes == {(SW, SH)}, f"{len(files)} screen images exist, {SW}x{SH}")
    tl_json = json.loads((OUT / "screen_timeline.json").read_text())
    req(tl_json == [list(r) for r in runs], "screen_timeline.json matches the timeline")
    rb = [r for r in runs if TL.RAINBOW[0] <= r[0] < TL.RAINBOW[1]]
    req(len({r[2] for r in rb}) == 4 and all(r[1] - r[0] + 1 == TL.RAINBOW_STEP for r in rb[:-1]),
        f"rainbow animates: 4 states, {TL.RAINBOW_STEP} frames each, {len(rb)} runs")

    # glyphs
    F = fonts()
    texts = [TL.PROMPT_1, TL.PROMPT_2, TL.CLAUDE_1, "Claude"]
    miss = set()
    for t in texts:
        miss |= set(missing_glyphs(t, F["msg"]))
    for t, fsize in ((TL.CAPTION_1, 76), (TL.CLAUDE_1, 80), (TL.CARD_TEXT, 78), (TL.CARD_LABEL, 64)):
        miss |= set(missing_glyphs(t, font(HELVETICA_NEUE, fsize, HN_BOLD)))
    req(not miss, f"all glyphs present in Helvetica Neue (missing: {sorted(miss)})")

    # overlays: in the safe area, readable
    for name, fn in OVERLAYS.items():
        img, boxes, pairs = fn()
        on_disk = Image.open(OUT / name)
        inside = all(SAFE[0] <= b[0] and b[2] <= SAFE[2] and SAFE[1] <= b[1] and b[3] <= SAFE[3] for b in boxes)
        crs = [(round(contrast(a, b), 2), need) for a, b, need in pairs]
        req(on_disk.size == (VW, VH) and on_disk.mode == "RGBA", f"{name} {on_disk.size} {on_disk.mode}")
        req(inside or name == "overlay_card.png" and all(60 <= b[0] and b[2] <= VW - 60 for b in boxes),
            f"{name} text inside the safe area {[tuple(int(v) for v in b) for b in boxes]}")
        req(all(c >= need for c, need in crs), f"{name} text contrast (measured, needed) {crs}")
        a = np.asarray(on_disk)[..., 3]
        if name != "overlay_card.png":
            req((a == 0).mean() > 0.85, f"{name} transparent outside the text ({100 * (a == 0).mean():.1f}%)")

    # sounds
    for name in SOUND_FNS:
        with wave.open(str(sound_path(name))) as w:
            n, rate = w.getnframes(), w.getframerate()
            x = np.frombuffer(w.readframes(n), "<i2") / 32767
        req(rate == RATE and 0.2 < np.abs(x).max() < 0.99, f"{name} {n / rate:.3f} s, peak {np.abs(x).max():.2f}")
        if name == "disco.wav":
            req(n == round(TL.DISCO_FRAMES / TL.FPS * RATE), f"disco is exactly {TL.DISCO_FRAMES} frames ({n / rate:.3f} s)")
            tail = x[-int(0.05 * RATE):]
            req(np.sqrt((tail ** 2).mean()) > 0.02, f"disco does not fade: last 50 ms RMS {np.sqrt((tail ** 2).mean()):.3f}")
    cues = TL.sound_cues()
    req(all(1 <= f <= TL.FRAME_END and sound_path(n).exists() for n, f in cues), f"{len(cues)} sound cues inside 1..600")
    req(TL.RAINBOW[0] + TL.DISCO_FRAMES == TL.RAINBOW[1] == next(a for sc, c, a, b in shots if sc == 5),
        "music stops on the first frame of scene 5")
    print("ALL OK" if ok else "SOME CHECKS FAILED")
    return ok


if __name__ == "__main__":
    if "--check" not in sys.argv:
        build()
    sys.exit(0 if check() else 1)
