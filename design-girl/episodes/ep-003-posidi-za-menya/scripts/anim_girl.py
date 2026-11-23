"""EP3: her whole performance on STU_Designer_Rig, the cup, the key-press finger, and the short laptop pull in shot 23.

The acting is written as one chronological script in perform(): to(frame, duration, channel=value) moves a channel so
it arrives on that frame, cut(frame, ...) jumps on a cut. Every frame is derived from timeline.json, so a retime only
needs a rebuild. A later move interrupts an earlier one on the same channel. Channels are solved (two-bone arms) and keyed.

Face: eyes are white + pupil + lid meshes whose gaze, size and lid are shape keys; ^_^ is the Studio "delighted" set; a
blink is a soft arc. The mouth is one mesh with shape keys (open, smile, smirk, sad), so a smile can creep and slide.
Her exit is to frame left, behind the desk line; off stage she is parked behind the back wall so she casts no shadow.
"""
import bisect
import math
import random
import wave
from collections import namedtuple

import bpy
import numpy as np
from mathutils import Matrix, Vector

import ep3

SEAT = (0.0, 0.6, -0.11)
DESK_Z = 0.72
PARK = (0.0, 8.0, 0.0)
ACTION = ep3.PREFIX + "Girl"

# ---------------------------------------------------------------- hand targets (armature space: wrist, tip, elbow pole)
# She holds the mug the way people do: the mitt wraps its side. The palm lies on the wall on the handle side, the handle
# sits in the palm, the hand's long axis runs along the wall and the end of the mitt curls round to the front.
CUP_SCALE = 1.3                              # a big cozy mug, set at build time
CUP_RADIUS = 0.04 * CUP_SCALE
PALM_OVERLAP = 0.002                         # how far the palm presses into the wall
PALM_AT = -0.035                             # where along the mitt (from its end) the palm touches the handle side
PALM_HALF = 0.04                             # half the mitt's thickness
GRIP_Z = 0.0495 * CUP_SCALE                  # the middle of the handle above the base
HAND_LENGTH = 0.14
# wrist in the mug's own axes: x towards the handle, y towards her forearm
GRIP_WRIST = Vector((CUP_RADIUS - PALM_OVERLAP + PALM_HALF, PALM_AT + HAND_LENGTH, GRIP_Z))
HOLD_PSI = 16.0                              # where the handle points: out to her left, a little back towards her
LEFT_PSI = 34.0                              # walking to frame left her hand is on the camera side: it slides back so the mug shows
MOUTH_PSI = -30.0                            # at her lips the wrist comes forward, so the hand stays outside her cheek
MOUTH_TILT = 18.0                            # the mug leans towards her lips
HOLD_POLE = (0.15, 0.6, -1.0)                # the elbow hangs low, relaxed near her ribs
MOUTH_POLE = (0.9, 0.2, -0.5)                # drinking, the elbow lifts out to her side


def desk(x, y, z):
    return (x, y - SEAT[1], z + DESK_Z - SEAT[2])


def hand(wrist, tip, side, pole=None):
    sx = 1 if side == "L" else -1
    return (*desk(*wrist), *desk(*tip), *(pole or (0.5 * sx, 0.3, -1.0)))


def up(h, dz):
    return (h[0], h[1], h[2] + 0.6 * dz, h[3], h[4], h[5] + dz, h[6], h[7], h[8])


def down(sx, a=0.0):
    """Arm hanging at her side, swung forward by a degrees."""
    r = math.radians(a)
    w = (sx * 0.33, -0.42 * math.sin(r), 1.0 - 0.44 * math.cos(r))
    return (*w, w[0], w[1] - 0.03, w[2] - 0.13, sx * 0.3, 1.0, 0.05)


def cup_pose(base, psi=HOLD_PSI, tilt=0.0, pole=HOLD_POLE):
    """The left hand wrapped round a mug standing at base: its target, the way its thumb points, and the closed mitt."""
    turn = Matrix.Rotation(math.radians(-tilt), 3, "X") @ Matrix.Rotation(math.radians(psi), 3, "Z")
    w = Vector(base) + turn @ GRIP_WRIST
    t = w + turn @ Vector((0.0, -0.13, 0.0))
    return dict(L=(*w, *t, *pole), thumb=tuple(turn @ Vector((0.0, 0.0, 1.0))), grip=1.0)


def slid(h, dx):
    """A hand target that stays where it is in the room while her body slides dx along the desk."""
    return (h[0] - dx, h[1], h[2], h[3] - dx, h[4], h[5], h[6], h[7], h[8])


KL = hand((0.08, 0.32, 0.10), (0.05, 0.19, 0.06), "L")
KR = hand((-0.08, 0.32, 0.10), (-0.05, 0.19, 0.06), "R")
KEY_SPOT = (-0.085, 0.19, 0.733)             # the key she presses in shot 2, on top of the keyboard (world)
PRESS = hand((-0.115, 0.31, 0.163), (KEY_SPOT[0], KEY_SPOT[1], KEY_SPOT[2] - DESK_Z), "R")
PUSH_R = hand((-0.16, 0.30, 0.07), (-0.12, 0.18, 0.03), "R")
FLICK_UP = hand((-0.30, 0.30, 0.30), (-0.38, 0.22, 0.40), "R", (-0.8, 0.3, -0.6))
FLICK_OUT = hand((-0.37, 0.28, 0.28), (-0.52, 0.22, 0.31), "R", (-0.8, 0.3, -0.6))
LAPTOP_L = hand((0.20, 0.14, 0.13), (0.19, 0.02, 0.09), "L")
LAPTOP_R = hand((-0.20, 0.14, 0.13), (-0.19, 0.02, 0.09), "R")
LAPTOP_PULL = 0.045
LAPTOP_L2 = hand((0.20, 0.14 + LAPTOP_PULL, 0.13), (0.19, 0.02 + LAPTOP_PULL, 0.09), "L")
LAPTOP_R2 = hand((-0.20, 0.14 + LAPTOP_PULL, 0.13), (-0.19, 0.02 + LAPTOP_PULL, 0.09), "R")
FIST_L = (0.15, -0.30, 0.90, 0.115, -0.335, 1.01, 0.9, 0.2, -0.6)     # both fists clenched at her chest on «Красиво»
FIST_R = (-0.15, -0.30, 0.90, -0.115, -0.335, 1.01, -0.9, 0.2, -0.6)

CUP_DESK = (0.60, 0.14)                      # its place on the desk: the cameras see it there, clear of the tablet
CUP_CHEST = (0.36, -0.43, 0.82)              # carried at mid-chest, 25 cm in front of her, on her left
CUP_TUCK = (0.20, -0.33, 0.86)               # close to her while she gets up: the shot 7 camera stands right in front of her
CUP_SEATED = (0.31, -0.48, 0.88)             # seated: above the desk, just right of the laptop lid in the wide
CUP_AT_MOUTH = Vector((0.05, -0.095, -0.15))  # mug base from her mouth: the near rim just under her lip, the mouth stays readable
REACH_LOC = (0.06, SEAT[1], SEAT[2])         # for the far end of the desk she shifts over and leans
REACH_TORSO = (9.0, 0.0, 9.0)


def desk_base(loc):
    """The mug's spot on the desk, in her armature's space when her rig is at loc."""
    return (CUP_DESK[0] - loc[0], CUP_DESK[1] - loc[1], DESK_Z - loc[2])


SEATED = (90.0, 90.0)                        # thigh angle, knee bend
STAND = (0.0, 0.0)

# head (pitch down, yaw to her left, roll to her left), degrees
H_LAPTOP = (11.0, -1.0, 0.0)
H_CLAWD = (10.0, -24.0, 0.0)
H_FREEZE = (6.0, -5.0, 0.0)                  # nearly square to the lens for the fisheye
T_REST = (4.0, 0.0, 0.0)
# gaze: pupil shift in the eye (x to her left, z up), metres
G_LAPTOP = (0.0, -0.012)
G_CLAWD = (-0.026, -0.008)
G_AHEAD = (0.0, -0.004)
LOOK_X, LOOK_Z = 0.03, 0.016
PUPIL_SMALL = 0.5
STAR_EYE = (0.105, 0.198)                    # centre of the star eye: the middle of her glasses lens
STAR_COLOR = (1.0, 0.80, 0.02, 1.0)

HER_MARK = (-0.93, 0.46)                     # the end of her shot 29 walk: Clawd looks here
PACE = 1.3                                   # moves were first timed for the fast cut; this is the calm one


