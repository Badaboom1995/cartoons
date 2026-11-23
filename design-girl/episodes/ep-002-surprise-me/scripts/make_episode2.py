#!/usr/bin/env python3
"""Images and sounds for Episode 2 "Surprise Me" (voice input, Claude throws a party). Built in Blender by
scripts/episode2.py into the scene EP2_Inspiration.

    python3 scripts/make_episode2.py

Writes overlays/ and audio/sfx/ here:
  screens/*.png   laptop screen states 1600 x 1000 (empty, flicker, confetti, palette, moodboard),
                  voice-input pill overlays mic_idle / mic_0..5 (RGBA)
  overlays/captions.json  subtitle lines (wrapped with the caption font, max 2 lines) - Blender turns them into
                  Video Sequencer text strips in the edit scene EP2_Edit; overlays/card.png = optional end card
  sfx/*.wav       48 kHz mono: clock, scratch, step, whoosh, chip (cleanup tune), sneeze
  key_mic.png     the mic key cap, 256 x 256
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scene" / "locations" / "studio" / "scripts"))
from make_textures import HELVETICA_NEUE, HN_BOLD, HN_MEDIUM, HN_REGULAR, INK, PAPER, PEACH, font  # noqa: E402

OUT = Path(__file__).resolve().parents[1]
SW, SH = 1600, 1000
VW, VH = 1080, 1920
TERRA = (0xD9, 0x77, 0x57)
CHAT_BG = (0xFA, 0xF8, 0xF5)
LINE = (0xE2, 0xDE, 0xD8)
GREY_TXT = (0x8A, 0x86, 0x80)
EMOJI = "/System/Library/Fonts/Apple Color Emoji.ttc"

# the disco colours: the lights cycle through these, the palette is made of them
DISCO = [(0xFF, 0x4F, 0xA3), (0x8A, 0x5C, 0xFF), (0x2F, 0xD4, 0xE0), (0xB6, 0xF0, 0x3C), (0xFF, 0x9A, 0x3D)]
DISCO_NAMES = ["Disco Pink", "Laser Violet", "Club Aqua", "Glowstick", "Sunrise Nap"]

SUBS = {   # her lines (white on a dark box); timed to the voice lines in scripts/episode2.py
    "s01": "Hey, Claude…",
    "s03a": "The deadline is so close…",
    "s03b": "…and I still have zero ideas.",
    "s04a": "I need some inspiration…",
    "s04b": "…surprise me.",
    "s05a": "Okay…",
    "s05b": "I'm gonna nap a little.",
    "s06a": "Huh?!",
    "s06b": "…Claude…",
    "s06c": "…was there a party just now?",
    "s08a": "My moodboard…",
    "s08b": "…my deadline…",
    "s08c": "Claude!",
    "s10a": "…Oh.",
    "s10b": "That's… actually beautiful.",
    "s11a": "Thank you, Claude.",
    "s11b": "Now I can finally go for a walk.",
}
BUBBLES = {  # Claude's lines (Claude-orange box + 'Claude' tag)
    "b02": "Yep, I'm here!",
    "b05": "Say less. Cooking!",
    "b07a": "A party?",
    "b07b": "Nooo. No party.",
    "b07c": "…Definitely… no party.",
    "b09": "Hey, relax. Look.",
    "b12a": "Go! Enjoy it.",
    "b12b": "I've got this.",
    "b13": "…oh no.",
}


def wrap(text, f, width):
    words, lines, cur = text.split(" "), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if f.getlength(t) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def clawd_mark(d, x, y, s):
    d.rectangle((x + s, y, x + 11 * s, y + 4 * s), fill=TERRA)
    d.rectangle((x, y + 2 * s, x + 12 * s, y + 3 * s), fill=TERRA)
    for lx in (2, 4, 7, 9):
        d.rectangle((x + lx * s, y + 4 * s, x + (lx + 1) * s, y + 5 * s), fill=TERRA)
    for ex in (3, 8):
        d.rectangle((x + ex * s, y + s, x + (ex + 1) * s, y + 2 * s), fill=INK)


def mic_glyph(d, cx, cy, s, col):
    """Microphone centred at cx, cy; s = overall height."""
    w = s * 0.36
    d.rounded_rectangle((cx - w / 2, cy - s / 2, cx + w / 2, cy + s * 0.12), radius=w / 2, fill=col)
    lw = max(2, int(s * 0.07))
    r = s * 0.32
    d.arc((cx - r, cy - s * 0.25 - r * 0.2, cx + r, cy + s * 0.22), 0, 180, fill=col, width=lw)
    d.line((cx, cy + s * 0.22, cx, cy + s * 0.42), fill=col, width=lw)
    d.line((cx - s * 0.2, cy + s * 0.44, cx + s * 0.2, cy + s * 0.44), fill=col, width=lw)


# ---------------------------------------------------------------- laptop screens
F = {}


def fonts():
    if not F:
        F.update(title=font(HELVETICA_NEUE, 44, HN_BOLD), ui=font(HELVETICA_NEUE, 28, HN_MEDIUM),
                 small=font(HELVETICA_NEUE, 24, HN_REGULAR), head=font(HELVETICA_NEUE, 34, HN_BOLD),
                 big=font(HELVETICA_NEUE, 150, HN_BOLD), hex=font(HELVETICA_NEUE, 26, HN_BOLD))
    return F


def chrome(img, title):
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, SW, 56), fill=(0xEC, 0xEA, 0xE6))
    for i, c in enumerate([(0xEE, 0x6A, 0x5F), (0xF5, 0xBD, 0x4F), (0x61, 0xC5, 0x54)]):
        d.ellipse((22 + i * 30, 19, 40 + i * 30, 37), fill=c)
    d.rounded_rectangle((150, 12, 900, 44), radius=16, fill=(255, 255, 255))
    f = fonts()
    d.text((60, 130), title, font=f["title"], fill=INK, anchor="ls")


def chat_side(img, mic_on=False):
    d = ImageDraw.Draw(img)
    f = fonts()
    x0, y0, x1, y1 = 1180, 56, SW, SH
    d.rectangle((x0, y0, x1, y1), fill=CHAT_BG)
    d.line((x0, y0, x0, y1), fill=LINE, width=2)
    clawd_mark(d, x0 + 24, y0 + 24, 4)
    d.text((x0 + 86, y0 + 50), "Claude", font=f["head"], fill=INK, anchor="ls")
    d.line((x0, y0 + 80, x1, y0 + 80), fill=LINE, width=2)
    d.rounded_rectangle((x0 + 20, y1 - 110, x1 - 20, y1 - 24), radius=40, fill=(255, 255, 255), outline=LINE, width=2)
    d.ellipse((x1 - 100, y1 - 100, x1 - 34, y1 - 34), fill=TERRA)
    mic_glyph(d, x1 - 67, y1 - 67, 40, (255, 255, 255))


def tile_grid():
    """6 tiles of the moodboard: (x0, y0, x1, y1)."""
    out = []
    for r in range(2):
        for c in range(3):
            x = 60 + c * 360
            y = 180 + r * 390
            out.append((x, y, x + 330, y + 360))
    return out


def screen_empty():
    img = Image.new("RGB", (SW, SH), (255, 255, 255))
    chrome(img, "Moodboard")
    d = ImageDraw.Draw(img)
    f = fonts()
    d.text((290, 130), "· 0 items", font=f["ui"], fill=GREY_TXT, anchor="ls")
    for (x0, y0, x1, y1) in tile_grid():
        d.rounded_rectangle((x0, y0, x1, y1), radius=18, fill=(0xE6, 0xE5, 0xE3))
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        d.line((cx - 24, cy, cx + 24, cy), fill=(0xC6, 0xC4, 0xC0), width=6)
        d.line((cx, cy - 24, cx, cy + 24), fill=(0xC6, 0xC4, 0xC0), width=6)
    chat_side(img)
    return img


def mic_overlay(k):
    """Voice-input pill at the bottom of the screen: k = None idle (flat wave), 0..5 talking. RGBA."""
    img = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = 470, 846, 1130, 966
    d.rounded_rectangle((x0 + 6, y0 + 8, x1 + 6, y1 + 8), radius=60, fill=(0, 0, 0, 70))
    d.rounded_rectangle((x0, y0, x1, y1), radius=60, fill=(255, 255, 255, 250), outline=TERRA + (255,), width=5)
    cy = (y0 + y1) / 2
    d.ellipse((x0 + 14, y0 + 14, x0 + 106, y1 - 14), fill=TERRA + (255,))
    mic_glyph(d, x0 + 60, cy - 2, 56, (255, 255, 255, 255))
    n = 17
    for i in range(n):
        x = x0 + 150 + i * 26
        if k is None:
            h = 10
        else:
            env = math.sin(math.pi * (i + 0.5) / n)
            h = 12 + 78 * env * (0.3 + 0.7 * abs(math.sin(k * 1.3 + i * 0.9)))
        d.rounded_rectangle((x - 8, cy - h / 2, x + 8, cy + h / 2), radius=8, fill=TERRA + (255,))
    f = fonts()
    d.text((x1 - 30, cy + 10), "Listening" if k is not None else "Mic on", font=f["small"],
           fill=GREY_TXT + (255,), anchor="rs")
    return img


def screen_flicker(k):
    """The empty moodboard glitching: tiles shuffle and flash neon (k = 0..3)."""
    img = Image.new("RGB", (SW, SH), (255, 255, 255))
    chrome(img, "Moodboard")
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(20 + k)
    tiles = tile_grid()
    order = rng.permutation(len(tiles))
    for n, j in enumerate(order):
        x0, y0, x1, y1 = tiles[j]
        dx, dy = int(rng.integers(-40, 40)), int(rng.integers(-30, 30))
        c = DISCO[(n + k) % 5] if rng.random() < 0.25 + 0.2 * k else (0xE6, 0xE5, 0xE3)
        d.rounded_rectangle((x0 + dx, y0 + dy, x1 + dx, y1 + dy), radius=18, fill=c)
        for _ in range(k * 3):
            sx, sy = int(rng.integers(x0, x1)), int(rng.integers(y0, y1))
            d.rectangle((sx, sy, sx + 60, sy + 8), fill=DISCO[int(rng.integers(0, 5))])
    chat_side(img)
    return img


def screen_moodboard():
    """The finished moodboard: neon-pastel, colours taken from the party."""
    img = Image.new("RGB", (SW, SH), (255, 255, 255))
    chrome(img, "Moodboard")
    d = ImageDraw.Draw(img)
    f = fonts()
    d.text((290, 130), "· “Surprise me” · 6 items", font=f["ui"], fill=TERRA, anchor="ls")
    pastel = [tuple(int(c + (255 - c) * 0.35) for c in col) for col in DISCO]
    t = tile_grid()
    # 1 gradient
    x0, y0, x1, y1 = t[0]
    g = Image.new("RGB", (x1 - x0, y1 - y0))
    ga = np.linspace(0, 1, x1 - x0)[None, :, None]
    gb = np.linspace(0, 1, y1 - y0)[:, None, None]
    a, b2 = np.array(pastel[0], float), np.array(pastel[1], float)
    g = Image.fromarray(np.clip(a * (1 - (ga + gb) / 2) + b2 * (ga + gb) / 2, 0, 255).astype(np.uint8))
    m = Image.new("L", g.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, g.size[0] - 1, g.size[1] - 1), radius=18, fill=255)
    img.paste(g, (x0, y0), m)
    # 2 disco ball
    x0, y0, x1, y1 = t[1]
    d.rounded_rectangle(t[1], radius=18, fill=(0x2A, 0x22, 0x3A))
    cx, cy, r = (x0 + x1) / 2, (y0 + y1) / 2 + 20, 110
    d.line((cx, y0, cx, cy - r), fill=(200, 200, 210), width=4)
    for i in range(-5, 6):
        for j in range(-5, 6):
            px, py = cx + i * 20, cy + j * 20
            if (px - cx) ** 2 + (py - cy) ** 2 < r * r:
                c = pastel[(i * 3 + j) % 5] if (i + j) % 3 == 0 else (0xDD, 0xDD, 0xE6)
                d.rectangle((px - 9, py - 9, px + 9, py + 9), fill=c)
    # 3 type specimen
    x0, y0, x1, y1 = t[2]
    d.rounded_rectangle(t[2], radius=18, fill=pastel[2])
    d.text((x0 + 40, y0 + 230), "Aa", font=font(HELVETICA_NEUE, 170, HN_BOLD), fill=INK, anchor="ls")
    d.text((x0 + 44, y0 + 300), "Neon Grotesk", font=f["ui"], fill=INK, anchor="ls")
    # 4 palette strip
    x0, y0, x1, y1 = t[3]
    d.rounded_rectangle(t[3], radius=18, fill=(0xF6, 0xF4, 0xF0))
    w = (x1 - x0 - 40) / 5
    for i, c in enumerate(DISCO):
        d.rounded_rectangle((x0 + 20 + i * w, y0 + 30, x0 + 20 + (i + 1) * w - 8, y1 - 80), radius=12, fill=c)
    d.text((x0 + 24, y1 - 30), "Palette: Disco Nap", font=f["small"], fill=INK, anchor="ls")
    # 5 confetti pattern
    x0, y0, x1, y1 = t[4]
    d.rounded_rectangle(t[4], radius=18, fill=(0xFD, 0xF6, 0xEC))
    rng = np.random.default_rng(3)
    for i in range(46):
        px, py = rng.uniform(x0 + 20, x1 - 30), rng.uniform(y0 + 20, y1 - 30)
        d.rectangle((px, py, px + 22, py + 12), fill=DISCO[i % 5])
    # 6 neon sign
    x0, y0, x1, y1 = t[5]
    d.rounded_rectangle(t[5], radius=18, fill=(0x1C, 0x16, 0x2A))
    fs = font(HELVETICA_NEUE, 64, HN_BOLD)
    for k2, (txt, yy) in enumerate((("surprise", y0 + 160), ("me.", y0 + 240))):
        for blur, col in ((6, pastel[0]), (0, (255, 255, 255))):
            d.text(((x0 + x1) / 2 + blur, yy + blur), txt, font=fs, fill=col if blur else (255, 230, 245), anchor="ms")
    chat_side(img)
    return img



def hue_bg(w, h, k):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    rgb = np.zeros((h, w, 3), np.float32)
    cols = np.array(DISCO, np.float32) / 255
    t = ((xx / w + yy / h) * 0.8 + k * 0.17) % 1.0 * len(DISCO)
    i0 = np.floor(t).astype(int) % len(DISCO)
    i1 = (i0 + 1) % len(DISCO)
    fr = (t - np.floor(t))[..., None]
    rgb = cols[i0] * (1 - fr) + cols[i1] * fr
    return Image.fromarray((np.clip(rgb * 0.85 + 0.12, 0, 1) * 255).astype(np.uint8), "RGB")


def screen_confetti(k, frozen=False):
    img = hue_bg(SW, SH, k)
    d = ImageDraw.Draw(img)
    f = fonts()
    rng = np.random.default_rng(42)
    cx, cy = SW / 2, SH / 2
    burst = 1.0 if frozen else min(1.0, 0.35 + 0.25 * k)
    for i in range(170):
        ang = rng.uniform(0, 2 * math.pi)
        dist = rng.uniform(0.15, 1.0) * 900 * burst
        x = cx + math.cos(ang) * dist + (0 if frozen else 10 * math.sin(k + i))
        y = cy + math.sin(ang) * dist * 0.62 + (0 if frozen else k * 6)
        s = rng.uniform(10, 26)
        rot = rng.uniform(0, math.pi) + (0 if frozen else k * 0.6)
        c = DISCO[i % 5] if i % 3 else (255, 255, 255)
        pts = [(x + s * math.cos(rot + a), y + s * 0.5 * math.sin(rot + a)) for a in (0, math.pi / 2, math.pi, 3 * math.pi / 2)]
        d.polygon(pts, fill=c)
    word = "PARTY!" if not frozen else "PARTY?"
    for dx, dy, c in ((8, 8, INK), (0, 0, (255, 255, 255))):
        d.text((cx + dx, cy + 60 + dy), word, font=f["big"], fill=c, anchor="ms")
    d.rectangle((0, 0, SW, 56), fill=(0xEC, 0xEA, 0xE6))
    for i, c in enumerate([(0xEE, 0x6A, 0x5F), (0xF5, 0xBD, 0x4F), (0x61, 0xC5, 0x54)]):
        d.ellipse((22 + i * 30, 19, 40 + i * 30, 37), fill=c)
    return img


def screen_palette(n):
    """Moodboard with n of 5 swatches (n = 0..5)."""
    img = Image.new("RGB", (SW, SH), (255, 255, 255))
    chrome(img, "Moodboard")
    d = ImageDraw.Draw(img)
    f = fonts()
    d.text((290, 130), "· Palette: “Disco Nap”", font=f["ui"], fill=TERRA if n else GREY_TXT, anchor="ls")
    x0, x1 = 60, 1120
    w = (x1 - x0) / 5
    for i in range(5):
        a = x0 + i * w
        if i < n:
            d.rounded_rectangle((a + 10, 190, a + w - 10, 760), radius=22, fill=DISCO[i])
            d.text((a + 30, 820), "#%02X%02X%02X" % DISCO[i], font=f["hex"], fill=INK, anchor="ls")
            d.text((a + 30, 860), DISCO_NAMES[i], font=f["small"], fill=GREY_TXT, anchor="ls")
        else:
            d.rounded_rectangle((a + 10, 190, a + w - 10, 760), radius=22, fill=(0xEE, 0xED, 0xEB))
    chat_side(img)
    return img


# ---------------------------------------------------------------- tablet (portrait, 600 x 800)
# ---------------------------------------------------------------- overlays (1080 x 1920)
# ---------------------------------------------------------------- subtitles (Video Sequencer text strips)
CAPTION_FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"   # also loaded by Blender for the text strips
CAPTION_SIZE = 62            # px at 1080 x 1920
CAPTION_WRAP = 860           # px: lines are broken here (max 2 lines), Blender gets the explicit line breaks


def caption_lines(text):
    f = ImageFont.truetype(CAPTION_FONT, CAPTION_SIZE)
    lines = wrap(text, f, CAPTION_WRAP)
    assert len(lines) <= 2, (text, lines)
    if len(lines) == 2:                      # balance the two lines (no one-word orphans)
        words = text.split(" ")
        cuts = [(" ".join(words[:k]), " ".join(words[k:])) for k in range(1, len(words))]
        lines = list(min(cuts, key=lambda c: max(f.getlength(c[0]), f.getlength(c[1]))))
    return lines


def card():
    img = Image.new("RGBA", (VW, VH), PAPER + (255,))
    d = ImageDraw.Draw(img)
    fl = font(HELVETICA_NEUE, 64, HN_BOLD)
    fb = font(HELVETICA_NEUE, 132, HN_BOLD)
    fs = font(HELVETICA_NEUE, 54, HN_MEDIUM)
    x0 = 110
    y = 820
    d.rectangle((x0, y - 70, x0 + 120, y - 58), fill=PEACH + (255,))
    d.text((x0, y), "Episode 2", font=fl, fill=TERRA + (255,), anchor="ls")
    d.text((x0, y + 170), "Surprise me.", font=fb, fill=INK + (255,), anchor="ls")
    em = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    ImageDraw.Draw(em).text((10, 10), "\U0001FAA9", font=ImageFont.truetype(EMOJI, 160), embedded_color=True)
    em = em.resize((140, 140), Image.LANCZOS)
    img.alpha_composite(em, (int(x0 + fb.getlength("Surprise me.") + 20), y + 50))
    d.text((x0, y + 280), "Voice in. Party out.", font=fs, fill=GREY_TXT + (255,), anchor="ls")
    d.text((x0, y + 350), "Moodboard: saved.", font=fs, fill=GREY_TXT + (255,), anchor="ls")
    for i, c in enumerate(DISCO):
        d.rounded_rectangle((x0 + i * 120, y + 420, x0 + i * 120 + 100, y + 520), radius=18, fill=c + (255,))
    return img


def key_cap():
    img = Image.new("RGB", (256, 256), TERRA)
    d = ImageDraw.Draw(img)
    mic_glyph(d, 128, 128, 150, (255, 255, 255))
    return img


# ---------------------------------------------------------------- sound effects (48 kHz mono)
RATE = 48000


def write_wav(path, x):
    import wave
    x = np.clip(x, -1, 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((x * 32767).astype("<i2").tobytes())


def _t(sec):
    return np.arange(int(sec * RATE)) / RATE


def lowpass(x, k):
    k = max(1, int(k))
    return np.convolve(x, np.ones(k) / k, mode="same")


def sfx_clock():
    """Tick-tock, one per second, 4 s."""
    x = np.zeros(int(4 * RATE))
    rng = np.random.default_rng(1)
    for i in range(4):
        n = int(0.025 * RATE)
        t = np.arange(n) / RATE
        hz = 3200 if i % 2 == 0 else 2400
        s = (np.sin(2 * np.pi * hz * t) + 0.5 * rng.normal(0, 1, n)) * np.exp(-t / 0.004)
        a = int(i * RATE)
        x[a:a + n] += 0.35 * s
    return x


def sfx_scratch():
    t = _t(0.55)
    rng = np.random.default_rng(2)
    f = 900 * np.exp(-t * 5) + 120 + 300 * np.sin(2 * np.pi * 9 * t) * (t < 0.25)
    ph = 2 * np.pi * np.cumsum(f) / RATE
    saw = 2 * ((ph / (2 * np.pi)) % 1) - 1
    noise = lowpass(rng.normal(0, 1, len(t)), 6)
    x = (0.6 * saw + 0.5 * noise) * np.minimum(1, t / 0.01) * np.exp(-t / 0.35)
    return 0.9 * x / np.abs(x).max()


def sfx_step():
    t = _t(0.16)
    rng = np.random.default_rng(4)
    thump = np.sin(2 * np.pi * (90 - 200 * t) * t) * np.exp(-t / 0.03)
    click = lowpass(rng.normal(0, 1, len(t)), 3) * np.exp(-t / 0.008)
    x = 0.8 * thump + 0.25 * click
    return 0.6 * x / np.abs(x).max()


def sfx_whoosh():
    t = _t(0.4)
    rng = np.random.default_rng(5)
    n = rng.normal(0, 1, len(t))
    env = np.sin(np.pi * t / t[-1]) ** 2
    x = lowpass(n, 10) * env + 0.3 * n * env ** 3
    return 0.7 * x / np.abs(x).max()


def sfx_chip():
    """Fast, squeaky 'cleaning montage' tune: 3.4 s, 200 bpm square-wave arpeggios."""
    dur = 3.4
    x = np.zeros(int(dur * RATE))
    step = 60 / 200 / 2
    notes = [1046.5, 1318.5, 1568.0, 2093.0, 1568.0, 1318.5, 1174.7, 1568.0]
    i = 0
    while i * step < dur:
        a = int(i * step * RATE)
        n = min(len(x) - a, int(step * 0.9 * RATE))
        t = np.arange(n) / RATE
        hz = notes[i % len(notes)] * (1.06 if (i // 8) % 2 else 1.0)
        x[a:a + n] += 0.22 * np.sign(np.sin(2 * np.pi * hz * t)) * np.exp(-t / 0.08)
        if i % 2 == 0:
            m = min(len(x) - a, int(0.03 * RATE))
            x[a:a + m] += 0.12 * np.random.default_rng(i).normal(0, 1, m) * np.exp(-np.arange(m) / (0.006 * RATE))
        i += 1
    return 0.8 * x / np.abs(x).max()


def sfx_sneeze():
    """Tiny 'ah-choo': rising 'ah' (0.35 s) then a sharp 'choo' burst."""
    rng = np.random.default_rng(6)
    t1 = _t(0.35)
    f = 420 + 380 * t1 / t1[-1]
    ph = 2 * np.pi * np.cumsum(f) / RATE
    ah = (np.sin(ph) + 0.5 * np.sin(2 * ph) + 0.25 * np.sin(3 * ph)) * np.minimum(1, t1 / 0.15) * 0.35
    ah += 0.08 * lowpass(rng.normal(0, 1, len(t1)), 4)
    t2 = _t(0.22)
    choo = rng.normal(0, 1, len(t2)) - lowpass(rng.normal(0, 1, len(t2)), 8)
    choo = choo * np.exp(-t2 / 0.05) * 0.9 + np.sin(2 * np.pi * 900 * t2) * np.exp(-t2 / 0.04) * 0.4
    x = np.concatenate([ah, np.zeros(int(0.04 * RATE)), choo])
    return 0.85 * x / np.abs(x).max()


SFX = {"clock.wav": sfx_clock, "scratch.wav": sfx_scratch, "step.wav": sfx_step, "whoosh.wav": sfx_whoosh,
       "chip.wav": sfx_chip, "sneeze.wav": sfx_sneeze}


def build():
    for sub in ("overlays/screens", "overlays", "audio/sfx"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    s = OUT / "overlays" / "screens"
    for old in list(s.glob("mic_*.png")):
        old.unlink()
    screen_empty().save(s / "empty.png", optimize=True)
    mic_overlay(None).save(s / "mic_idle.png", optimize=True)
    for k in range(6):
        mic_overlay(k).save(s / ("mic_%d.png" % k), optimize=True)
        screen_confetti(k).save(s / ("confetti_%d.png" % k), optimize=True)
        screen_palette(k).save(s / ("palette_%d.png" % k), optimize=True)
    for k in range(4):
        screen_flicker(k).save(s / ("flicker_%d.png" % k), optimize=True)
    screen_confetti(0, frozen=True).save(s / "confetti_frozen.png", optimize=True)
    screen_moodboard().save(s / "moodboard.png", optimize=True)
    o = OUT / "overlays"
    for old in list(o.glob("*.png")):
        old.unlink()
    caps = {name: {"who": "girl", "lines": caption_lines(t)} for name, t in SUBS.items()}
    caps.update({name: {"who": "claude", "lines": caption_lines(t)} for name, t in BUBBLES.items()})
    (o / "captions.json").write_text(json.dumps(caps, indent=1, ensure_ascii=False))
    card().save(o / "card.png", optimize=True)
    key_cap().save(OUT / "overlays" / "key_mic.png", optimize=True)
    for name, fn in SFX.items():
        write_wav(OUT / "audio" / "sfx" / name, fn())
    print("written to", OUT)


if __name__ == "__main__":
    build()
