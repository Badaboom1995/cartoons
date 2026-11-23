#!/usr/bin/env python3
"""Numeric checks for the poster colours (no viewing needed).

    python3 scripts/check_textures.py [ORIGINALS_DIR]

ORIGINALS_DIR (optional) holds the pre-colour posters; with it, also checks that the layout did
not move: ink masks (pixels that differ from each poster's own paper) match except at the accent.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_textures import INK, OUT, PAPER, POSTER_ACCENTS  # noqa: E402

SIZE = (1200, 1800)
INK_COV = 0.15      # a pixel is "ink" if it is more than 15% of the way from its paper to black ink
HEX_TOL = 4         # measured vs intended colour, per channel
# planned accent coverage, % of poster area
PLAN = {
    "poster_eyechart.png": (0.02, 0.3),    # small detail: one row of small letters
    "poster_lorem.png": (0.1, 1.0),        # one ornament
    "poster_chtoby.png": (0.3, 2.0),       # the main object, one big glyph
    "poster_kerning.png": (0.4, 1.5),      # a block in the gap
    "poster_rams.png": (0.01, 0.1),        # a single comma
}
# accent vs paper contrast where the accent is text (WCAG 2): 4.5 small text, 3.0 large text
TEXT_MIN = {"poster_eyechart.png": 4.5, "poster_chtoby.png": 3.0, "poster_rams.png": 3.0}
BODY_MIN = 4.5      # black ink vs paper, every poster (covers the small text on coloured paper)


def lum(c):
    c = np.array(c, float) / 255
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return float(c @ [0.2126, 0.7152, 0.0722])


def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def hexs(c):
    return "#%02X%02X%02X" % tuple(c)


def ink_mask(a, paper):
    full = np.abs(np.array(INK) - np.array(paper)).max()
    return np.abs(a - np.array(paper)).max(-1) / full > INK_COV


def to_segment(a, p, q):
    """Distance of each pixel to the mix line p..q, and how far along it (0 = p, 1 = q)."""
    p, q = np.array(p, float), np.array(q, float)
    t = np.clip(((a - p) @ (q - p)) / ((q - p) @ (q - p)), 0, 1)
    return np.linalg.norm(a - (p + t[..., None] * (q - p)), axis=-1), t


def grow(m, r=3):
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out |= np.roll(np.roll(m, dy, 0), dx, 1)
    return out


def main(orig_dir=None):
    ok = True
    for name, (paper, accent, what) in POSTER_ACCENTS.items():
        img = Image.open(OUT / name)
        assert img.size == SIZE, (name, img.size)
        a = np.asarray(img.convert("RGB")).astype(int)
        # accent = lies nearer the paper..accent mix line than the paper..ink one, past half coverage;
        # anti-aliased black edges and greys sit on the paper..ink line and stay neutral
        d_ink, t_ink = to_segment(a, paper, INK)
        d_acc, t_acc = to_segment(a, paper, accent)
        acc = (d_acc < d_ink) & (t_acc > 0.5)
        cls = np.where(acc, 2, np.where(ink_mask(a, paper), 1, 0))
        n = a[..., 0].size
        pct, pct_paper = 100 * acc.sum() / n, 100 * (cls == 0).sum() / n
        paper_meas = tuple(int(v) for v in np.median(a[cls == 0], 0))
        solid = np.abs(a - np.array(accent)).max(-1) <= 24
        acc_meas = tuple(int(v) for v in np.median(a[solid & acc], 0))
        ys, xs = np.nonzero(acc)
        cr, body = contrast(accent, paper), contrast(INK, paper)
        checks = [max(abs(m - i) for m, i in zip(acc_meas, accent)) <= HEX_TOL,
                  max(abs(m - i) for m, i in zip(paper_meas, paper)) <= HEX_TOL,
                  PLAN[name][0] <= pct <= PLAN[name][1], body >= BODY_MIN]
        line = (f"{name:20s} paper {hexs(paper)} meas {hexs(paper_meas)} ({pct_paper:.1f}%)  "
                f"accent {hexs(accent)} meas {hexs(acc_meas)} {pct:.3f}% of poster, "
                f"{100 * acc.sum() / max(1, (cls != 0).sum()):.1f}% of marks, "
                f"bbox x{xs.min()}-{xs.max()} y{ys.min()}-{ys.max()}  "
                f"ink/paper {body:.2f}  accent/paper {cr:.2f}")
        if name in TEXT_MIN:
            checks.append(cr >= TEXT_MIN[name])
            line += f" (text, needs {TEXT_MIN[name]})"
        if orig_dir:
            o = np.asarray(Image.open(Path(orig_dir) / name).convert("RGB")).astype(int)
            diff = ink_mask(o, PAPER) != ink_mask(a, paper)
            outside = int((diff & ~grow(acc)).sum())
            line += f"  mask diff {int(diff.sum())} px, outside accent {outside}"
            checks.append(outside == 0)
        ok &= all(checks)
        print("OK  " if all(checks) else "FAIL", line)
    return ok


if __name__ == "__main__":
    sys.exit(0 if main(sys.argv[1] if len(sys.argv) > 1 else None) else 1)
