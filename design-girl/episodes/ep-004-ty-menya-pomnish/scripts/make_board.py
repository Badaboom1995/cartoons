"""Textures for the evening props of EP4: the scribbled whiteboard and the sketch sheets on the desk.

Run with any Python 3 that has Pillow (not Blender's):
    python3 EP/scripts/make_board.py
Writes EP/assets/board_drawn.png and EP/assets/paper_1..4.png. Deterministic: same seed, same pictures.

Everything is drawn in fat, simple marker strokes, so it reads on a phone as "she drew all of this" rather than as
small text: schemes of boxes and arrows, a timeline of their half year, logo sketches crossed out and circled.
The first lines she draws in shot 16 (ep4.BOARD_STROKES_16, read from ep4.py without Blender) are on the evening board
in the same place and the same width, so the viewer recognises the beginning: the banner box and the arrow out of it.
"""
import ast
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

EP = Path(__file__).resolve().parents[1]
ASSETS = EP / "assets"

BOARD_SIZE_M = (0.85, 0.72)          # must match BOARD_SIZE in stage.py: a mobile board in the corner by the lamp
BOARD_UNITS = 1000                   # the board is laid out 1000 units wide, whatever its pixel size
BOARD_PX = (1600, round(1600 * BOARD_SIZE_M[1] / BOARD_SIZE_M[0]))
MARKER_STROKE_M = 0.010              # must match STROKE_WIDTH in stage.py: the lines of shot 16
PAPER_PX = (600, 848)                # A4 proportions
SS = 2                               # supersampling, for clean anti-aliased strokes

BLACK = (34, 36, 44)
BLUE = (36, 84, 196)
RED = (214, 52, 44)
GREEN = (30, 138, 78)
ORANGE = (232, 120, 52)
PENCIL = (92, 92, 104)

FONT_CANDIDATES = (                  # the first one that has Cyrillic wins
    "/System/Library/Fonts/Supplemental/Comic Sans MS Bold.ttf",
    "/System/Library/Fonts/Noteworthy.ttc",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
)


def font(size):
    for path in FONT_CANDIDATES:
        try:
            f = ImageFont.truetype(path, size * SS)
        except OSError:
            continue
        if f.getbbox("Б") != f.getbbox("\u0378"):      # a missing glyph draws the same box as any other
            return f
    return ImageFont.load_default()