# ---------------------------------------------------------------- channels
class Track:
    def __init__(self, value):
        self.keys = [(1, self._t(value))]

    @staticmethod
    def _t(v):
        return tuple(v) if isinstance(v, (tuple, list, Vector)) else (float(v),)

    def _from(self, f):
        """Continue from the value at f: anything keyed from f on is replaced."""
        value = self.at(f)
        self.keys = [k for k in self.keys if k[0] < f]
        self.keys.append((f, value))

    def to(self, f, dur, v):
        self._from(max(1, min(f - 1, f - dur)))
        self.keys.append((f, self._t(v)))

    def cut(self, f, v):
        self._from(f - 1)
        self.keys.append((f, self._t(v)))

    def key(self, f, v):
        self.keys.append((f, self._t(v)))

    def hold(self, f):
        self._from(f)

    def at(self, f):
        frames = [k[0] for k in self.keys]
        i = bisect.bisect_right(frames, f)
        if i == 0:
            return self.keys[0][1]
        if i == len(frames):
            return self.keys[-1][1]
        (a, va), (b, vb) = self.keys[i - 1], self.keys[i]
        t = (f - a) / (b - a)
        t = t * t * (3 - 2 * t)
        return tuple(x + (y - x) * t for x, y in zip(va, vb))

    def frames(self):
        return [k[0] for k in self.keys]


class Script:
    def __init__(self, stand_z, cup_mouth):
        self.z = stand_z
        self.t = {
            "loc": Track(SEAT), "yaw": Track(0.0), "torso": Track(T_REST), "head": Track(H_LAPTOP),
            "L": Track(KL), "R": Track(KR), "legL": Track(SEATED), "legR": Track(SEATED),
            "gaze": Track(G_LAPTOP), "lid": Track(0.30), "pupil": Track(1.0),
            "smile": Track(0.0), "smirk": Track(0.0), "sad": Track(0.0), "gape": Track(0.0), "wide": Track(0.0),
            "huge": Track(0.0), "round": Track(0.0), "finger": Track(0.0), "grip": Track(0.0), "thumb": Track((0.0, 0.0, 1.0)),
        }
        self.brows = [(1, "neutral")]
        self.eyes = [(1, "open")]
        self.mouth_cup = cup_mouth
        self.exit_edge = -1.31                  # world x of the wide frame's left edge along her exit line
        self.cup, self.laptop = {}, ()
        self.stars = ()
        self.press = None
        self.still, self.no_blink, self.blinks = [], [], []

    def _expand(self, kw):
        if "legs" in kw:
            legs = kw.pop("legs")
            kw["legL"] = kw["legR"] = legs
        return kw

    def to(self, f, dur, **kw):
        for k, v in self._expand(kw).items():
            self.t[k].to(f, dur, v)

    def cut(self, f, **kw):
        for k, v in self._expand(kw).items():
            self.t[k].cut(f, v)

    def brow(self, f, name):
        self.brows.append((f, name))

    def eye(self, f, mode):
        self.eyes.append((f, mode))

    def walk(self, a, b, p0, p1, via=None, cup=False, period=16, lift=0.035, swing=22.0, reach=None, settle=0, psi=HOLD_PSI):
        """reach=(frame, fraction of the path): be that far along on that frame, easing from slow to fast.
        settle: frames over which the cup hand eases from where it is into the carry."""
        settle_from = self.t["L"].at(a - 1)
        pts = [Vector(p0), Vector(via), Vector(p1)] if via else [Vector(p0), Vector(p1)]
        lengths = [(q - r).length for r, q in zip(pts, pts[1:])]

        def along(t):
            d = t * sum(lengths)
            for r, q, n in zip(pts, pts[1:], lengths):
                if d <= n:
                    return r + (q - r) * (d / n)
                d -= n
            return pts[-1]

        power = 1.0
        if reach:
            tau = (reach[0] - a) / (b - a)
            power = max(1.0, math.log(max(0.05, min(0.95, reach[1]))) / math.log(max(0.05, min(0.95, tau))))

        def place(f):
            return along(((f - a) / (b - a)) ** power)

        names = ["loc", "legL", "legR", "R", "L"]
        for n in names:
            self.t[n].hold(a - 1)
        for f in list(range(a, b, 2)) + [b]:
            ph = 2 * math.pi * (f - a) / period
            s = math.sin(ph)
            x, y = place(f)
            stride = 1.0
            if reach:                                  # short steps while she is slow, so the feet don't skate
                speed = (place(min(f + 1, b)) - place(max(f - 1, a))).length / 2
                stride = max(0.35, min(1.0, speed / 0.03))
            amp = swing * stride
            self.t["loc"].key(f, (x, y, self.z - lift * stride * s * s))
            self.t["legL"].key(f, (amp * s, 16.0 * stride * max(0.0, -s)))
            self.t["legR"].key(f, (-amp * s, 16.0 * stride * max(0.0, s)))
            self.t["R"].key(f, down(-1, amp * 0.9 * s))
            if cup:                                    # the arm soaks up most of the bounce, the cup only sways a little
                carry = cup_pose(Vector(CUP_CHEST) + Vector((0.0, 0.004 * s, 0.6 * lift * stride * s * s)), psi)["L"]
                if f - a < settle:
                    k = (f - a + 1) / settle
                    k = k * k * (3 - 2 * k)
                    carry = tuple(p + (q - p) * k for p, q in zip(settle_from, carry))
                self.t["L"].key(f, carry)
            else:
                self.t["L"].key(f, down(1, -amp * 0.9 * s))


# ---------------------------------------------------------------- timing, read from the timeline
Span = namedtuple("Span", "first last")


class Beats:
    """Shots and lines as frame spans, and where a line's second phrase starts in its audio."""

    def __init__(self, ctx):
        self.ctx = ctx

    def shot(self, shot_id):
        s = self.ctx.shot(shot_id)
        return Span(s["first_frame"], s["last_frame"])

    def line(self, line_id):
        l = self.ctx.line(line_id)
        return Span(l["first_frame"], l["last_frame"])

    def runs(self, line_id):
        """Voiced stretches of the line, in frames from its start."""
        e = envelope(self.ctx.audio_path(self.ctx.line(line_id)))
        on = e > max(0.03, float(e.max()) * 0.12)
        runs, start = [], None
        for i, v in enumerate(list(on) + [False]):
            if v and start is None:
                start = i
            elif not v and start is not None:
                runs.append((start, i - 1))
                start = None
        return runs

    def voiced_end(self, line_id):
        l = self.ctx.line(line_id)
        runs = self.runs(line_id)
        return l["first_frame"] + runs[-1][1] if runs else l["last_frame"]

    def phrase2(self, line_id):
        """First voiced frame after the longest pause inside the line (its middle if it has no pause)."""
        l = self.ctx.line(line_id)
        runs = self.runs(line_id)
        if len(runs) < 2:
            return (l["first_frame"] + l["last_frame"]) // 2
        k = max(range(len(runs) - 1), key=lambda j: runs[j + 1][0] - runs[j][1])
        return l["first_frame"] + runs[k + 1][0]