class Marker:
    """Wobbly marker strokes on a supersampled canvas. Coordinates are in final pixels."""

    def __init__(self, size, background, seed, k=1.0):
        """k: pixels per layout unit. Coordinates, stroke widths and text sizes are all in layout units."""
        self.size = size
        self.k = k
        self.img = Image.new("RGB", (size[0] * SS, size[1] * SS), background)
        self.draw = ImageDraw.Draw(self.img)
        self.rnd = random.Random(seed)

    def _wobble(self, pts, amount):
        out = []
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            length = math.hypot(x1 - x0, y1 - y0)
            steps = max(1, int(length / 18))
            nx, ny = (-(y1 - y0) / length, (x1 - x0) / length) if length else (0, 0)
            phase = self.rnd.uniform(0, 6.3)
            for i in range(steps):
                t = i / steps
                w = amount * math.sin(phase + t * 3.1) * min(1.0, 4 * t * (1 - t) + 0.25)
                out.append((x0 + (x1 - x0) * t + nx * w, y0 + (y1 - y0) * t + ny * w))
        out.append(pts[-1])
        return out

    def line(self, pts, colour, width=12, wobble=2.0):
        pts = self._wobble([tuple(p) for p in pts], wobble)
        scaled = [(x * SS * self.k, y * SS * self.k) for x, y in pts]
        w = int(width * SS * self.k)
        self.draw.line(scaled, fill=colour, width=w, joint="curve")
        for x, y in (scaled[0], scaled[-1]):
            self.draw.ellipse((x - w / 2, y - w / 2, x + w / 2, y + w / 2), fill=colour)

    def arrow(self, a, b, colour, width=12, head=34, bend=0.0):
        mid = ((a[0] + b[0]) / 2 - (b[1] - a[1]) * bend, (a[1] + b[1]) / 2 + (b[0] - a[0]) * bend)
        pts = [quad(a, mid, b, i / 16) for i in range(17)]
        self.line(pts, colour, width)
        ang = math.atan2(b[1] - pts[-3][1], b[0] - pts[-3][0])
        for side in (-1, 1):
            a2 = ang + math.pi + side * 0.5
            self.line([b, (b[0] + head * math.cos(a2), b[1] + head * math.sin(a2))], colour, width, wobble=0.5)

    def box(self, x, y, w, h, colour, width=12):
        j = lambda: self.rnd.uniform(-5, 5)
        self.line([(x + j(), y + j()), (x + w + j(), y + j()), (x + w + j(), y + h + j()), (x + j(), y + h + j()),
                   (x + 6, y + j())], colour, width)

    def circle(self, cx, cy, r, colour, width=12, turns=1.08, squash=1.0):
        start = self.rnd.uniform(0, 6.3)
        pts = []
        n = 48
        for i in range(int(n * turns) + 1):
            a = start + 2 * math.pi * i / n
            rr = r * (1 + 0.04 * math.sin(3 * a + start))
            pts.append((cx + rr * math.cos(a), cy + rr * squash * math.sin(a)))
        self.line(pts, colour, width, wobble=1.0)

    def scribble_text(self, x, y, length, colour, width=8, lines=1, gap=34):
        """Handwriting seen from afar: a wavy line with small loops."""
        for row in range(lines):
            ln = length * self.rnd.uniform(0.6, 1.0) if row == lines - 1 and lines > 1 else length
            pts = []
            for i in range(int(ln / 6) + 1):
                t = i * 6
                pts.append((x + t, y + row * gap + 9 * math.sin(t / 9 + row) + 4 * math.sin(t / 3.3)))
            self.line(pts, colour, width, wobble=0.5)

    def cross(self, cx, cy, r, colour, width=14):
        self.line([(cx - r, cy - r), (cx + r, cy + r)], colour, width)
        self.line([(cx + r, cy - r), (cx - r, cy + r)], colour, width)

    def tick(self, cx, cy, r, colour, width=14):
        self.line([(cx - r, cy), (cx - r * 0.3, cy + r * 0.7), (cx + r, cy - r * 0.8)], colour, width)

    def text(self, x, y, s, colour, size, angle=0.0):
        f = font(round(size * self.k))
        bbox = self.draw.textbbox((0, 0), s, font=f)
        layer = Image.new("RGBA", (bbox[2] + 20 * SS, bbox[3] + 20 * SS), (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((10 * SS, 10 * SS), s, font=f, fill=colour + (255,))
        layer = layer.rotate(angle, resample=Image.BICUBIC, expand=True)
        self.img.paste(layer, (int(x * SS * self.k), int(y * SS * self.k)), layer)

    def text_centred(self, cx, cy, s, colour, size, angle=0.0):
        f = font(round(size * self.k))
        bbox = self.draw.textbbox((0, 0), s, font=f)
        w, h = (bbox[2] - bbox[0]) / (SS * self.k), (bbox[3] + bbox[1]) / (SS * self.k)
        self.text(cx - w / 2 - 10, cy - h / 2 - 10, s, colour, size, angle)

    def save(self, path):
        self.img.resize(self.size, Image.LANCZOS).save(path, optimize=True)
        print("make_board: wrote", path)


def quad(a, m, b, t):
    return ((1 - t) ** 2 * a[0] + 2 * (1 - t) * t * m[0] + t * t * b[0],
            (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * m[1] + t * t * b[1])


# ---------------------------------------------------------------- the board
def contract(name):
    """A literal from scripts/ep4.py (which imports bpy, so it is parsed, not imported)."""
    tree = ast.parse((EP / "scripts" / "ep4.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise KeyError(name)


def board_units(x, y):
    """Board coordinates (metres from the centre, y up) to layout units (from the top left, y down)."""
    per_m = BOARD_UNITS / BOARD_SIZE_M[0]
    return ((x + BOARD_SIZE_M[0] / 2) * per_m, (BOARD_SIZE_M[1] / 2 - y) * per_m)


def star(m, cx, cy, r, colour, width=10):
    pts = []
    for i in range(11):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    m.line(pts, colour, width, wobble=1.0)


def heart(m, cx, cy, r, colour, width=10):
    pts = []
    for i in range(41):
        t = 2 * math.pi * i / 40
        x = 16 * math.sin(t) ** 3
        y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
        pts.append((cx + x * r / 16, cy + y * r / 16))
    m.line(pts, colour, width, wobble=0.6)


def smiley(m, cx, cy, r, colour, width=9):
    m.circle(cx, cy, r, colour, width)
    m.line([(cx - r * 0.35, cy - r * 0.25), (cx - r * 0.35, cy - r * 0.1)], colour, width)
    m.line([(cx + r * 0.35, cy - r * 0.25), (cx + r * 0.35, cy - r * 0.1)], colour, width)
    m.line([(cx - r * 0.5 + i * r / 10, cy + r * 0.25 + r * 0.25 * math.sin(math.pi * i / 10)) for i in range(11)],
           colour, width, wobble=0.3)


def lightning(m, cx, cy, r, colour, width=10):
    m.line([(cx + r * 0.2, cy - r), (cx - r * 0.4, cy + r * 0.1), (cx + r * 0.3, cy + r * 0.05), (cx - r * 0.2, cy + r)],
           colour, width, wobble=0.5)


def logo_sketch(m, kind, cx, cy, r, colour):
    if kind == "ring":
        m.circle(cx, cy, r, colour, 12)
        m.circle(cx, cy, r * 0.55, colour, 10)
    elif kind == "triangle":
        m.line([(cx, cy - r), (cx + r * 0.95, cy + r * 0.7), (cx - r * 0.95, cy + r * 0.7), (cx, cy - r)], colour, 12)
        m.circle(cx, cy + r * 0.2, r * 0.3, colour, 10)
    elif kind == "leaf":
        m.line([quad((cx - r, cy + r), (cx - r, cy - r), (cx + r, cy - r), i / 12) for i in range(13)], colour, 12)
        m.line([quad((cx + r, cy - r), (cx + r, cy + r), (cx - r, cy + r), i / 12) for i in range(13)], colour, 12)
        m.line([(cx - r * 0.8, cy + r * 0.8), (cx + r * 0.5, cy - r * 0.5)], colour, 9)
    elif kind == "letter":
        m.circle(cx, cy, r, colour, 12)
        m.line([(cx - r * 0.45, cy + r * 0.5), (cx, cy - r * 0.55), (cx + r * 0.45, cy + r * 0.5)], colour, 12)
        m.line([(cx - r * 0.25, cy + r * 0.12), (cx + r * 0.25, cy + r * 0.12)], colour, 10)
    elif kind == "flower":
        for i in range(5):
            a = 2 * math.pi * i / 5
            m.circle(cx + r * 0.5 * math.cos(a), cy + r * 0.5 * math.sin(a), r * 0.42, colour, 9)
        m.circle(cx, cy, r * 0.22, colour, 9)
    elif kind == "squares":
        m.box(cx - r, cy - r, r * 1.2, r * 1.2, colour, 11)
        m.box(cx - r * 0.2, cy - r * 0.2, r * 1.2, r * 1.2, colour, 11)


def board():
    """The evening board: everything she told him in one day. Laid out on a BOARD_UNITS-wide grid."""
    k = BOARD_PX[0] / BOARD_UNITS
    w, h = BOARD_UNITS, BOARD_PX[1] / k
    m = Marker(BOARD_PX, (247, 247, 244), seed=4, k=k)

    # a faint ghost of older, wiped drawings: a lived-in board
    ghost = (226, 228, 230)
    for _ in range(8):
        x, y = m.rnd.uniform(30, w - 220), m.rnd.uniform(40, h - 80)
        m.scribble_text(x, y, m.rnd.uniform(90, 180), ghost, width=8)

    # --- shot 16: the banner box and the arrow out of it, exactly where and as thick as she drew them
    width = MARKER_STROKE_M * BOARD_UNITS / BOARD_SIZE_M[0]
    strokes = [[board_units(x, y) for x, y in line] for line in contract("BOARD_STROKES_16")]
    for line in strokes:
        m.line(line, BLACK, width, wobble=0.0)
    box = strokes[0]
    bx0, bx1 = min(x for x, _ in box), max(x for x, _ in box)
    by0, by1 = min(y for _, y in box), max(y for _, y in box)
    tip = max(strokes[1], key=lambda p: p[0])

    # later that day: БАННЕР written into the box, underlined in red, and "как в тот раз" under it
    m.text_centred((bx0 + bx1) / 2, (by0 + by1) / 2 - 10, "БАННЕР", RED, 44, angle=2)
    m.line([(bx0 + 34, by1 - 30), (bx1 - 34, by1 - 33)], RED, 7)
    m.text(bx0 - 6, by0 - 78, "как в тот раз", BLUE, 34, angle=-3)      # above the box: the space under it is
    m.line([(bx0 - 2, by0 - 18), (bx1 - 4, by0 - 24)], BLUE, 7)        # for the scheme and the versions

    # where the arrow points: the logo she settled on, circled, with exclamation marks
    chosen = (tip[0] + 88, tip[1])
    logo_sketch(m, "letter", chosen[0], chosen[1], 40, BLACK)
    m.circle(chosen[0], chosen[1], 60, GREEN, 10, turns=1.2)
    m.text(chosen[0] - 30, chosen[1] - 128, "!!!", GREEN, 40, angle=-10)       # above it: below are the versions
    m.scribble_text(330, 205, 300, BLACK, width=7, lines=2, gap=34)                 # notes over the banner

    # --- top band: the timeline of their half year together, left to right
    y0 = 118
    m.arrow((36, y0), (962, y0 + 4), BLACK, width=11, head=30)
    icons = (heart, star, smiley, lightning, heart)
    colours = (RED, ORANGE, BLUE, ORANGE, GREEN)
    for i, (icon, colour) in enumerate(zip(icons, colours)):
        x = 100 + i * 190
        m.line([(x, y0 - 18), (x, y0 + 18)], BLACK, 8)
        icon(m, x, y0 - 48, 22, colour, width=8)
        m.scribble_text(x - 36, y0 + 38, 72, BLUE, width=6)

    # --- left of the banner: the logos she threw out, crossed
    kinds = ("ring", "triangle", "leaf", "flower", "squares", "ring")
    spots = [(78 + 128 * (i % 2), 270 + 112 * (i // 2)) for i in range(6)]
    for kind, (cx, cy) in zip(kinds, spots):
        logo_sketch(m, kind, cx, cy, 38, BLACK)
        m.cross(cx, cy, 42, RED, 9)

    # --- bottom, below the banner: the scheme on the left, versions and a doodle of Clawd on the right
    low = max(by1 + 30, 612)
    for x, y, bw, bh in ((40, 0, 170, 68), (40, 104, 170, 68), (272, 50, 180, 74)):
        m.box(x, low + y, bw, bh, BLUE, 11)
        m.scribble_text(x + 22, low + y + 22, bw - 50, BLACK, width=7, lines=2, gap=24)
    m.arrow((212, low + 34), (272, low + 80), BLACK, 10, head=24, bend=-0.15)
    m.arrow((212, low + 138), (272, low + 104), BLACK, 10, head=24, bend=0.15)
    m.text(458, low + 50, "?!", RED, 44, angle=8)
    vx = max(bx1 + 30, 690)
    for i, verdict in enumerate(("x", "x", "ok")):
        x = vx + i * 98
        m.box(x, low + 6, 80, 58, BLACK, 9)
        m.text(x + 10, low + 8, "v%d" % (i + 2), BLACK, 30)
        if verdict == "x":
            m.cross(x + 40, low + 35, 30, RED, 10)
        else:
            m.circle(x + 40, low + 35, 50, GREEN, 10)
    m.tick(vx + 236, low + 112, 24, GREEN, 12)
    cx, cy = vx + 60, low + 150
    m.box(cx - 46, cy - 30, 92, 58, ORANGE, 10)
    m.line([(cx - 16, cy - 12), (cx - 16, cy + 2)], BLACK, 10)
    m.line([(cx + 16, cy - 12), (cx + 16, cy + 2)], BLACK, 10)
    for lx in (cx - 32, cx - 11, cx + 11, cx + 32):
        m.line([(lx, cy + 28), (lx, cy + 40)], ORANGE, 8)
    heart(m, cx + 90, cy - 6, 18, RED, 8)
    m.save(ASSETS / "board_drawn.png")


# ---------------------------------------------------------------- the sheets on the desk
def paper(index, seed):
    w, h = PAPER_PX
    tint = ((250, 249, 243), (246, 247, 250), (250, 246, 238), (248, 248, 246))[index - 1]
    m = Marker(PAPER_PX, tint, seed)
    if index == 1:                   # a grid of banner thumbnails
        for row in range(4):
            for col in range(2):
                x, y = 50 + col * 270, 60 + row * 190
                m.box(x, y, 230, 140, PENCIL, 6)
                m.scribble_text(x + 24, y + 40, 150, BLACK, width=5)
                m.circle(x + 180, y + 95, 22, (RED, BLUE)[(row + col) % 2], 6)
                if (row, col) in ((0, 1), (2, 0), (3, 1)):
                    m.cross(x + 115, y + 70, 60, RED, 7)
    elif index == 2:                 # logo variants
        kinds = ("ring", "triangle", "leaf", "letter", "flower", "squares")
        for i, kind in enumerate(kinds):
            cx, cy = 160 + (i % 2) * 280, 150 + (i // 2) * 260
            logo_sketch(m, kind, cx, cy, 70, BLACK if i % 3 else BLUE)
        m.circle(440, 410, 120, RED, 8)
    elif index == 3:                 # notes and arrows
        for row in range(9):
            m.scribble_text(60, 70 + row * 74, m.rnd.uniform(300, 470), BLUE, width=5)
        m.arrow((420, 420), (530, 600), RED, 8, head=26, bend=0.2)
        star(m, 480, 700, 50, ORANGE, 7)
    else:                            # one big banner layout
        m.box(50, 120, 500, 300, BLACK, 8)
        m.line([(90, 170), (330, 170)], RED, 18)
        m.scribble_text(90, 230, 300, BLACK, width=6, lines=3, gap=40)
        m.circle(440, 300, 70, BLUE, 7)
        m.arrow((300, 560), (300, 440), BLACK, 7, head=24)
        m.scribble_text(70, 620, 420, PENCIL, width=5, lines=3, gap=42)
    m.save(ASSETS / ("paper_%d.png" % index))


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    board()
    for i in range(1, 5):
        paper(i, seed=40 + i)


if __name__ == "__main__":
    main()