# ---------------------------------------------------------------- the performance
def perform(s, ctx):
    """Every frame here comes from a shot or a line. A reaction starts on its cut; what doesn't fit starts off camera."""
    Z, SZ = s.z, SEAT[2]
    to, cut, brow, eye = s.to, s.cut, s.brow, s.eye
    beats = Beats(ctx)
    S, V, P2 = beats.shot, beats.line, beats.phrase2
    D = lambda frames: max(1, round(frames * PACE))
    mouth = s.mouth_cup
    cup_near = tuple(Vector(mouth) + Vector((0.03, -0.01, -0.05)))

    # 0: the whole room. She is settled at the laptop: a lazy look away, and the join chime brings her eyes back
    s0, s1, s2, s3 = S(0), S(1), S(2), S(3)
    join = ctx.sfx("join")["first_frame"]
    to(join - 12, D(12), head=(9.5, 4.0, 1.5), gaze=(0.012, -0.004))
    to(join + D(3), D(4), gaze=G_LAPTOP)
    to(join + D(12), D(12), head=H_LAPTOP)
    to(join + 16, 3, R=up(KR, 0.012))
    to(join + 19, 3, R=KR)
    to(join + 24, 3, L=up(KL, 0.012))
    to(join + 27, 3, L=KL)

    # 1: the call. Stone face, eyes on the laptop
    to(s1.first + D(10), D(14), head=(12.0, 1.0, 0.0))
    to(s1.last - 2, D(14), head=(10.0, -2.0, 0.0))

    # 2: the key beat, while Viktor keeps talking. A skeptical stare, a slow eye roll, a small exhale, and without
    # looking away one finger finds a key: contact exactly on the click, a small dip, then it lifts. No smile
    key = ctx.sfx("key")["first_frame"]
    n2 = s2.last - s2.first
    at2 = lambda x: s2.first + round(n2 * x)
    stare_end = at2(0.20)
    roll_top, roll_end, back = at2(0.36), at2(0.50), at2(0.66)
    exhale, slumped = at2(0.52), at2(0.74)
    cut(s2.first, lid=0.46, gaze=G_LAPTOP, head=(11.0, -2.0, 0.0), smile=0.0, smirk=0.0)
    brow(s2.first, "hmm")
    brow(stare_end + 1, "eyeroll")
    to(roll_top, roll_top - stare_end, gaze=(-0.006, 0.016), lid=0.30)
    to(roll_end, roll_end - roll_top, gaze=(0.020, 0.013))
    to(roll_end, roll_end - stare_end, head=(8.0, -1.0, -4.0))
    to(back, back - roll_end, gaze=G_LAPTOP, lid=0.46, head=(11.0, -2.0, -1.0))
    brow(back - 2, "hmm")
    # (her hands are in frame: they take the opposite shift, so they stay on the keys while her body breathes)
    held = lambda h, dz: (h[0], h[1], h[2] - dz, h[3], h[4], h[5] - dz, h[6], h[7], h[8])
    sink = -0.007
    to(exhale, exhale - roll_top, torso=(3.0, 0.0, 0.0), loc=(0.0, 0.6, SZ + 0.004), L=held(KL, 0.004), R=held(KR, 0.004))
    to(slumped, slumped - exhale, torso=(6.0, 0.0, 0.0), loc=(0.0, 0.6, SZ + sink), L=held(KL, sink), R=held(KR, sink))
    on_key = held(PRESS, sink)
    hover = key - 5
    to(hover, 8, R=up(on_key, 0.03), finger=1.0)
    to(key, key - hover, R=on_key)
    to(key + 1, 1, R=held(on_key, 0.004))
    s.press = key

    # 3 (the screen): the hand lifts and goes home, her body settles
    to(key + 5, 4, R=up(on_key, 0.03))
    to(key + D(10), D(6), R=KR, finger=0.0)
    to(s3.first + D(10), D(8), torso=T_REST, loc=SEAT, L=KL)
    to(s3.last, D(10), head=(11.0, -2.0, 0.0))

    # 4: "Клод, если что, ответишь за меня? Я отойду." Turns on the cut, eyes first; the head lifts on the question,
    # and the sly smirk comes with "Я отойду"
    s4, v02 = S(4), V("v02")
    p = P2("v02")
    brow(s4.first, "hmm")
    to(s4.first + D(3), D(3), gaze=G_CLAWD, lid=0.12)
    to(s4.first + D(5), D(5), head=(8.0, -24.0, 3.0), torso=(3.0, -6.0, 0.0))
    to(p - D(2), D(7), head=(6.0, -24.0, 4.5))
    to(p + 1, D(6), smirk=0.5)
    to(p + D(3), D(4), head=(10.0, -25.0, 5.0))
    to(v02.last, D(6), head=(8.0, -24.0, 4.0))

    # 5 (off camera, his close-up): she waits for him, and without looking away takes her cup by the handle
    s5, s6, v04 = S(5), S(6), V("v04")
    to(s5.first + D(8), D(6), head=(8.0, -22.0, 6.0), smirk=0.38)
    day_took = s5.first + D(9)
    to(day_took, D(8), **cup_pose(desk_base(REACH_LOC)), torso=REACH_TORSO, loc=REACH_LOC, R=slid(KR, REACH_LOC[0]))
    to(day_took + D(11), D(9), **cup_pose(CUP_SEATED), torso=(3.0, -6.0, 0.0), loc=SEAT, R=KR)

    # 6: "Просто слушай. Если что-то спросят, отвечай коротко и по делу." Easy on the first phrase, rising through the
    # second, and one flick of the hand on "по делу"
    p = P2("v04")
    brow(s6.first, "smile")
    to(s6.first + D(4), D(5), lid=0.0, smirk=0.15)
    to(s6.first + D(6), D(6), smile=0.45)
    to(s6.first + D(6), D(5), head=(6.0, -25.0, 3.0))
    to(p - 1, D(6), head=(4.0, -24.0, 2.0))
    to(p + D(15), D(15), torso=(10.0, -4.0, 0.0), loc=(0.0, 0.585, SZ + 0.02), R=PUSH_R, head=(2.0, -20.0, 2.0))
    to(p + D(24), D(6), head=(4.0, -24.0, 2.0))
    to(p + D(30), D(6), head=(2.0, -20.0, 2.0))
    to(v04.last - D(3), D(18), torso=(7.0, -5.0, 0.0), loc=(0.0, 0.58, SZ + 0.05))
    flick = beats.voiced_end("v04") - D(4)
    to(flick - D(3), D(5), R=FLICK_UP)
    to(flick, D(3), R=FLICK_OUT)
    to(flick + D(3), D(3), R=FLICK_UP)
    to(s6.last, D(5), R=PUSH_R)

    # 7 (off camera): up, clear of the chair, turned to the door
    s7, s8, v26 = S(7), S(8), V("v26")
    up_at = s7.first + round((s7.last - s7.first) * 0.65)
    start = (-0.45, 0.64)
    to(up_at, up_at - s7.first, loc=(*start, Z), legs=STAND, torso=(3.0, 0.0, 0.0),
       **cup_pose(CUP_TUCK, LEFT_PSI), R=down(-1), head=(2.0, 18.0, 0.0), gaze=(0.0, -0.002), smirk=0.0)
    to(up_at + D(3), D(5), yaw=-70.0)                     # turns once she is past that camera

    # 8: "Я за кофе, скоро буду." Over her shoulder, at a calm walk. Her head is still in frame on the last word, and she
    # is gone before the timelapse starts, so only the light changes on the empty chair
    said = beats.voiced_end("v26")
    at_line_end, gone = s.exit_edge + 0.13, s.exit_edge - 0.36
    timelapse = s8.last - round(ctx.shot(8)["transition"]["seconds"] * ctx.fps) + 1
    left = timelapse - 3
    s.walk(up_at + 1, left, start, (gone, 0.62), cup=True, psi=LEFT_PSI, period=18, swing=22.0, settle=D(4),
           reach=(said, (start[0] - at_line_end) / (start[0] - gone)))
    cut(left + 1, loc=PARK, legs=STAND)
    to(v26.first, D(5), head=(4.0, 42.0, 0.0), gaze=(0.02, -0.004))
    to(said + D(4), D(4), head=(3.0, 18.0, 0.0))

    # 9: evening. Comes in cheerful with the cup, unhurried, and settles into the chair on the first word
    s9, v06 = S(9), V("v06")
    enter = s.exit_edge - 0.74                            # she and the cup she leads with start just outside the frame
    cut(s9.first, loc=(enter, 0.62, Z), yaw=75.0, torso=(1.0, 0.0, 0.0), head=(3.0, -20.0, 3.0), **cup_pose(CUP_CHEST),
        gaze=(-0.015, 0.0), lid=0.0, smile=0.85, legL=STAND, legR=STAND)
    brow(s9.first, "delighted")
    arrive = v06.first - 2
    s.walk(s9.first + 1, arrive, (enter, 0.62), (-0.62, 0.66), cup=True, period=16, lift=0.04, swing=20.0)
    to((s9.first + arrive) // 2, D(8), head=(3.0, -21.0, -2.0))
    to(arrive, D(8), head=(3.0, -20.0, 2.0))
    eye(arrive - 2, "happy")
    to(arrive + D(8), D(11), yaw=0.0)                     # a slow turn, or the cup whips round with her
    to(arrive + D(10), D(10), loc=SEAT, legs=SEATED, torso=(3.0, -3.0, 0.0), head=(8.0, -22.0, 3.0), R=KR,
       **cup_pose(CUP_SEATED))
    eye(v06.first, "open")
    brow(v06.first, "smile")
    to(v06.first + 1, D(3), gaze=G_CLAWD)
    to(P2("v06") + D(3), D(5), head=(5.0, -24.0, 5.0))
    to(v06.last, D(5), head=(7.0, -23.0, 4.0))

    # 10: pleased nod on "Отлично", and the cup is on its way up for a sip as the news lands
    s10, s11, s12 = S(10), S(11), S(12)
    eye(s10.first, "open")
    to(s10.first + D(6), D(4), head=(10.0, -23.0, 3.0))
    to(s10.first + D(11), D(4), head=(8.0, -22.0, 3.0))
    to(s10.last, D(10), smile=0.35)
    to(s10.last, D(12), **cup_pose(cup_near, MOUTH_PSI, MOUTH_TILT * 0.5, MOUTH_POLE), torso=(5.0, -2.0, 0.0), head=H_FREEZE,
       gaze=(-0.02, -0.004))

    # 11-12: the cup stops at her mouth and she stops with it. In the long pause only her eyes live: one blink, then
    # they creep to Clawd. Only the mouth moves on "Меня уволили?"
    v08 = V("v08")
    stop = s11.first + 4
    to(stop, 4, **cup_pose(mouth, MOUTH_PSI, MOUTH_TILT, MOUTH_POLE))
    brow(stop + 1, "shocked")
    to(stop + 2, 2, pupil=0.55)
    to(stop + D(3), D(3), smile=0.0)
    to(v08.first - 1, D(8), gaze=(-0.026, -0.006))
    to(v08.first + D(2), D(3), sad=0.3)

    # 15 (off camera): still in shock. The cup goes down while he talks and she turns to him
    s15 = S(15)
    to(s15.first + D(8), D(8), head=H_CLAWD, gaze=G_CLAWD, sad=0.0)
    cup_down = s15.first + D(14)
    to(cup_down, D(14), **cup_pose(desk_base(REACH_LOC)), torso=REACH_TORSO, loc=REACH_LOC, R=slid(KR, REACH_LOC[0]))
    to(cup_down + D(10), D(9), L=KL, grip=0.0, torso=T_REST, loc=SEAT, R=KR)

    # 18: the news has landed. Shock and total incomprehension: brows high, eyes as wide as they go, mouth hanging
    # slightly open, a small jerk back on the cut, then frozen for the whole shot. No smile
    s18, s19 = S(18), S(19)
    brow(s18.first, "shocked")
    cut(s18.first, wide=1.0, pupil=0.5, lid=0.0, smile=0.0, smirk=0.0, sad=0.0)
    to(s18.first + 2, 2, head=(6.0, -24.0, -1.5), torso=(2.5, -1.0, 0.0))
    to(s18.first + 3, 3, gape=0.35)
    to(s18.first + D(7), D(4), head=(8.0, -23.0, 1.0), torso=T_REST)
    to(s18.first + D(12), D(6), gape=0.2)

    # 19: she looks at him while he lists, sinking a little with each item; the shock slowly turns into dread.
    # (turned past Clawd on purpose: this camera is at her right shoulder, so her face reads three-quarter)
    v13, v15 = V("v13"), V("v15")
    cut(s19.first, head=(9.0, -42.0, 0.0), torso=(4.0, -10.0, 0.0), gaze=(0.010, -0.008))
    to(s19.first + D(10), D(6), gape=0.0)
    to((s19.first + v13.last) // 2, D(16), head=(10.0, -42.0, -1.5))
    to(v13.last - D(4), v13.last - s19.first - 24, wide=0.35, pupil=0.75)
    brow(v13.last - D(6), "panic")
    to(v15.first + D(4), D(5), sad=0.45, lid=0.04)
    to(v15.first + D(10), D(8), head=(11.0, -42.0, -3.0))
    to(v15.last - D(6), D(4), lid=0.2)
    to(v15.last, D(8), sad=0.7)

    # 20: "Я же сказала отвечать коротко." Dismayed and reproachful: she leans in on "сказала", the lids come down on
    # him, and a small shake of the head on "коротко"
    s20, v16 = S(20), V("v16")
    p = P2("v16")
    brow(s20.first, "panic")
    cut(s20.first, head=(10.0, -26.0, -3.0), torso=(5.0, -7.0, 0.0), gaze=G_CLAWD, wide=0.12, lid=0.10, sad=0.5, pupil=1.0)
    to(v16.first + D(8), D(6), head=(12.0, -27.0, -4.0), torso=(7.0, -8.0, 0.0))
    to(p - 2, D(8), lid=0.24, wide=0.0, sad=0.6)
    to(p + D(3), 4, head=(12.0, -30.0, -4.0))
    to(p + D(6), 4, head=(12.0, -23.0, -4.0))
    to(p + D(9), 4, head=(11.0, -26.0, -3.0))

    # 21: she sinks while he answers; by the cut she is staring at nothing
    s21 = S(21)
    sunk = s21.first + round((s21.last - s21.first) * 0.5)
    to(sunk, sunk - s21.first, head=(13.0, -25.0, -2.0), lid=0.42, sad=0.5)
    brow(s21.last - D(6), "neutral")
    to(s21.last - 1, D(8), head=(8.0, -5.0, 0.0), torso=(5.0, 0.0, 0.0), gaze=G_AHEAD, sad=0.2)

    # 22: the stare, sinking a hair, "Ну.", then a sad smile for "Зато не уволили."
    s22, v18 = S(22), V("v18")
    p = P2("v18")
    to(v18.first - 1, v18.first - 1 - s22.first, head=(9.5, -5.0, 0.0))
    to(v18.first + D(3), D(3), head=(10.5, -5.0, 0.0))
    to(v18.first + D(7), D(3), head=(8.0, -5.0, 0.0))
    brow(p - 2, "smile")
    to(p + D(2), D(3), gaze=(-0.02, -0.004))
    to(p + D(5), D(7), sad=0.0, smile=0.42, lid=0.24)
    to(p + D(8), D(6), head=(7.0, -12.0, 2.0))

    # 23: the sigh on the cut, pulls the laptop in on "Ладно", hands on the keys. "С чего начнём?"
    s23, s24, v19, v20 = S(23), S(24), V("v19"), V("v20")
    brow(s23.first, "sleepy")
    eye(s23.first + D(3), "closed")
    to(s23.first + D(3), D(3), smile=0.0)
    to(s23.first + D(5), D(5), torso=(-1.0, 0.0, 0.0), head=(2.0, -6.0, 0.0), loc=(0.0, 0.6, SZ + 0.012), gape=0.25)
    to(s23.first + D(8), D(6), sad=0.35)
    to(v19.first + 3, D(5), gape=0.0)
    to(v19.first + D(6), D(8), torso=(11.0, 0.0, 0.0), head=(16.0, -2.0, 0.0), loc=(0.0, 0.6, SZ - 0.012))
    eye(v19.first + 6, "open")
    to(v19.first + 6 + D(3), D(3), gaze=G_LAPTOP)
    grab = v19.first + D(13)
    to(grab, D(7), torso=(14.0, 0.0, 0.0), L=LAPTOP_L, R=LAPTOP_R, loc=SEAT, head=(14.0, 0.0, 0.0))
    to(grab, D(4), lid=0.42)
    pulled = grab + D(7)
    to(pulled, D(7), L=LAPTOP_L2, R=LAPTOP_R2, torso=(7.0, 0.0, 0.0))
    to(max(pulled + D(8), P2("v19") + D(4)), D(8), L=KL, R=KR, torso=T_REST, head=H_LAPTOP)
    s.laptop = (grab, pulled, s24.first)

    # 24 (off camera, he lists for a long time): two unwilling taps, on "Я уже" the hands lift and stay. Her eyes go to him
    # and her head comes round slowly through the list, so she is set for the freeze on the cut to 25
    runs = beats.runs("v20")
    p = v20.first + next((b[0] for a, b in zip(runs, runs[1:]) if b[0] - a[1] >= 4), P2("v20") - v20.first)
    to(s24.first + D(5), D(3), L=KL, R=up(KR, 0.016))
    to(s24.first + D(10), D(3), L=up(KL, 0.016), R=KR)
    to(p + D(3), D(5), L=up(KL, 0.04), R=up(KR, 0.04))
    brow(p + D(4), "hmm")
    to(p + D(12), D(8), gaze=G_CLAWD, lid=0.2)
    to(s24.last, s24.last - p - D(12), head=(10.0, -9.0, 0.0), sad=0.1)

    # 25: hands frozen, the eyes travel to the screen across the whole shot
    s25, s26, s27 = S(25), S(26), S(27)
    to(s25.last - 1, s25.last - 1 - s25.first, gaze=(0.0, -0.008), lid=0.08, sad=0.0)
    to(s25.last, s25.last - s25.first, head=(11.0, -2.0, 0.0))

    # 26: the gold grows on her face and she stares, spellbound, the eyes opening all the way through the shot.
    # Chin up and back straight, so her face clears the lid
    brow(s26.first + D(6), "delighted")
    to(s26.first + D(10), D(10), head=(8.0, -1.0, 0.0), torso=(3.0, 0.0, 0.0), lid=0.0)
    to(s26.first + D(12), D(12), wide=0.6, pupil=0.85, gape=0.22)
    to(s26.last, s26.last - s26.first - D(12), wide=0.85)

    # 27, «Красиво»: stars, brows, round mouth and fists all land on the line's first frame, with a tiny pop,
    # and hold until «А корпоратив?», the fists still squeezing a little
    v21, v27 = V("v21"), V("v27")
    second = v27.first
    star = v21.first
    to(star - 2, 3, head=(10.0, -1.0, 0.0), torso=(5.0, 0.0, 0.0))
    to(star, 4, L=FIST_L, R=FIST_R)
    eye(star, "stars")
    brow(star, "awe")
    cut(star, wide=0.0, huge=1.0, round=1.0, gape=0.3, lid=0.0, pupil=1.0)
    to(star + 1, 3, head=(4.0, -1.0, 0.0), torso=(1.0, 0.0, 0.0), loc=(0.0, 0.6, SZ + 0.014))
    settled = star + D(7)
    to(settled, settled - star - 1, head=(7.0, -1.0, 0.0), torso=(3.0, 0.0, 0.0), loc=SEAT)
    to(second - 3, second - 3 - settled, head=(6.0, -1.0, 1.2))
    squeeze = (settled + second) // 2
    to(squeeze, squeeze - star, L=up(FIST_L, 0.008), R=up(FIST_R, 0.008))
    to(second - 2, second - 2 - squeeze, L=FIST_L, R=FIST_R)

    # 27, «А корпоратив?»: normal eyes on the blink, fists come down, she turns to Clawd with hope
    eye(second, "open")
    brow(second, "smile")
    cut(second, huge=0.0, round=0.0, gape=0.0, wide=0.25, pupil=1.0, gaze=G_CLAWD)
    to(second + D(4), D(4), wide=0.0, smile=0.4)
    to(second + D(5), D(6), head=(9.0, -24.0, 3.0), torso=(4.0, -5.0, 0.0))
    to(second + D(6), D(6), L=up(KL, 0.04), R=up(KR, 0.04))
    to(v27.last - 1, D(5), head=(8.0, -24.0, 4.0))

    # 28 (off camera): «Проведу я.» Relief: the smile comes, and her hand is already going to the cup
    s28, s29, s30, s31, v23, v24 = S(28), S(29), S(30), S(31), V("v23"), V("v24")
    brow(s28.first + D(3), "delighted")
    to(s28.first + D(7), D(6), head=(5.0, -22.0, 3.0), gaze=G_CLAWD, R=KR)

    # 29: smiling, she takes the cup right at the start. She rises on «Тогда на сегодня всё», makes the short walk to her
    # mark on «Завтра снова», and is turned back to Clawd for «меня подменишь?»
    took = s29.first + 6
    p = P2("v23")
    question = p + round((beats.voiced_end("v23") - p) * 4 / 9)           # 4 of the second sentence's 9 syllables in
    to(s29.first, D(5), smile=0.85)
    to(took - D(2), D(5), gaze=(0.018, -0.016))
    to(took, D(10), **cup_pose(desk_base(REACH_LOC)), torso=REACH_TORSO, loc=REACH_LOC, R=slid(KR, REACH_LOC[0]),
       head=(10.0, -14.0, 0.0))
    brow(v23.first, "smile")
    to(took + D(3), D(3), gaze=G_CLAWD)
    stood = p - 8
    to(stood, stood - took - 2, **cup_pose(CUP_CHEST, LEFT_PSI), loc=(-0.48, 0.66, Z), legs=STAND, torso=(2.0, 0.0, 0.0), R=down(-1),
       head=(4.0, -16.0, 2.0))
    to(stood + D(2), D(12), yaw=-75.0)
    at_mark = question + 3
    s.walk(stood + 1, at_mark, (-0.48, 0.66), HER_MARK, via=(-0.86, 0.66), cup=True, psi=LEFT_PSI, period=16, swing=20.0)
    to(p + 2, D(5), head=(3.0, 14.0, 0.0))
    to(at_mark + D(3), D(3), loc=(*HER_MARK, Z), legs=STAND, **cup_pose(CUP_CHEST, LEFT_PSI))
    clawd = bpy.data.objects["STU_Claude_Dock_Anchor"].matrix_world.translation
    facing = math.degrees(math.atan2(clawd.x - HER_MARK[0], HER_MARK[1] - clawd.y))    # the way to him from her mark
    to(at_mark + D(6), D(11), yaw=facing - 12.0)
    to(question + D(7), D(7), head=(4.0, 12.0, 3.0), gaze=(0.0, -0.006))
    to(v23.last - 1, D(5), head=(2.0, 12.0, 5.0))                         # the question lands, a small tilt, and she waits

    # 30 (off camera): «Конечно!» She waits at her mark, one pleased little nod
    to(v24.first + D(5), D(4), head=(6.0, 12.0, 4.0))
    eye(v24.first + D(3), "happy")
    to(v24.last + 1, D(4), head=(3.0, 12.0, 4.0))

    # 31: she turns and leaves calmly with the cup. The room holds after her
    eye(s31.first, "open")
    to(s31.first + D(13), D(13), yaw=-75.0, head=(2.0, 18.0, 0.0))        # a slow turn, the mug is at arm's length
    out = s31.first + round((s31.last - s31.first) * 0.78)
    s.walk(s31.first + D(8), out, HER_MARK, (-1.95, 0.62), cup=True, psi=LEFT_PSI, period=16, swing=22.0)
    cut(out + 2, loc=PARK, legs=STAND)

    # what the props and the blinks need to know
    s.cup = dict(grab=day_took + 1, down=cup_down + 1, regrab=took + 1, gone=out + 2)
    s.still = [(s2.first, stare_end), (stop + 1, s12.last), s18, s25]
    s.no_blink = [s2, (s11.first, s12.last), s18, (s22.first, v18.first - 3), (s25.first, second + 3)]
    s.blinks = [v08.first - 14, v15.last - D(6), v18.first - 2, second]
    s.stars = (star, second)


# ---------------------------------------------------------------- solving the body
def turn(pitch, yaw, roll=0.0):
    return (Matrix.Rotation(math.radians(yaw), 3, "Z") @ Matrix.Rotation(math.radians(pitch), 3, "X")
            @ Matrix.Rotation(math.radians(roll), 3, "Y"))


def leg_dirs(a, bend):
    ra, rb = math.radians(a), math.radians(a - bend)
    return (0, -math.sin(ra), -math.cos(ra)), (0, -math.sin(rb), -math.cos(rb))


def solve(bones, torso, head, hands, legs, hold=None):
    """Pose matrices (armature space) and matrix_basis per bone. hold=(0..1, thumb direction) turns the left hand into
    the wrap round the mug: fingers along its aim, thumb up the mug, palm on the wall."""
    pose = {}

    def place(name, direction=None, rot=None):
        b = bones[name]
        rest = b.matrix_local
        head_pt = rest.translation if b.parent is None else \
            (pose[b.parent.name] @ b.parent.matrix_local.inverted() @ rest).translation
        R = rest.to_3x3()
        if rot is not None:
            R = rot @ R
        elif direction is not None:
            R = R.col[1].normalized().rotation_difference(Vector(direction).normalized()).to_matrix() @ R
        M = R.to_4x4()
        M.translation = head_pt
        pose[name] = M
        return M

    def tail(name):
        return pose[name] @ Vector((0, bones[name].length, 0))

    place("root")
    place("hips")
    place("torso", rot=turn(*torso))
    place("head", rot=turn(*head))
    for s in (".L", ".R"):
        th, sh = leg_dirs(*legs[s])
        place("thigh" + s, th)
        place("shin" + s, sh)
        place("foot" + s)
        h = hands[s]
        wrist, tip, pole = Vector(h[:3]), Vector(h[3:6]), Vector(h[6:9])
        s_head = place("upper_arm" + s).translation.copy()
        l1, l2 = bones["upper_arm" + s].length, bones["forearm" + s].length
        d = wrist - s_head
        dist = min(d.length, l1 + l2 - 1e-4)
        u = d.normalized()
        a = (l1 * l1 - l2 * l2 + dist * dist) / (2 * dist)
        off = math.sqrt(max(l1 * l1 - a * a, 0.0))
        v = (pole - pole.dot(u) * u).normalized()
        elbow = s_head + u * a + v * off
        place("upper_arm" + s, elbow - s_head)
        place("forearm" + s, wrist - tail("upper_arm" + s))
        aim = tip - tail("forearm" + s)
        if s == ".L" and hold and hold[0] > 0.0:
            rest = bones["hand.L"].matrix_local.to_3x3()
            free = rest.col[1].normalized().rotation_difference(aim.normalized()).to_matrix() @ rest
            y = aim.normalized()
            x = Vector(hold[1])
            x = (x - x.dot(y) * y).normalized()
            wrap = Matrix((x, y, x.cross(y))).transposed()
            R = free.to_quaternion().slerp(wrap.to_quaternion(), min(1.0, hold[0])).to_matrix()
            place("hand.L", rot=R @ rest.inverted())
        else:
            place("hand" + s, aim)
    basis = {}
    for name, M in pose.items():
        b = bones[name]
        if b.parent is None:
            basis[name] = b.matrix_local.inverted() @ M
        else:
            local = b.parent.matrix_local.inverted() @ b.matrix_local
            basis[name] = local.inverted() @ pose[b.parent.name].inverted() @ M
    return pose, basis


def idle(f, still):
    """Slow breathing and a little head drift; nothing in the frozen beats."""
    k = 1.0
    for a, b in still:
        if a <= f <= b:
            return (0.0, 0.0, 0.0), 0.0
        k = min(k, max(0.0, min(1.0, abs(f - a) / 6.0)), max(0.0, min(1.0, abs(f - b) / 6.0)))
    head = (0.55 * math.sin(f / 23.0), 0.7 * math.sin(f / 37.0 + 1.1), 0.5 * math.sin(f / 31.0 + 2.3))
    return tuple(k * v for v in head), k * 0.4 * math.sin(2 * math.pi * f / 96.0)


# ---------------------------------------------------------------- keys
def action_for(idb, name):
    ad = idb.animation_data_create()
    if ad.action is None:
        ad.action = bpy.data.actions.new(name)
    return ad.action


def write(action, idb, path, index, pairs, mode="BEZIER"):
    fc = action.fcurve_ensure_for_datablock(idb, path, index=index)
    fc.keyframe_points.add(len(pairs))
    fc.keyframe_points.foreach_set("co", [v for p in pairs for v in p])
    if mode != "BEZIER":
        for kp in fc.keyframe_points:
            kp.interpolation = mode
    fc.update()
    return fc


def key_body(rig, s, frame_end):
    bones = rig.data.bones
    t = s.t
    names = ("torso", "head", "L", "R", "legL", "legR", "grip", "thumb")
    frames = set(range(1, frame_end + 1, 8)) | {frame_end}
    for n in names:
        frames.update(t[n].frames())
    frames.update(range(s.cup["grab"], s.cup["down"] + 1))     # every frame while she holds the cup, so it can't wobble
    frames.update(range(s.cup["regrab"], s.cup["gone"] + 1))   # between keys
    samples = {}
    prev = {}
    for f in sorted(frames):
        drift, breath = idle(f, s.still)
        torso = list(t["torso"].at(f))
        torso[0] += breath
        head = [a + b for a, b in zip(t["head"].at(f), drift)]
        hands = {".L": t["L"].at(f), ".R": t["R"].at(f)}
        legs = {".L": t["legL"].at(f), ".R": t["legR"].at(f)}
        _, basis = solve(bones, torso, head, hands, legs, (t["grip"].at(f)[0], t["thumb"].at(f)))
        for name, M in basis.items():
            q = M.to_quaternion()
            if name in prev and prev[name].dot(q) < 0:
                q.negate()
            prev[name] = q
            samples.setdefault(name, []).append((f, tuple(q)))
    action = action_for(rig, ACTION)
    for name, keys in samples.items():
        rig.pose.bones[name].rotation_mode = "QUATERNION"
        path = f'pose.bones["{name}"].rotation_quaternion'
        for i in range(4):
            write(action, rig, path, i, [(f, q[i]) for f, q in keys])
    rig.rotation_mode = "XYZ"
    for i in range(3):
        write(action, rig, "location", i, [(f, v[i]) for f, v in t["loc"].keys])
    write(action, rig, "rotation_euler", 2, [(f, math.radians(v[0])) for f, v in t["yaw"].keys])
    return action


# ---------------------------------------------------------------- face meshes
def material(name):
    return bpy.data.materials.get("STU_Designer_" + name) or bpy.data.materials[name]


def face_object(ctx, rig, template, name, verts, faces, mats, face_mats):
    me = bpy.data.meshes.new(ep3.PREFIX + "Designer_Face_" + name)
    me.from_pydata(verts, [], faces)
    for m in mats:
        me.materials.append(material(m))
    for poly, mi in zip(me.polygons, face_mats):
        poly.material_index = mi
    me.update()
    ob = bpy.data.objects.new(me.name, me)
    ctx.collection("Girl").objects.link(ob)
    ob.parent = rig
    ob.parent_type = "BONE"
    ob.parent_bone = template.parent_bone
    ob.matrix_parent_inverse = template.matrix_parent_inverse.copy()
    ob.matrix_basis = template.matrix_basis.copy()
    return ob


def rects(boxes, y):
    verts, faces = [], []
    for x0, x1, z0, z1 in boxes:
        b = len(verts)
        verts += [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)]
        faces.append((b, b + 1, b + 2, b + 3))
    return verts, faces


def mirrored(boxes):
    return boxes + [(-x1, -x0, z0, z1) for x0, x1, z0, z1 in boxes]


def shape(ob, name, coords, slider_min=0.0):
    if ob.data.shape_keys is None:
        ob.shape_key_add(name="Basis", from_mix=False)
    k = ob.shape_key_add(name=name, from_mix=False)
    k.slider_min = slider_min
    k.data.foreach_set("co", [v for c in coords for v in c])
    return k


def build_eyes(ctx, rig, tmpl):
    X0, X1, Z0, Z1 = 0.04, 0.16, 0.16, 0.24
    v, f = rects(mirrored([(X0, X1, Z0, Z1)]), -0.2442)
    whites = face_object(ctx, rig, tmpl, "Eyes_whites", v, f, ["DSG_eye_hi"], [0] * len(f))
    shape(whites, "wide", [(math.copysign(0.10, x) + (x - math.copysign(0.10, x)) * 1.06, y, 0.20 + (z - 0.20) * 1.35)
                           for x, y, z in v])
    shape(whites, "huge", [(math.copysign(STAR_EYE[0] + math.copysign(0.066, abs(x) - 0.10), x), y,
                            STAR_EYE[1] + math.copysign(0.058, z - 0.20)) for x, y, z in v])

    centres = [(0.10, 0.20), (-0.10, 0.20)]
    boxes = [(cx - 0.02, cx + 0.02, cz - 0.028, cz + 0.028) for cx, cz in centres]
    v, f = rects(boxes, -0.2447)
    pupils = face_object(ctx, rig, tmpl, "Eyes_pupils", v, f, ["DSG_pupil"], [0] * len(f))
    shape(pupils, "look_x", [(x + LOOK_X, y, z) for x, y, z in v], -1.0)
    shape(pupils, "look_z", [(x, y, z + LOOK_Z) for x, y, z in v], -1.0)
    small = []
    for i, (x, y, z) in enumerate(v):
        cx, cz = centres[i // 4]
        small.append((cx + (x - cx) * PUPIL_SMALL, y, cz + (z - cz) * PUPIL_SMALL))
    shape(pupils, "small", small)

    top = Z1 + 0.001
    v, f = rects(mirrored([(X0 - 0.001, X1 + 0.001, top, top)]), -0.2452)
    lids = face_object(ctx, rig, tmpl, "Eyes_lids", v, f, ["DSG_skin_shadow"], [0] * len(f))
    shape(lids, "close", [(x, y, Z0 - 0.001 if i % 4 < 2 else z) for i, (x, y, z) in enumerate(v)])

    arc = mirrored([(0.064, 0.136, 0.176, 0.192), (0.04, 0.07, 0.188, 0.204), (0.13, 0.16, 0.188, 0.204)])
    v, f = rects(arc, -0.2447)
    closed = face_object(ctx, rig, tmpl, "Eyes_closed", v, f, ["DSG_pupil"], [0] * len(f))
    return whites, pupils, lids, closed


def build_mouth(ctx, rig, tmpl):
    n = 17
    us = [-1 + 2 * i / (n - 1) for i in range(n)]
    Y_LIP, Y_DARK, Z0 = -0.2448, -0.2452, 0.084

    def state(gap=0.0, smile=0.0, smirk=0.0, sad=0.0, narrow=1.0):
        out = []
        for u in us:
            x = u * 0.052 * narrow * (1 + 0.16 * smile + 0.05 * smirk - 0.10 * (gap > 0))
            taper = math.sqrt(max(0.0, 1 - u ** 4))
            c = Z0 + smile * (0.026 * u * u - 0.007) + smirk * (0.03 * max(u, 0.0) ** 2 - 0.004) \
                + sad * (0.006 - 0.020 * u * u)
            g = gap * taper
            lip = 0.0058 * (0.35 + 0.65 * taper)
            out += [(x, Y_LIP, c + g + lip), (x, Y_LIP, c - g - lip), (x, Y_DARK, c + g), (x, Y_DARK, c - g)]
        return out

    verts = state()
    faces, fmats = [], []
    for i in range(n - 1):
        a, b = 4 * i, 4 * (i + 1)
        faces.append((a + 1, b + 1, b, a))
        fmats.append(0)
        faces.append((a + 3, b + 3, b + 2, a + 2))
        fmats.append(1)
    ob = face_object(ctx, rig, tmpl, "Mouth", verts, faces, ["DSG_mouth", "DSG_mouth_dark"], fmats)
    shape(ob, "open", state(gap=0.017))
    shape(ob, "smile", state(smile=1.0))
    shape(ob, "smirk", state(smirk=1.0))
    shape(ob, "sad", state(sad=1.0))
    shape(ob, "round", state(gap=0.010, narrow=0.58))
    return ob


def star_material():
    m = bpy.data.materials.new(ep3.PREFIX + "Designer_Star")
    nt = m.node_tree
    nt.nodes.clear()
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = STAR_COLOR
    emit.inputs["Strength"].default_value = 1.0
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(emit.outputs[0], out.inputs[0])
    return m


def build_stars(ctx, rig, tmpl):
    """A dark iris with a bright four-pointed star in each eye."""
    star_material()
    verts, faces, fmats, small = [], [], [], []
    for sx in (1, -1):
        cx, cz = sx * STAR_EYE[0], STAR_EYE[1]
        b = len(verts)
        n = 28
        for i in range(n):                     # the iris: a soft square, like the rest of her face
            a = 2 * math.pi * i / n
            ca, sa = math.cos(a), math.sin(a)
            verts.append((cx + 0.052 * math.copysign(abs(ca) ** 0.6, ca), -0.2448, cz + 0.050 * math.copysign(abs(sa) ** 0.6, sa)))
            small.append(verts[-1])
        faces.append(tuple(range(b, b + n)))
        fmats.append(0)
        c = len(verts)
        verts.append((cx, -0.2450, cz))
        small.append(verts[-1])
        m = 40
        for i in range(m):                     # the star: an astroid, four long points with curved sides
            a = 2 * math.pi * i / m
            ca, sa = math.cos(a), math.sin(a)
            dx, dz = 0.048 * math.copysign(abs(ca) ** 2.7, ca), 0.050 * math.copysign(abs(sa) ** 2.7, sa)
            verts.append((cx + dx, -0.2450, cz + dz))
            small.append((cx + dx * 0.6, -0.2450, cz + dz * 0.6))
        for i in range(m):
            faces.append((c, c + 1 + i, c + 1 + (i + 1) % m))
            fmats.append(1)
    ob = face_object(ctx, rig, tmpl, "Eyes_stars", verts, faces, ["DSG_pupil", ep3.PREFIX + "Designer_Star"], fmats)
    shape(ob, "small", small, -0.3)
    return ob


def build_awe_brows(ctx, rig):
    """Brows angled in, for the star eyes. Named like the Studio sets, so they swap the same way."""
    tmpl = bpy.data.objects["STU_Designer_Face_Brows_neutral"]
    y = -0.2444
    verts = [(0.055, y, 0.302), (0.160, y, 0.338), (0.160, y, 0.352), (0.055, y, 0.324),
             (-0.160, y, 0.338), (-0.055, y, 0.302), (-0.055, y, 0.324), (-0.160, y, 0.352)]
    return face_object(ctx, rig, tmpl, "Brows_awe", verts, [(0, 1, 2, 3), (4, 5, 6, 7)], ["DSG_hair_hi"], [0, 0])


def build_finger(ctx, rig, s):
    """Her hands are mitts, so the one finger of the key press slides out of the right hand and back. Its tip is
    solved to land on the key on the press frame."""
    f = s.press
    bones = rig.data.bones
    _, breath = idle(f, s.still)
    torso = list(s.t["torso"].at(f))
    torso[0] += breath
    hands = {".L": s.t["L"].at(f), ".R": s.t["R"].at(f)}
    legs = {".L": s.t["legL"].at(f), ".R": s.t["legR"].at(f)}
    pose, _ = solve(bones, torso, s.t["head"].at(f), hands, legs)
    tail = pose["hand.R"] @ Matrix.Translation((0, bones["hand.R"].length, 0))
    tip = tail.inverted() @ (Vector(KEY_SPOT) - Vector(s.t["loc"].at(f)))

    root = Vector((tip.x * 0.4 - 0.012, -0.012, tip.z * 0.4))
    rings = [(0.0, 0.017, 0.015), (0.72, 0.014, 0.012), (0.90, 0.008, 0.007)]
    out = []
    for u, hx, hz in rings:
        c = root.lerp(tip, u)
        out += [(c.x - hx, c.y, c.z - hz), (c.x + hx, c.y, c.z - hz), (c.x + hx, c.y, c.z + hz), (c.x - hx, c.y, c.z + hz)]
    out.append(tuple(tip))
    faces = [(0, 3, 2, 1)]
    for r in range(2):
        for i in range(4):
            a, b = r * 4 + i, r * 4 + (i + 1) % 4
            faces.append((a, b, b + 4, a + 4))
    faces += [(8 + i, 8 + (i + 1) % 4, 12) for i in range(4)]
    inside = [(x, -0.04 + (y + 0.012) * 0.25, z) for x, y, z in out]         # folded away inside the mitt

    me = bpy.data.meshes.new(ep3.PREFIX + "Designer_Finger")
    me.from_pydata(inside, [], faces)
    me.materials.append(material("DSG_skin"))
    me.update()
    ob = bpy.data.objects.new(me.name, me)
    ctx.collection("Girl").objects.link(ob)
    ob.parent = rig
    ob.parent_type = "BONE"
    ob.parent_bone = "hand.R"
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_basis = Matrix.Identity(4)
    shape(ob, "out", out)
    keys = s.t["finger"].keys
    write(action_for(me.shape_keys, ep3.PREFIX + "Girl_Finger"), me.shape_keys, 'key_blocks["out"].value', 0,
          [(k, v[0]) for k, v in keys])
    used = [k for k, v in keys if v[0] > 0.0]
    key_visibility(ob, [(1, False), (used[0] - 8, True), (used[-1] + 8, False)])
    return ob


def build_blush(ctx, rig, tmpl):
    """Three short pink strokes on each cheek, just under the glasses."""
    y, verts, faces = -0.2443, [], []
    for sx in (1, -1):
        for i in range(3):
            x0 = (0.150 + 0.024 * i) if sx > 0 else (-0.198 + 0.024 * i)
            b = len(verts)
            verts += [(x0, y, 0.068), (x0 + 0.012, y, 0.068), (x0 + 0.024, y, 0.094), (x0 + 0.012, y, 0.094)]
            faces.append((b, b + 1, b + 2, b + 3))
    return face_object(ctx, rig, tmpl, "Blush", verts, faces, ["DSG_blush"], [0] * len(faces))


# ---------------------------------------------------------------- lip sync
_ENVELOPES = {}


def envelope(path):
    if str(path) not in _ENVELOPES:
        _ENVELOPES[str(path)] = read_envelope(path)
    return _ENVELOPES[str(path)]


def read_envelope(path):
    with wave.open(str(path)) as w:
        n, r, ch, width = w.getnframes(), w.getframerate(), w.getnchannels(), w.getsampwidth()
        x = np.frombuffer(w.readframes(n), {2: "<i2", 4: "<i4"}[width]).astype(np.float32) / 2 ** (8 * width - 1)
    if ch > 1:
        x = x.reshape(-1, ch).mean(1)
    hop = r / 24
    count = int(len(x) / hop)
    return np.array([np.sqrt((x[int(i * hop):int((i + 1) * hop)] ** 2).mean()) for i in range(count)])


def lip_sync(ctx):
    """{frame: 0..1}, on twos, so the mouth reads as flaps and not as a tremble."""
    out = {}
    for line in ctx.lines("girl"):
        e = envelope(ctx.audio_path(line))
        peak = max(float(e.max()), 1e-4)
        start = line["first_frame"]
        out[start - 1] = 0.0                         # shut until the line starts, or the keys ramp across the silence
        for i in range(0, len(e), 2):
            level = float(e[i:i + 2].max()) / peak
            v = 0.0 if level < 0.12 else min(1.0, (level / 0.75) ** 0.7)
            if v > 0 and (i // 2) % 3 == 2:          # a short close inside long vowels keeps it talking
                v *= 0.55
            out[start + i] = v
        out[start + len(e) + 1] = 0.0
    return out


# ---------------------------------------------------------------- face keys
def key_visibility(ob, changes):
    action = action_for(ob, ob.name)
    pairs = [(f, 0.0 if on else 1.0) for f, on in changes]
    write(action, ob, "hide_render", 0, pairs, "CONSTANT")
    write(action, ob, "hide_viewport", 0, pairs, "CONSTANT")
    ob.hide_render = ob.hide_viewport = not changes[0][1]


def hold_at(keys, f):
    v = keys[0][1]
    for k, val in keys:
        if k > f:
            break
        v = val
    return v


def key_face(ctx, rig, s, parts):
    end = ctx.frame_end
    # eyes: open / ^_^ / closed, with blinks
    rng = random.Random(3)
    blinks = set()
    for b in s.blinks:
        blinks.update((b, b + 1, b + 2))
    f = 20
    while f < end:
        if not any(a - 3 <= f <= b for a, b in s.no_blink):
            blinks.update((f, f + 1, f + 2))
        f += rng.randint(48, 90)
    shows = {"whites": ("open", "stars"), "pupils": ("open",), "lids": ("open", "stars"), "closed": ("closed",),
             "happy": ("happy",), "stars": ("stars",)}
    s.eyes.sort(key=lambda k: k[0])
    modes = []
    for f in range(1, end + 1):
        mode = hold_at(s.eyes, f)
        modes.append((f, "closed" if mode == "open" and f in blinks else mode))
    for name, on_in in shows.items():
        changes, last = [], None
        for f, mode in modes:
            on = mode in on_in
            if on != last:
                changes.append((f, on))
                last = on
        key_visibility(parts[name], changes)

    # the stars pop in, overshoot, then twinkle; the blush lives exactly as long as they do
    first, gone = s.stars
    key_visibility(parts["blush"], [(1, False), (first, True), (gone, False)])
    pop = [(first, 1.0), (first + 2, -0.22), (first + 4, 0.0)]
    pop += [(f, 0.14 if (f - first) % 6 == 0 else 0.0) for f in range(first + 6, gone, 3)]
    star_key = parts["stars"].data.shape_keys
    write(action_for(star_key, ep3.PREFIX + "Girl_Stars"), star_key, 'key_blocks["small"].value', 0, pop)

    # pupils and lid
    pup_key = parts["pupils"].data.shape_keys
    act = action_for(pup_key, ep3.PREFIX + "Girl_Pupils")
    write(act, pup_key, 'key_blocks["look_x"].value', 0, [(f, v[0] / LOOK_X) for f, v in s.t["gaze"].keys])
    write(act, pup_key, 'key_blocks["look_z"].value', 0, [(f, v[1] / LOOK_Z) for f, v in s.t["gaze"].keys])
    write(act, pup_key, 'key_blocks["small"].value', 0,
          [(f, (1 - v[0]) / (1 - PUPIL_SMALL)) for f, v in s.t["pupil"].keys])
    white_key = parts["whites"].data.shape_keys
    act = action_for(white_key, ep3.PREFIX + "Girl_Whites")
    for name in ("wide", "huge"):
        write(act, white_key, f'key_blocks["{name}"].value', 0, [(f, v[0]) for f, v in s.t[name].keys])
    lid_key = parts["lids"].data.shape_keys
    write(action_for(lid_key, ep3.PREFIX + "Girl_Lids"), lid_key, 'key_blocks["close"].value', 0,
          [(f, v[0]) for f, v in s.t["lid"].keys])

    # mouth
    mouth_key = parts["mouth"].data.shape_keys
    act = action_for(mouth_key, ep3.PREFIX + "Girl_Mouth")
    for name in ("smile", "smirk", "sad", "round"):
        write(act, mouth_key, f'key_blocks["{name}"].value', 0, [(f, v[0]) for f, v in s.t[name].keys])
    lips = lip_sync(ctx)
    frames = sorted(set(lips) | set(s.t["gape"].frames()) | {1, end})
    write(act, mouth_key, 'key_blocks["open"].value', 0,
          [(f, max(lips.get(f, 0.0), s.t["gape"].at(f)[0])) for f in frames], "LINEAR")

    # brows: Studio sets
    for name, ob in parts["brows"].items():
        ch, last = [], None
        for f, state in sorted(s.brows, key=lambda k: k[0]):
            on = state == name
            if on != last:
                ch.append((f, on))
                last = on
        key_visibility(ob, ch)


# ---------------------------------------------------------------- props
def key_wrap(rig, s):
    """The mitt closes round the mug: a shape key on the left hand (and what it wears) bends its end around the wall, slims
    it so the mug shows above and below, and folds the thumb down."""
    radius = CUP_RADIUS - PALM_OVERLAP
    for ob in (o for o in rig.children if o.type == "MESH" and o.parent_bone == "hand.L"):
        M = ob.matrix_parent_inverse @ ob.matrix_basis
        back = M.inverted()
        closed = []
        for v in ob.data.vertices:
            x, y, z = M @ v.co
            k = max(0.0, min(1.0, (y + 0.16) / 0.08))           # the wrist end stays as it is, so it meets the forearm
            if x > 0.06:
                x = 0.06 + (x - 0.06) * 0.2
            x *= 1.0 - 0.30 * k                                  # slimmer, so the rim and base show above and below it
            z = -PALM_HALF + (z + PALM_HALF) * (1.0 - 0.2 * k)
            if y > PALM_AT:
                a = (y - PALM_AT) / radius
                r = radius + z + PALM_HALF
                y, z = PALM_AT + r * math.sin(a), -PALM_HALF - radius + r * math.cos(a)
            closed.append(tuple(back @ Vector((x, y, z))))
        shape(ob, "wrap", closed)
        keys = ob.data.shape_keys
        write(action_for(keys, ep3.PREFIX + "Girl_Grip_" + ob.name), keys, 'key_blocks["wrap"].value', 0,
              [(f, v[0]) for f, v in s.t["grip"].keys])


def key_cup(rig, s, bones):
    """The mug is scaled up and turned to its holding angle for the whole episode, so nothing changes when she takes it."""
    cup = bpy.data.objects[ep3.CUP]
    cup.scale = (CUP_SCALE, CUP_SCALE, CUP_SCALE)
    cup.rotation_euler = (0.0, 0.0, math.radians(HOLD_PSI))
    GRAB, DOWN_AT, REGRAB = s.cup["grab"], s.cup["down"], s.cup["regrab"]

    held = cup_pose(CUP_CHEST)
    ref_hands = {".L": held["L"], ".R": KR}
    pose, _ = solve(bones, T_REST, H_LAPTOP, ref_hands, {".L": SEATED, ".R": SEATED}, (1.0, held["thumb"]))
    own = cup.parent.matrix_world @ cup.matrix_parent_inverse @ cup.matrix_basis
    in_hand = Matrix.LocRotScale(Vector(CUP_CHEST), Matrix.Rotation(math.radians(HOLD_PSI), 3, "Z"), Vector((CUP_SCALE,) * 3))
    con = cup.constraints.new("CHILD_OF")
    con.name = ep3.PREFIX + "Hold"
    con.target = rig
    con.subtarget = "hand.L"
    con.inverse_matrix = pose["hand.L"].inverted() @ in_hand @ own.inverted()

    action = action_for(cup, ep3.PREFIX + "Cup")
    write(action, cup, f'constraints["{con.name}"].influence', 0,
          [(1, 0.0), (GRAB, 1.0), (DOWN_AT, 0.0), (REGRAB, 1.0)], "CONSTANT")
    key_wrap(rig, s)


def key_laptop(s):
    """Shot 23 pulls the laptop in. It goes back on the cut to shot 24, so the cameras framed on the screen stay true."""
    start, pulled, back = s.laptop
    stand = bpy.data.objects["STU_Laptop_Stand"]
    y = stand.location.y
    action = action_for(stand, ep3.PREFIX + "Laptop_Pull")
    fc = write(action, stand, "location", 1, [(1, y), (start, y), (pulled, y + LAPTOP_PULL),
                                              (back - 1, y + LAPTOP_PULL), (back, y)])
    fc.keyframe_points[3].interpolation = "CONSTANT"
    fc.update()


# ---------------------------------------------------------------- build
def foot_floor_z(rig):
    """Rig height that puts her feet on the floor when she stands straight."""
    rz = rig.matrix_world.translation.z
    low = 1e9
    for side in (".L", ".R"):
        ob = bpy.data.objects["STU_Designer_Foot" + side]
        b = rig.data.bones[ob.parent_bone]
        M = rig.matrix_world @ b.matrix_local @ Matrix.Translation((0, b.length, 0)) @ ob.matrix_parent_inverse \
            @ ob.matrix_basis
        low = min(low, min((M @ v.co).z for v in ob.data.vertices))
    return rz - low + 0.005


def mouth_position(rig, tmpl, torso, head):
    bones = rig.data.bones
    hands = {".L": KL, ".R": KR}
    pose, _ = solve(bones, torso, head, hands, {".L": SEATED, ".R": SEATED})
    b = bones["head"]
    local = Vector((0.0, -0.2445, 0.084))
    return pose["head"] @ Matrix.Translation((0, b.length, 0)) @ tmpl.matrix_parent_inverse @ tmpl.matrix_basis @ local


def frame_left_x(ctx, y=0.62):
    """World x where the left edge of the shot 8 frame crosses her exit line. Stage runs first, so this is the real one."""
    cam = bpy.data.objects.get(ep3.camera_name(8)) or bpy.data.objects.get("STU_Cam_Wide")
    ctx.scene.frame_set(ctx.shot(8)["last_frame"])
    corners = cam.data.view_frame(scene=ctx.scene)
    left = sorted(corners, key=lambda c: c.x)[:2]
    M = cam.matrix_world.copy()
    origin = M.translation
    ray = M.to_3x3() @ ((left[0] + left[1]) / 2)
    ctx.scene.frame_set(ctx.frame_start)
    return origin.x + ray.x * (y - origin.y) / ray.y


def build(ctx):
    rig = bpy.data.objects[ep3.GIRL_RIG]
    tmpl_eye = bpy.data.objects["STU_Designer_Face_Eyes_neutral"]
    tmpl_mouth = bpy.data.objects["STU_Designer_Face_Mouth_neutral"]

    for ob in rig.children:                    # her Studio eyes and mouths are replaced; ^_^ and the brows stay
        if "_Face_Mouth_" in ob.name or ("_Face_Eyes_" in ob.name and not ob.name.endswith("_delighted")):
            ob.hide_render = ob.hide_viewport = True

    whites, pupils, lids, closed = build_eyes(ctx, rig, tmpl_eye)
    mouth_ob = build_mouth(ctx, rig, tmpl_mouth)
    stars = build_stars(ctx, rig, tmpl_eye)
    blush = build_blush(ctx, rig, tmpl_eye)
    build_awe_brows(ctx, rig)
    parts = {
        "whites": whites, "pupils": pupils, "lids": lids, "closed": closed, "mouth": mouth_ob, "stars": stars, "blush": blush,
        "happy": bpy.data.objects["STU_Designer_Face_Eyes_delighted"],
        "brows": {o.name.rsplit("_", 1)[1]: o for o in rig.children if "_Face_Brows_" in o.name},
    }

    at_mouth = mouth_position(rig, tmpl_mouth, (5.0, -2.0, 0.0), H_FREEZE) + CUP_AT_MOUTH
    script = Script(foot_floor_z(rig), tuple(at_mouth))
    script.exit_edge = frame_left_x(ctx)
    perform(script, ctx)

    key_body(rig, script, ctx.frame_end)
    key_face(ctx, rig, script, parts)
    build_finger(ctx, rig, script)
    key_cup(rig, script, rig.data.bones)
    key_laptop(script)
    return rig
