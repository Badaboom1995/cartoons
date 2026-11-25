"""EP4: her whole performance on STU_Designer_Rig, her face and lip sync, the headphones and the chair (STU_Chair).

The acting is one chronological script in perform(): to(frame, duration, channel=value) moves a channel so it arrives on
that frame, cut(frame, ...) jumps on a cut. Every frame comes from timeline.json through ctx, so a retimed sound only
needs a rebuild. Channels are solved (two-bone arms) and keyed on every frame.

The chair: the rig sits on STU_Chair and turns with it about the chair's pivot. Her "loc" channel is in the chair's own
space (where she would be with the chair straight), "chair" is the chair's turn in Blender degrees about Z.
ep4.CHAIR_TOWARDS_CLAWD_DEG says how far she turns towards Clawd (the -X side), which is a negative Z rotation here.

Face (from ep-003): eyes are white + pupil + lid meshes whose gaze, size and lid are shape keys; a blink or a squeeze is
the closed arcs. Shot 24 ends in anime crying: "cry" eyes are two flat bars (T_T) with two tear streams under them. One mouth mesh with shape keys (open, smile, smirk, sad, yell). Brows are the Studio sets plus "angry".
Lip sync follows the envelope of each of her lines, and in shot 28 the envelope of the bleep that covers her yell.
"""
import bisect
import math
import random
import sys
import wave
from collections import namedtuple

import bpy
import numpy as np
from mathutils import Matrix, Vector

import ep4
import girl_board16

SEAT = (0.0, 0.6, -0.11)                     # rig location seated at the laptop, chair straight
DESK_Z = 0.72
DESK_TOP = 0.724                             # where a hand lands: the desk top is 0.721, the desk mat 0.723
KEY_TOP = 0.733                              # top of STU_Keyboard
ACTION = ep4.PREFIX + "Girl"
ROLL_BACK = 0.14                             # turned to Clawd, the chair rolls back this much, clear of the desk edge
CLAWD_FACE_UP = 0.08                         # his face above the dock anchor (he is scaled to 0.18)
HEAD_SHARE = 0.8                             # when she looks at someone, the head turns this much and the eyes do the rest
PUPIL_PER_DEG = 0.0022                       # pupil shift (m) for each degree the eyes turn past the head
LOOK_X, LOOK_Z = 0.03, 0.016
PUPIL_SMALL = 0.5
SKEPTIC_LID = 0.58                           # shot 8: the lids come down flat over the top of the pupils, "-_-"
TEAR_COLOUR = (0.36, 0.72, 1.0, 1.0)         # linear RGBA
TEAR_FLOW_FRAMES = 5                         # the streams run down from the eyes to the chin
SOB_PERIOD, SOB_DEG = 8, 2.2                 # the shoulders heave with each sob


# ---------------------------------------------------------------- hand targets (armature space: wrist, tip, elbow pole)
def desk(x, y, z):
    """World x, y and height above the desk top, in her armature's space when she sits straight at the laptop."""
    return (x - SEAT[0], y - SEAT[1], z + DESK_Z - SEAT[2])


def hand(wrist, tip, side, pole=None):
    sx = 1 if side == "L" else -1
    return (*desk(*wrist), *desk(*tip), *(pole or (0.5 * sx, 0.3, -1.0)))


def up(h, dz):
    return (h[0], h[1], h[2] + 0.6 * dz, h[3], h[4], h[5] + dz, h[6], h[7], h[8])


def lift(h, dz):
    return (h[0], h[1], h[2] + dz, h[3], h[4], h[5] + dz, h[6], h[7], h[8])


def mirror_pole(p):
    return (-p[0], p[1], p[2])


def mirror(h):
    return (-h[0], h[1], h[2], -h[3], h[4], h[5], -h[6], h[7], h[8])


# Her shoulders are only ~17 cm above the desk top, so her elbows hang at desk height. Typing, they flare out a little
# so the forearms clear the desk edge; resting a hand on the desk, the elbow lifts out and up (pressing down).
TYPE_POLE = (1.0, 0.0, 0.0)
PRESS_POLE = (0.6, 0.0, 0.4)
KL = hand((0.09, 0.32, 0.13), (0.06, 0.19, 0.08), "L", TYPE_POLE)
KR = mirror(KL)
# shot 4: a light wave of the right hand towards the screen
WAVE_A = hand((-0.20, 0.25, 0.17), (-0.15, 0.13, 0.23), "R", (-1.0, 0.15, -0.2))
WAVE_B = hand((-0.15, 0.24, 0.17), (-0.06, 0.14, 0.20), "R", (-1.0, 0.15, -0.2))
# shot 6: the "so what?" hand, up and open
SHRUG_R = hand((-0.25, 0.33, 0.15), (-0.28, 0.20, 0.19), "R", (-1.0, 0.0, 0.0))
# shot 9: the palm laid flat on the desk, right of the keyboard (z is set by land())
PALM_R = hand((-0.27, 0.26, 0.06), (-0.255, 0.12, 0.02), "R", mirror_pole(PRESS_POLE))
# shot 13: pointing at the laptop screen
POINT_R = hand((-0.12, 0.13, 0.22), (-0.07, 0.00, 0.25), "R", (-0.8, 0.2, -0.5))
POINT_JAB = hand((-0.11, 0.10, 0.22), (-0.06, -0.03, 0.25), "R", (-0.8, 0.2, -0.5))
# turned to Clawd: forearms on the armrests, hands loose over their ends (body space, they turn with her)
LAP_L = (0.28, -0.12, 0.792, 0.27, -0.22, 0.722, 0.4, 1.0, -0.5)
LAP_R = mirror(LAP_L)
# on the way between the keys and her lap the hands pass above the desk edge, close to her body
CLEAR_L = (0.15, -0.22, 0.98, 0.13, -0.35, 0.96, 0.9, 0.3, 0.0)
# turned towards Clawd her left side comes close to the desk: the hands must be on the armrests before the chair passes
# this angle, and leave them only after it has turned back past it
ARMREST_BY_DEG = 15.0
CLEAR_R = mirror(CLEAR_L)
SLUMP_L = lift(LAP_L, 0.012)
SLUMP_R = mirror(SLUMP_L)
# shot 28: fists up, fists on the desk (z set by land()), fists at her chest for the yell
FIST_UP_L = hand((0.25, 0.44, 0.40), (0.23, 0.36, 0.52), "L", (0.9, 0.3, -0.4))
FIST_UP_R = mirror(FIST_UP_L)
FIST_DESK_L = hand((0.27, 0.28, 0.06), (0.255, 0.14, 0.02), "L", PRESS_POLE)
FIST_DESK_R = mirror(FIST_DESK_L)
FIST_CHEST_L = (0.16, -0.18, 1.00, 0.12, -0.22, 1.12, 0.8, 0.0, 0.3)
FIST_CHEST_R = mirror(FIST_CHEST_L)
# shots 23-24: leaning on both palms on the desk, out of breath
LEAN_L = hand((0.29, 0.28, 0.06), (0.275, 0.14, 0.02), "L", PRESS_POLE)
LEAN_R = mirror(LEAN_L)

SEATED = (90.0, 90.0)                        # thigh angle, knee bend

# head and torso (pitch down, yaw, roll), degrees, absolute in armature space
H_LAPTOP = (11.0, -1.0, 0.0)
T_REST = (4.0, 0.0, 0.0)
G_LAPTOP = (0.0, -0.012)


# ---------------------------------------------------------------- channels
class Track:
    def __init__(self, value, name=""):
        self.keys = [(1, self._t(value))]
        self.name = name

    @staticmethod
    def _t(v):
        return tuple(v) if isinstance(v, (tuple, list, Vector)) else (float(v),)

    def _from(self, f):
        """Continue from the value at f: anything keyed from f on is replaced."""
        value = self.at(f)
        dropped = [k[0] for k in self.keys if k[0] > f]
        if dropped:
            print("[anim_girl] WARNING: %s: a move from %d replaces keys on %s" % (self.name, f, dropped))
        self.keys = [k for k in self.keys if k[0] < f]
        self.keys.append((f, value))

    def to(self, f, dur, v):
        self._from(max(1, min(f - 1, f - dur)))
        self.keys.append((f, self._t(v)))

    def cut(self, f, v):
        self._from(f - 1)
        self.keys.append((f, self._t(v)))

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
    def __init__(self):
        self.t = {
            "loc": Track(SEAT), "chair": Track(0.0), "roll": Track(0.0), "yaw": Track(0.0), "torso": Track(T_REST), "head": Track(H_LAPTOP),
            "L": Track(KL), "R": Track(KR), "legL": Track(SEATED), "legR": Track(SEATED), "fist": Track(0.0),
            "gaze": Track(G_LAPTOP), "lid": Track(0.15), "pupil": Track(1.0),
            "smile": Track(0.0), "smirk": Track(0.0), "sad": Track(0.0), "gape": Track(0.0), "wide": Track(0.0),
            "yell": Track(0.0),
        }
        for k, tr in self.t.items():
            tr.name = k
        self.brows = [(1, "neutral")]
        self.eyes = [(1, "open")]
        self.still, self.no_blink, self.blinks = [], [], []
        self.pant = []                       # (first, last, amplitude in degrees, period in frames, amplitude at the end)
        self.hits = []
        self.evening = None
        self.override = {}                   # frame -> planned body (shot 16)

    def to(self, f, dur, **kw):
        for k, v in kw.items():
            self.t[k].to(f, dur, v)

    def cut(self, f, **kw):
        for k, v in kw.items():
            self.t[k].cut(f, v)

    def brow(self, f, name):
        self.brows.append((f, name))

    def eye(self, f, mode):
        self.eyes.append((f, mode))


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

    def voiced(self, line_id):
        l = self.ctx.line(line_id)
        runs = self.runs(line_id)
        if not runs:
            return Span(l["first_frame"], l["last_frame"])
        return Span(l["first_frame"] + runs[0][0], l["first_frame"] + runs[-1][1])

    def last_phrase(self, line_id, min_gap=4):
        """First voiced frame after the last pause of at least min_gap frames (the line's start if there is none)."""
        l = self.ctx.line(line_id)
        runs = self.runs(line_id)
        starts = [b[0] for a, b in zip(runs, runs[1:]) if b[0] - a[1] >= min_gap]
        return l["first_frame"] + (starts[-1] if starts else 0)

    def phrase2(self, line_id):
        """First voiced frame after the longest pause inside the line (its middle if it has no pause)."""
        l = self.ctx.line(line_id)
        runs = self.runs(line_id)
        if len(runs) < 2:
            return (l["first_frame"] + l["last_frame"]) // 2
        k = max(range(len(runs) - 1), key=lambda j: runs[j + 1][0] - runs[j][1])
        return l["first_frame"] + runs[k + 1][0]


# ---------------------------------------------------------------- solving the body
def turn(pitch, yaw, roll=0.0):
    return (Matrix.Rotation(math.radians(yaw), 3, "Z") @ Matrix.Rotation(math.radians(pitch), 3, "X")
            @ Matrix.Rotation(math.radians(roll), 3, "Y"))


def leg_dirs(a, bend):
    ra, rb = math.radians(a), math.radians(a - bend)
    return (0, -math.sin(ra), -math.cos(ra)), (0, -math.sin(rb), -math.cos(rb))


def solve(bones, torso, head, hands, legs):
    """Pose matrices (armature space) and matrix_basis per bone."""
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
        leg = legs[s]
        if isinstance(leg, dict):                 # shot 16: two-bone IK to an ankle point, the foot turned on its own
            hip = place("thigh" + s, (0, 0, -1)).translation.copy()
            l1, l2 = bones["thigh" + s].length, bones["shin" + s].length
            d = leg["ankle"] - hip
            dist = min(d.length, l1 + l2 - 1e-4)
            u = d.normalized()
            a = (l1 * l1 - l2 * l2 + dist * dist) / (2 * dist)
            off = math.sqrt(max(l1 * l1 - a * a, 0.0))
            v = (leg["pole"] - leg["pole"].dot(u) * u).normalized()
            place("thigh" + s, u * a + v * off)
            place("shin" + s, leg["ankle"] - tail("thigh" + s))
            place("foot" + s, rot=leg["rot"])
        else:
            th, sh = leg_dirs(*leg)
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
        place("hand" + s, tip - tail("forearm" + s))
    basis = {}
    for name, M in pose.items():
        b = bones[name]
        if b.parent is None:
            basis[name] = b.matrix_local.inverted() @ M
        else:
            local = b.parent.matrix_local.inverted() @ b.matrix_local
            basis[name] = local.inverted() @ pose[b.parent.name].inverted() @ M
    return pose, basis


class Body:
    """Geometry of her rig that the script needs to aim and land things: where her eyes are, where her mitts touch."""

    def __init__(self, rig):
        self.rig = rig
        self.bones = rig.data.bones
        self.pivot = bpy.data.objects[ep4.CHAIR].matrix_world.translation.copy()
        tmpl = bpy.data.objects["STU_Designer_Face_Eyes_neutral"]
        hb = self.bones["head"]
        p = Matrix.Translation((0, hb.length, 0)) @ tmpl.matrix_parent_inverse @ tmpl.matrix_basis @ Vector((0, -0.2442, 0.20))
        self.eye_off = hb.matrix_local.to_3x3() @ p                     # eye midpoint from the head joint, rest pose
        self.hand_verts = {}
        for side in (".L", ".R"):
            ob = bpy.data.objects["STU_Designer_Hand" + side]
            M = ob.matrix_parent_inverse @ ob.matrix_basis
            self.hand_verts[side] = [M @ v.co for v in ob.data.vertices]
        self.head_verts = []
        for name in ("STU_Designer_Head", "STU_Designer_Glasses"):
            ob = bpy.data.objects[name]
            M = ob.matrix_parent_inverse @ ob.matrix_basis
            self.head_verts += [M @ v.co for v in ob.data.vertices]

    def world(self, loc, chair, yaw, roll=0.0):
        """The rig's world matrix for a location in the chair's space, the chair's turn and how far it rolled back."""
        R = Matrix.Rotation(math.radians(chair), 4, "Z")
        p = self.pivot + Vector((0.0, roll, 0.0)) + (R.to_3x3() @ (Vector(loc) - self.pivot))
        return Matrix.Translation(p) @ Matrix.Rotation(math.radians(chair + yaw), 4, "Z")

    def head_joint(self, torso):
        b = self.bones["torso"]
        return b.head_local + turn(*torso) @ Vector((0, 0, b.length))

    def eyes(self, loc, chair, yaw, torso, head, roll=0.0):
        return self.world(loc, chair, yaw, roll) @ (self.head_joint(torso) + turn(*head) @ self.eye_off)

    def aim(self, target, loc, chair=0.0, yaw=0.0, torso=T_REST, tilt=0.0, share=1.0, roll=0.0):
        """Head (pitch, yaw, roll) that points her face at a world point; share < 1 leaves the rest to the eyes.
        Returns the head and the pupil shift that covers the rest."""
        head = (0.0, 0.0, tilt)
        for _ in range(3):
            e = self.eyes(loc, chair, yaw, torso, head, roll)
            d = Matrix.Rotation(math.radians(-(chair + yaw)), 3, "Z") @ (Vector(target) - e)
            pitch = math.degrees(math.atan2(-d.z, math.hypot(d.x, d.y)))
            hy = math.degrees(math.atan2(d.x, -d.y))
            head = (pitch, hy, tilt)
        partial = (pitch * share, hy * share, tilt)
        # pupils: x to her left (+x in the face), z up
        gaze = (max(-LOOK_X, min(LOOK_X, (hy - partial[1]) * PUPIL_PER_DEG)),
                max(-LOOK_Z, min(LOOK_Z, -(pitch - partial[0]) * PUPIL_PER_DEG)))
        return partial, gaze

    def mitt_low(self, side, torso, head, hands, fist, loc=SEAT, chair=0.0, yaw=0.0, roll=0.0):
        """Lowest world z of a mitt in this pose."""
        pose, _ = solve(self.bones, torso, head, hands, {".L": SEATED, ".R": SEATED})
        b = self.bones["hand" + side]
        M = self.world(loc, chair, yaw, roll) @ pose["hand" + side] @ Matrix.Translation((0, b.length, 0))
        return min((M @ fisted(v, fist)).z for v in self.hand_verts[side])


def fisted(v, k):
    """A mitt vertex (bone space at the fingertips) curled into a fist by k."""
    if k <= 0.0:
        return v
    x, y, z = v
    if y > -0.09:
        y = y + (-0.09 + (y + 0.09) * 0.3 - y) * k
    z = z * (1.0 + 0.2 * k)
    return Vector((x, y, z))


def land(body, h, side, torso, head, other, fist=0.0, top=DESK_TOP, loc=SEAT, chair=0.0, yaw=0.0, roll=0.0):
    """Shift a hand target up or down so its mitt rests exactly on a surface at height top."""
    for _ in range(3):
        hands = {side: h, (".R" if side == ".L" else ".L"): other}
        low = body.mitt_low(side, torso, head, hands, fist, loc, chair, yaw, roll)
        h = lift(h, top - low)
    return h


# ---------------------------------------------------------------- the performance
def perform(s, ctx, body):
    to, cut, brow, eye = s.to, s.cut, s.brow, s.eye
    beats = Beats(ctx)
    S, V, P2, VO = beats.shot, beats.line, beats.phrase2, beats.voiced
    anchor = bpy.data.objects["STU_Claude_Dock_Anchor"].matrix_world.translation
    clawd = anchor + Vector((0, 0, CLAWD_FACE_UP))
    turned = -ep4.CHAIR_TOWARDS_CLAWD_DEG

    def taps(a, b, gap=9):
        """Typing: small alternating taps of the hands on the keys between frames a and b."""
        f, left = a, True
        while f + 4 < b:
            h, base = ("L", KL) if left else ("R", KR)
            to(f + 2, 2, **{h: up(base, 0.012)})
            to(f + 4, 2, **{h: base})
            f += gap + (2 if left else -1)
            left = not left

    # 1: the room. She works calmly; the chime lands in the middle and she reads it
    s1 = S(1)
    chime = ctx.sfx("notify")["first_frame"]
    taps(s1.first + 4, chime - 2)
    to(chime + 5, 6, head=(9.0, -1.0, 0.0), gaze=(0.0, -0.006), lid=0.05)
    brow(chime + 6, "hmm")
    to(s1.last - 4, 14, head=(10.0, -2.0, 1.5))

    # 2: reads the mail, one brow up, and retells it to Clawd like to a friend; her eyes go to him towards the end
    s2, v01 = S(2), V("v01")
    p = P2("v01")
    hc, gc = body.aim(clawd, SEAT, share=0.55)
    cut(s2.first, head=(10.0, -2.0, 1.5), gaze=(0.0, -0.006))
    brow(s2.first, "hmm")
    to(s2.first + 6, 6, lid=0.18, smirk=0.15)
    to(p - 2, 8, head=(9.0, -3.0, -2.5))
    to(p + 6, 6, smirk=0.35, head=(8.0, -2.0, 3.0))            # she mocks the client's voice on the quote
    to(p + 20, 10, head=(9.5, -3.0, 0.0))
    look = VO("v01").last - 26
    to(look, 5, gaze=gc)
    brow(look, "smile")
    to(look + 14, 14, head=hc, smirk=0.25, lid=0.08)
    to(s2.last - 2, 6, smirk=0.2)

    # 4: head and shoulders round to Clawd (the chair stays), a light wave of the hand at the screen: "you know, that one"
    s4, v02 = S(4), V("v02")
    hc4, gc4 = body.aim(clawd, SEAT, torso=(3.0, -12.0, 0.0), share=0.85)
    hc4 = (hc4[0], hc4[1], 3.0)
    to(s4.first + 6, 6, head=hc4, gaze=gc4, torso=(3.0, -12.0, 0.0), smirk=0.3, smile=0.15)
    brow(s4.first + 2, "smile")
    to(s4.first + 6, 6, R=up(KR, 0.03))
    to(s4.first + 12, 6, R=WAVE_A)
    p = beats.last_phrase("v02")                                   # "Ну ты помнишь"
    b1 = max(s4.first + 17, p - 10)
    to(b1, 4, R=WAVE_B)
    to(b1 + 5, 4, R=WAVE_A)
    to(max(b1 + 9, p + 1), 4, R=WAVE_B)
    to(max(b1 + 14, p + 6), 5, R=WAVE_A)
    to(min(s4.last - 1, max(b1 + 14, p + 6) + 12), 12, R=KR)
    to(v02.last - 2, 8, head=(hc4[0] + 1.0, hc4[1], 4.0))

    # 5 (off camera): she waits for his answer
    s5 = S(5)
    to(s5.first + 10, 10, smirk=0.1, smile=0.0, head=(hc4[0], hc4[1], 1.5))

    # 6: brows up, "И что?", the right hand comes up open
    s6, v04 = S(6), V("v04")
    cut(s6.first, lid=0.0)
    brow(s6.first, "shocked")
    to(s6.first + 7, 7, R=SHRUG_R, head=(hc4[0] - 3.0, hc4[1], 6.0), torso=(1.0, -12.0, 0.0), smirk=0.25)
    to(v04.last + 2, 6, head=(hc4[0] - 2.0, hc4[1], 5.0))

    # 7 (his close-up): she stays as she was in 6
    # 8: silent "really?". Not fear but skepticism: a flat stare at him, the lids slide down "-_-", one brow up, the
    # mouth pressed into a line, the head tilts a little
    s8 = S(8)
    cut(s8.first, wide=0.0, pupil=1.0, lid=0.2, smirk=0.0, smile=0.0, sad=0.0, gaze=(gc4[0], gc4[1] - 0.006),
        head=(hc4[0] - 24.0, hc4[1], 4.0))
    brow(s8.first, "hmm")
    # The chin comes up and she looks down at him from above with her eyes only: the high camera sees her face,
    # not the top of her head (head pitch is positive down)
    to(s8.first + 10, 9, lid=SKEPTIC_LID, sad=0.12, smirk=0.12, head=(hc4[0] - 24.0, hc4[1], 6.0),
       torso=(3.0, -12.0, 0.0), gaze=(gc4[0], gc4[1] - 0.006))
    s.still.append((s8.first + 12, s8.last))
    s.no_blink.append(s8)

    # 9: still flat and skeptical on «Совсем ничего?», reproachful on «Мы полгода вместе». The palm comes down slowly
    s9, v06 = S(9), V("v06")
    cut(s9.first, wide=0.0, pupil=1.0, gape=0.0, sad=0.12, smirk=0.12, lid=SKEPTIC_LID)
    brow(s9.first, "hmm")
    to(s9.first + 10, 10, head=(hc4[0] + 3.0, hc4[1], 4.0), torso=(5.0, -10.0, 0.0))
    t9 = (5.0, -10.0, 0.0)
    palm = land(body, PALM_R, ".R", t9, H_LAPTOP, KL)
    down_at = s9.first + 6 + 30
    to(s9.first + 6 + 18, 18, R=lift(palm, 0.06))
    to(down_at, 12, R=palm)
    to(P2("v06") + 4, 10, sad=0.35, smirk=0.0, lid=0.45, head=(hc4[0] + 4.0, hc4[1], -3.0))

    # 10 (off camera): he says something nice. Hurt turns into indignation
    s10 = S(10)
    to(s10.first + 20, 16, sad=0.3, lid=0.15)
    brow(s10.last - 8, "hmm")

    # 13: the last argument: she points at the screen, with reproach
    s13, v08 = S(13), V("v08")
    cut(s13.first, sad=0.3, lid=0.25, wide=0.0)
    brow(s13.first, "hmm")
    to(s13.first + 4, 4, gaze=(-0.004, -0.014))                   # a glance at the screen as the hand goes up
    to(s13.first + 10, 9, R=POINT_R, torso=(6.0, -8.0, 0.0))
    to(s13.first + 13, 5, gaze=gc4)
    jab = VO("v08").last - 10                                      # "гениальный"
    to(jab, 3, R=POINT_JAB)
    to(jab + 4, 4, R=POINT_R)
    to(jab + 2, 4, head=(hc4[0] + 3.0, hc4[1], -4.0))
    to(v08.last + 2, 6, head=(hc4[0] + 1.0, hc4[1], -2.0))

    # 14 (off camera): "Это похоже на меня." The hand goes back to the keys, she squares up to the laptop
    s14 = S(14)
    to(s14.first + 12, 12, R=KR, torso=(4.0, -4.0, 0.0), sad=0.0)
    to(s14.last - 2, 10, lid=0.05)

    # 15: bright and decided. The chair turns to Clawd right on the cut, the line lands on the end of the turn
    s15, v10 = S(15), V("v10")
    hT, gT = body.aim(clawd, SEAT, chair=turned, share=0.9, roll=ROLL_BACK)
    turn_end = max(s15.first + 18, min(VO("v10").last - 8, s15.first + 32))
    cut(s15.first, lid=0.0)
    brow(s15.first, "smile")
    to(s15.first + 4, 4, L=up(KL, 0.04), R=up(KR, 0.04), smile=0.3)
    # she pushes the chair back from the desk as it starts to turn, her hands go to the armrests on the way
    to(s15.first + 12, 12, roll=ROLL_BACK)
    to(turn_end, turn_end - s15.first, chair=turned, torso=(6.0, 0.0, 0.0), gaze=gT)
    on_rests = next(f for f in range(s15.first, turn_end) if s.t["chair"].at(f)[0] <= -ARMREST_BY_DEG + 2.0)
    to(on_rests - 7, on_rests - 7 - (s15.first + 4), L=CLEAR_L, R=CLEAR_R)
    to(on_rests, 7, L=LAP_L, R=LAP_R)
    # the head stays on him while the chair turns under her; "Ладно." gets a decided nod
    nod = v10.first + 3

    def nod_at(f):
        return 4.0 * max(0.0, 1.0 - abs(f - nod) / 5.0)

    f = s15.first + 3
    while f <= turn_end - 3:
        h, _ = body.aim(clawd, SEAT, chair=s.t["chair"].at(f)[0], torso=(6.0, 0.0, 0.0), share=0.9,
                        roll=s.t["roll"].at(f)[0])
        to(f, 3, head=(h[0] + nod_at(f), h[1], 0.0))
        f += 3
    to(turn_end, 3, head=hT)
    to(P2("v10") + 4, 6, smile=0.45)
    to(turn_end + 6, 6, head=(hT[0] + 2.0, hT[1], 3.0))
    to(v10.last + 2, 6, head=(hT[0], hT[1], 2.0))

    # 16: she gets up, pushes the chair away, walks to the board, takes the marker and draws. The body of the whole shot
    # is planned in girl_board16 (called from build); here only the face: keen, a small smile
    s16 = S(16)
    to(s16.first + 12, 12, smile=0.35)
    brow(s16.first + 4, "delighted")

    # ---- evening. From the first frame of 27 everything is different: slumped, headphones on her neck, tired lids
    s27, s25, v12 = S(27), S(25), V("v12")
    s.evening = s27.first
    slumped_torso = (16.0, 0.0, 0.0)
    slumped_loc = (0.0, SEAT[1], SEAT[2] - 0.01)
    hS, gS = body.aim(clawd, slumped_loc, chair=turned, torso=slumped_torso, share=0.75, roll=ROLL_BACK)
    head_s = (hS[0] + 6.0, hS[1], -4.0)
    cut(s27.first, chair=turned, roll=ROLL_BACK, loc=slumped_loc, torso=slumped_torso, head=head_s, gaze=(gS[0], gS[1] + 0.006),
        L=SLUMP_L, R=SLUMP_R, lid=0.5, smile=0.0, smirk=0.0, sad=0.25, wide=0.0, pupil=1.0)
    brow(s27.first, "sleepy")
    # 25: a second of silence (a slow blink, an exhale), then she finishes the story, worn out
    s.blinks.append(s25.first + 8)
    exhale = v12.first - 8
    to(exhale, 8, torso=(18.5, 0.0, 0.0), head=(head_s[0] + 2.0, head_s[1], -4.0))
    to(v12.first + 4, 10, torso=slumped_torso, head=head_s)
    to(P2("v12") + 6, 12, head=(head_s[0] - 2.0, head_s[1], -2.0), lid=0.55)
    to(v12.last - 2, 10, head=(head_s[0] + 2.0, head_s[1], -3.0))          # "...тот баннер." comes to rest

    # 18: tired, but hoping: the head comes up a little, the question tilts it
    s18, v13 = S(18), V("v13")
    hH, gH = body.aim(clawd, slumped_loc, chair=turned, torso=(12.0, 0.0, 0.0), share=0.9, roll=ROLL_BACK)
    cut(s18.first, lid=0.38)
    brow(s18.first, "smile")
    to(s18.first + 8, 8, head=(hH[0], hH[1], 3.0), torso=(12.0, 0.0, 0.0), gaze=gH, sad=0.0, smile=0.2)
    to(VO("v13").last, 6, head=(hH[0] - 1.0, hH[1], 7.0))

    # 19 (his close-up): he says he remembers. Relief
    s19 = S(19)
    to(s19.first + 16, 10, smile=0.4, lid=0.42, head=(hH[0], hH[1], 4.0))

    # 20: the last of her strength: chair back to the laptop, hands on the keys. The turn ends well before the cut
    s20, v15 = S(20), V("v15")
    t_start = s20.first + 2
    t_end = t_start + 22
    to(s20.first + 6, 6, torso=(9.0, 0.0, 0.0), loc=SEAT)                  # a breath in, she sits up
    to(t_end, t_end - t_start, chair=0.0, head=H_LAPTOP, gaze=G_LAPTOP, lid=0.35)
    to(t_end, t_end - s20.first - 6, torso=T_REST)
    off_rests = next(f for f in range(t_start, t_end + 1) if s.t["chair"].at(f)[0] >= -ARMREST_BY_DEG + 2.0)
    to(off_rests + 6, 6, L=CLEAR_L, R=CLEAR_R)
    to(t_end + 10, 12, roll=0.0)                                           # and rolls back in to the desk
    to(t_end + 8, t_end + 8 - (off_rests + 6), L=up(KL, 0.06), R=up(KR, 0.06))
    to(t_end + 14, 6, L=KL, R=KR)
    nod = max(P2("v15"), t_end) + 4                                        # "Как в тот раз!"
    to(nod, 4, head=(H_LAPTOP[0] + 4.0, H_LAPTOP[1], 0.0), smile=0.45)
    to(nod + 6, 6, head=H_LAPTOP)
    taps(max(t_end + 8, nod + 6), s20.last - 1, gap=8)

    # 21 (off camera): she types, and stops as his line sinks in
    s21, v16 = S(21), V("v16")
    taps(s21.first + 2, VO("v16").last - 6, gap=8)
    to(VO("v16").last + 4, 8, smile=0.0)

    # 22: the hands freeze over the keys. At the very end the fists start up
    s22 = S(22)
    cut(s22.first, wide=0.35, pupil=0.65, lid=0.05, smile=0.0)
    to(s22.first + 4, 4, L=up(KL, 0.035), R=up(KR, 0.035))
    brow(s22.first + 6, "angry")
    rise = s22.last - 5
    s.still.append((s22.first + 4, rise))
    s.no_blink.append(s22)

    # 28: the explosion. The fists hit the desk exactly on RAGE_HITS, then she throws her head back and yells upwards
    s28 = S(28)
    hits = [s28.first + h for h in ep4.RAGE_HITS]
    s.hits = hits
    t_hit, t_up = (12.0, 0.0, 0.0), (0.0, 0.0, 0.0)
    h_hit, h_up = (16.0, -2.0, 0.0), (2.0, -2.0, 0.0)
    fist_l = land(body, FIST_DESK_L, ".L", t_hit, h_hit, FIST_DESK_R, fist=1.0)
    fist_r = land(body, FIST_DESK_R, ".R", t_hit, h_hit, fist_l, fist=1.0)
    to(rise + 3, 3, fist=1.0)
    first_up = hits[0] - 3
    to(first_up, first_up - rise, L=FIST_UP_L, R=FIST_UP_R, torso=t_up, head=h_up, wide=0.6, pupil=PUPIL_SMALL)
    prev = first_up
    for i, hf in enumerate(hits):
        if i:
            peak = hf - 4
            to(peak, peak - prev, L=FIST_UP_L, R=FIST_UP_R, torso=t_up, head=h_up)
        a_l, a_r = s.t["L"].at(hf - 3), s.t["R"].at(hf - 3)
        to(hf - 1, 2, L=mix(a_l, fist_l, 0.8), R=mix(a_r, fist_r, 0.8))      # the slam speeds up into the desk
        to(hf, 1, L=fist_l, R=fist_r)
        to(hf, 3, torso=t_hit, head=h_hit)
        prev = hf + 2
        to(prev, 2, L=lift(fist_l, 0.006), R=lift(fist_r, 0.006))
    yell = hits[-1] + 4
    to(yell + 8, 10, L=FIST_CHEST_L, R=FIST_CHEST_R, torso=(8.0, 0.0, 0.0), head=(-38.0, 0.0, 0.0), yell=1.0)
    eye(yell + 4, "closed")
    bleep = ctx.sfx("bleep")
    bleep_end = bleep["first_frame"] + len(envelope(ctx.audio_path(bleep))) - 1
    to(bleep_end + 2, 4, yell=0.0)
    s.no_blink.append(s28)

    # 23 (off camera) and 24: out of breath, leaning on her palms. In 24 she slowly looks straight into the lens and holds
    s23, s24 = S(23), S(24)
    eye(bleep_end + 3, "open")
    brow(bleep_end + 3, "neutral")
    lean_t = (10.0, 0.0, 0.0)
    lean_l = land(body, LEAN_L, ".L", lean_t, H_LAPTOP, LEAN_R)
    lean_r = land(body, LEAN_R, ".R", lean_t, H_LAPTOP, lean_l)
    to(s23.first + 6, 7 + (s23.first - s28.last), L=lift(lean_l, 0.10), R=lift(lean_r, 0.10), fist=0.0)
    to(s23.first + 14, 8, L=lean_l, R=lean_r)
    to(s23.first + 14, 15 + (s23.first - s28.last), torso=lean_t, head=(22.0, 0.0, 0.0),
       wide=0.2, pupil=0.8, lid=0.2, gape=0.12)
    lens = Vector(ep4.LOOK_INTO_LENS[24])
    h_lens, _ = body.aim(lens, SEAT, torso=lean_t)
    s.lens_head = h_lens
    cut(s24.first, head=(20.0, 1.5, 0.0), gaze=(0.0, -0.012), wide=0.15)
    eyes_up = s24.first + 3
    to(eyes_up + 5, 5, gaze=(0.0, 0.0))
    look_end = eyes_up + 12
    to(look_end, 12, head=h_lens, lid=0.12, wide=0.05)
    s.lens_from = look_end
    # she holds the stare a moment, her chin wobbles, and she bursts into over-the-top anime tears: T_T eyes, two
    # streams down her cheeks, a wobbling wail and heaving sobs, still facing the lens
    quiver = look_end + 3
    brow(quiver, "panic")
    to(quiver + 4, 4, sad=0.75, wide=0.2)
    cry = quiver + 5
    eye(cry, "cry")
    s.tears = (cry, s24.last)
    to(cry + 3, 3, sad=1.0, gape=0.3)
    f, k = cry + 3, 0
    while f + 3 <= s24.last:
        f += 3
        k += 1
        to(f, 3, gape=0.44 if k % 2 else 0.28)
    pant_a = s28.last - 4                                           # it calms down slowly through the stare...
    sob = pant_a + 9 * math.ceil((cry - pant_a) / 9)               # ...and gives way to sobs where a breath ends
    s.pant.append((pant_a, sob, 2.4, 18, 1.4))
    s.pant.append((sob, s24.last, SOB_DEG, SOB_PERIOD, SOB_DEG))
    s.still.append((s24.first, s24.last))
    s.no_blink.append((s24.first, s24.last))                       # no blink spills over the cut into the stare

    # 29 (off camera): she lies down. 30: face down on the desk among the papers, arms on the desk, only breathing
    s29, s30 = S(29), S(30)
    loc_l, roll_l, torso_l, head_l = lying_pose(body)
    arm_l = world_hand(body, (0.40, 0.27, 0.06), (0.385, 0.13, 0.02), PRESS_POLE, loc_l, roll_l)
    arm_r = world_hand(body, (-0.40, 0.27, 0.06), (-0.385, 0.13, 0.02), mirror_pole(PRESS_POLE), loc_l, roll_l)
    arm_l = land(body, arm_l, ".L", torso_l, head_l, arm_r, loc=loc_l, roll=roll_l)
    arm_r = land(body, arm_r, ".R", torso_l, head_l, arm_l, loc=loc_l, roll=roll_l)
    down = s29.first + 36
    eye(s29.first, "closed")                                  # still sobbing, eyes shut, as she sinks onto the desk
    to(s29.first + 18, 14, roll=roll_l)                       # she shoves the chair back a little
    to(down, 26, loc=loc_l, torso=torso_l, head=head_l, L=arm_l, R=arm_r, gape=0.0, wide=0.0, pupil=1.0, lid=0.6,
       sad=0.3)
    s.pant.append((s29.first, down, 0.9, 22, 0.5))
    s.still.append((down, s30.last))
    s.lying = (down, s30.last)


def mix(a, b, k):
    return tuple(x + (y - x) * k for x, y in zip(a, b))


def world_hand(body, wrist, tip, pole, loc, roll=0.0):
    """A hand target given in world x, y and height above the desk, for the rig at loc with the chair straight."""
    inv = body.world(loc, 0.0, 0.0, roll).inverted()
    w = inv @ Vector((wrist[0], wrist[1], wrist[2] + DESK_Z))
    t = inv @ Vector((tip[0], tip[1], tip[2] + DESK_Z))
    return (*w, *t, *pole)


def lying_pose(body):
    """Face down on the desk: the head rests on the keyboard, its crown clear of the laptop. She leans in from the hips
    and the chair rolls back as far as that takes, so her neck does not fold more than it must.
    Returns (loc, chair roll, torso, head)."""
    best = None
    laptop = bpy.data.objects["STU_Laptop"]
    stand = bpy.data.objects["STU_Laptop_Stand"]
    clear_y = max(max((o.matrix_world @ Vector(c)).y for c in o.bound_box) for o in (laptop, stand)) + 0.015
    hb = body.bones["head"]
    for tp in range(10, 31, 5):
        for hp in range(72, 101, 4):
            torso, head = (float(tp), 0.0, 0.0), (float(hp), 0.0, 0.0)
            pose, _ = solve(body.bones, torso, head, {".L": KL, ".R": KR}, {".L": SEATED, ".R": SEATED})
            M = body.world(SEAT, 0.0, 0.0) @ pose["head"] @ Matrix.Translation((0, hb.length, 0))
            pts = [M @ v for v in body.head_verts]
            dz = KEY_TOP + 0.004 - min(p.z for p in pts)
            dy = max(0.0, clear_y - min(p.y for p in pts))
            cost = abs(dz) * 3 + dy * 0.5 + max(0.0, (hp - tp) - 58) * 0.01
            if dz < -0.005 or dz > 0.04 or dy > 0.16:
                cost += 9
            if best is None or cost < best[0]:
                best = (cost, (SEAT[0], SEAT[1], SEAT[2] + dz), dy, torso, head)
    print("[anim_girl] lying pose: loc %s roll %.3f torso %s head %s" % (
        tuple(round(v, 3) for v in best[1]), best[2], best[3], best[4]))
    return best[1:]


def idle(f, s):
    """Slow breathing and a little head drift; nothing in the frozen beats. Panting where the script asks for it."""
    k = 1.0
    for a, b in s.still:
        if a <= f <= b:
            k = 0.0
            break
        k = min(k, max(0.0, min(1.0, abs(f - a) / 6.0)), max(0.0, min(1.0, abs(f - b) / 6.0)))
    head = (0.55 * math.sin(f / 23.0), 0.7 * math.sin(f / 37.0 + 1.1), 0.5 * math.sin(f / 31.0 + 2.3))
    breath, lift_z = 0.4 * math.sin(2 * math.pi * f / 96.0), 0.0
    for a, b, amp, period, amp_end in s.pant:
        if a <= f <= b:
            fade = min(1.0, (f - a) / 8.0) * (amp + (amp_end - amp) * (f - a) / (b - a))
            ph = math.sin(2 * math.pi * (f - a) / period)
            breath = fade * ph
            lift_z = 0.0018 * fade * ph
    if getattr(s, "lying", None) and s.lying[0] <= f <= s.lying[1]:
        breath, lift_z = 0.3 * math.sin(2 * math.pi * f / 110.0), 0.0
    return tuple(k * v for v in head), breath, lift_z


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
    for kp in fc.keyframe_points:
        kp.interpolation = mode
    fc.update()
    return fc


def sample(s, body, f):
    """Everything the body needs on frame f: (world matrix of the rig, chair turn, bone bases, pose)."""
    t = s.t
    drift, breath, lift_z = idle(f, s)
    ov = s.override.get(f)
    if ov:                                         # shot 16 (girl_board16): the body is planned in world space
        torso = list(ov["torso"])
        torso[0] += breath
        head = [a + b for a, b in zip(ov["head"], drift)]
        pose, basis = solve(body.bones, torso, head, ov["hands"], ov["legs"])
        return ov["W"], ov["chair"], basis, pose
    torso = list(t["torso"].at(f))
    torso[0] += breath
    head = [a + b for a, b in zip(t["head"].at(f), drift)]
    hands = {".L": t["L"].at(f), ".R": t["R"].at(f)}
    legs = {".L": t["legL"].at(f), ".R": t["legR"].at(f)}
    pose, basis = solve(body.bones, torso, head, hands, legs)
    loc = Vector(t["loc"].at(f)) + Vector((0, 0, lift_z))
    chair, yaw, roll = t["chair"].at(f)[0], t["yaw"].at(f)[0], t["roll"].at(f)[0]
    return body.world(loc, chair, yaw, roll), (chair, roll, 0.0), basis, pose


def key_body(rig, s, body, frame_end):
    samples, prev, locs, rots, chairs = {}, {}, [], [], []
    for f in range(1, frame_end + 1):
        W, chair, basis, _ = sample(s, body, f)
        for name, M in basis.items():
            q = M.to_quaternion()
            if name in prev and prev[name].dot(q) < 0:
                q.negate()
            prev[name] = q
            samples.setdefault(name, []).append((f, tuple(q)))
        locs.append((f, tuple(W.translation)))
        rots.append((f, W.to_euler("XYZ").z))
        chairs.append((f, chair))
    action = action_for(rig, ACTION)
    for name, keys in samples.items():
        rig.pose.bones[name].rotation_mode = "QUATERNION"
        path = f'pose.bones["{name}"].rotation_quaternion'
        for i in range(4):
            write(action, rig, path, i, [(f, q[i]) for f, q in keys], "LINEAR")
    rig.rotation_mode = "XYZ"
    for i in range(3):
        write(action, rig, "location", i, [(f, v[i]) for f, v in locs], "LINEAR")
    unwrapped, last = [], None
    for f, z in rots:                                     # keep the yaw continuous
        if last is not None:
            while z - last > math.pi:
                z -= 2 * math.pi
            while z - last < -math.pi:
                z += 2 * math.pi
        unwrapped.append((f, z))
        last = z
    write(action, rig, "rotation_euler", 2, unwrapped, "LINEAR")

    chair = bpy.data.objects[ep4.CHAIR]
    base, x0, y0 = chair.rotation_euler.z, chair.location.x, chair.location.y
    chair.rotation_mode = "XYZ"
    act = action_for(chair, ep4.PREFIX + "Chair")
    write(act, chair, "rotation_euler", 2, thin([(f, base + math.radians(c[0])) for f, c in chairs]), "LINEAR")
    write(act, chair, "location", 1, thin([(f, y0 + c[1]) for f, c in chairs]), "LINEAR")
    write(act, chair, "location", 0, thin([(f, x0 + c[2]) for f, c in chairs]), "LINEAR")


def thin(pairs, eps=1e-6):
    """Drop keys that a straight line through their neighbours already gives."""
    out = [pairs[0]]
    for i in range(1, len(pairs) - 1):
        (fa, a), (f, v), (fb, b) = out[-1], pairs[i], pairs[i + 1]
        if abs(a + (b - a) * (f - fa) / (fb - fa) - v) > eps:
            out.append(pairs[i])
    out.append(pairs[-1])
    return out


# ---------------------------------------------------------------- face meshes
def material(name):
    return bpy.data.materials.get("STU_Designer_" + name) or bpy.data.materials[name]


def face_object(ctx, rig, template, name, verts, faces, mats, face_mats):
    me = bpy.data.meshes.new(ep4.PREFIX + "Designer_Face_" + name)
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


def build_cry(ctx, rig, tmpl):
    """Anime crying, T_T: two flat dark bars for the squeezed eyes and two tear streams running down from under them.
    The streams have a "flow" shape key (0: still at the eyes, 1: down to the chin) and a "wave" key that ripples them."""
    bars = mirrored([(0.045, 0.155, 0.188, 0.204)])
    v, f = rects(bars, -0.2449)
    cry = face_object(ctx, rig, tmpl, "Eyes_cry", v, f, ["DSG_pupil"], [0] * len(f))

    mat = bpy.data.materials.new(ep4.PREFIX + "Designer_Tears")
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = TEAR_COLOUR
    bsdf.inputs["Emission Color"].default_value = TEAR_COLOUR
    bsdf.inputs["Emission Strength"].default_value = 0.6
    bsdf.inputs["Roughness"].default_value = 0.15
    mat.diffuse_color = TEAR_COLOUR
    y, top, bottom, n = -0.2457, 0.188, 0.004, 10
    rows = [top + (bottom - top) * i / n for i in range(n + 1)]
    verts, faces, flow, wave = [], [], [], []
    for cx in (0.10, -0.10):
        base = len(verts)
        for i, z in enumerate(rows):
            t = i / n
            half = 0.014 + 0.012 * t                     # the stream widens as it runs down
            ripple = 0.004 * math.sin(t * 2.6 * math.pi) * t
            for sx in (-1, 1):
                verts.append((cx + sx * half, y, top))
                flow.append((cx + sx * half, y, z))
                wave.append((cx + sx * half + ripple, y, top))      # only the sideways ripple, added on top of flow
            if i:
                a = base + 2 * (i - 1)
                faces.append((a, a + 1, a + 3, a + 2))
    ob = face_object(ctx, rig, tmpl, "Tears", verts, faces, [mat.name], [0] * len(faces))
    shape(ob, "flow", flow)
    shape(ob, "wave", wave, slider_min=-1.0)
    return cry, ob


def key_tears(ctx, s, cry_eyes, tears):
    a, b = s.tears
    key_visibility(tears, [(1, False), (a, True), (b + 1, False)])
    keys = tears.data.shape_keys
    act = action_for(keys, ep4.PREFIX + "Girl_Tears")
    write(act, keys, 'key_blocks["flow"].value', 0, [(1, 0.0), (a, 0.08), (a + TEAR_FLOW_FRAMES, 1.0), (b, 1.0)])
    # "wave" swings the ripple from side to side, on twos, once the streams have run down
    write(act, keys, 'key_blocks["wave"].value', 0,
          [(1, 0.0)] + [(f, 0.0 if f < a + TEAR_FLOW_FRAMES else (0.9 if (f - a) // 2 % 2 else -0.9))
                        for f in range(a, b + 1, 2)], "CONSTANT")


def build_mouth(ctx, rig, tmpl):
    n = 17
    us = [-1 + 2 * i / (n - 1) for i in range(n)]
    Y_LIP, Y_DARK, Z0 = -0.2448, -0.2452, 0.084

    def state(gap=0.0, smile=0.0, smirk=0.0, sad=0.0, narrow=1.0, drop=0.0):
        out = []
        for u in us:
            x = u * 0.052 * narrow * (1 + 0.16 * smile + 0.05 * smirk - 0.10 * (gap > 0))
            taper = math.sqrt(max(0.0, 1 - u ** 4))
            c = Z0 + smile * (0.026 * u * u - 0.007) + smirk * (0.03 * max(u, 0.0) ** 2 - 0.004) \
                + sad * (0.006 - 0.020 * u * u) - drop
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
    # the yell: wide and tall, on top of "open"; its delta is added, so it is the extra over the closed mouth
    shape(ob, "yell", state(gap=0.016, narrow=1.25, drop=0.006))
    return ob


def build_angry_brows(ctx, rig):
    """Brows pulled down and in, for the explosion. Named like the Studio sets, so they swap the same way."""
    tmpl = bpy.data.objects["STU_Designer_Face_Brows_neutral"]
    y = -0.2444
    verts = [(0.050, y, 0.282), (0.160, y, 0.326), (0.160, y, 0.344), (0.050, y, 0.302),
             (-0.160, y, 0.326), (-0.050, y, 0.282), (-0.050, y, 0.302), (-0.160, y, 0.344)]
    return face_object(ctx, rig, tmpl, "Brows_angry", verts, [(0, 1, 2, 3), (4, 5, 6, 7)], ["DSG_hair_hi"], [0, 0])


def build_fists(rig, s):
    """A shape key on each mitt (and what it wears) curls its end into a fist."""
    for ob in (o for o in rig.children if o.type == "MESH" and o.parent_bone in ("hand.L", "hand.R")):
        M = ob.matrix_parent_inverse @ ob.matrix_basis
        back = M.inverted()
        shape(ob, "fist", [tuple(back @ fisted(M @ v.co, 1.0)) for v in ob.data.vertices])
        keys = ob.data.shape_keys
        write(action_for(keys, ep4.PREFIX + "Girl_Fist_" + ob.name), keys, 'key_blocks["fist"].value', 0,
              [(f, v[0]) for f, v in s.t["fist"].keys])


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


def voiced_items(ctx):
    """Her lines, plus the bleep that stands in for her yell in shot 28: (first frame, envelope, last frame allowed)."""
    out = [(l["first_frame"], envelope(ctx.audio_path(l)), l["last_frame"]) for l in ctx.lines("girl")]
    b = ctx.sfx("bleep")
    shot = next(s for s in ctx.shots if any(f["id"] == "bleep" for f in s.get("sfx", [])))
    out.append((b["first_frame"], envelope(ctx.audio_path(b)), shot["last_frame"]))
    return out


def lip_sync(ctx):
    """{frame: 0..1}, on twos, so the mouth reads as flaps and not as a tremble. Never past the line's last frame."""
    out = {}
    for start, e, last in voiced_items(ctx):
        peak = max(float(e.max()), 1e-4)
        out[start - 1] = 0.0                         # shut until the line starts, or the keys ramp across the silence
        for i in range(0, len(e), 2):
            if start + i > last - 1:
                break
            level = float(e[i:i + 2].max()) / peak
            v = 0.0 if level < 0.12 else min(1.0, (level / 0.75) ** 0.7)
            if v > 0 and (i // 2) % 3 == 2:          # a short close inside long vowels keeps it talking
                v *= 0.55
            out[start + i] = v
        out[min(start + len(e) + 1, last)] = 0.0
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
    rng = random.Random(4)
    blinks = set()
    for b in s.blinks:
        blinks.update((b, b + 1, b + 2))
    f = 22
    while f < end:
        if not any(a - 3 <= f <= b for a, b in s.no_blink):
            blinks.update((f, f + 1, f + 2))
        f += rng.randint(50, 92)
    shows = {"whites": ("open",), "pupils": ("open",), "lids": ("open",), "closed": ("closed",), "cry": ("cry",)}
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

    pup_key = parts["pupils"].data.shape_keys
    act = action_for(pup_key, ep4.PREFIX + "Girl_Pupils")
    write(act, pup_key, 'key_blocks["look_x"].value', 0, [(f, v[0] / LOOK_X) for f, v in s.t["gaze"].keys])
    write(act, pup_key, 'key_blocks["look_z"].value', 0, [(f, v[1] / LOOK_Z) for f, v in s.t["gaze"].keys])
    write(act, pup_key, 'key_blocks["small"].value', 0,
          [(f, (1 - v[0]) / (1 - PUPIL_SMALL)) for f, v in s.t["pupil"].keys])
    white_key = parts["whites"].data.shape_keys
    write(action_for(white_key, ep4.PREFIX + "Girl_Whites"), white_key, 'key_blocks["wide"].value', 0,
          [(f, v[0]) for f, v in s.t["wide"].keys])
    lid_key = parts["lids"].data.shape_keys
    write(action_for(lid_key, ep4.PREFIX + "Girl_Lids"), lid_key, 'key_blocks["close"].value', 0,
          [(f, v[0]) for f, v in s.t["lid"].keys])

    mouth_key = parts["mouth"].data.shape_keys
    act = action_for(mouth_key, ep4.PREFIX + "Girl_Mouth")
    for name in ("smile", "smirk", "sad", "yell"):
        write(act, mouth_key, f'key_blocks["{name}"].value', 0, [(f, v[0]) for f, v in s.t[name].keys])
    lips = lip_sync(ctx)
    frames = sorted(set(lips) | set(s.t["gape"].frames()) | {1, end})
    write(act, mouth_key, 'key_blocks["open"].value', 0,
          [(f, max(lips.get(f, 0.0), s.t["gape"].at(f)[0])) for f in frames], "LINEAR")

    for name, ob in parts["brows"].items():
        ch, last = [], None
        for f, state in sorted(s.brows, key=lambda k: k[0]):
            on = state == name
            if on != last:
                ch.append((f, on))
                last = on
        if not ch[0][1] and ch[0][0] != 1:
            ch.insert(0, (1, False))
        key_visibility(ob, ch)


def key_headphones(s):
    """Day: on her head, as in the Studio. From the first evening frame: down on her neck."""
    ev = s.evening
    key_visibility(bpy.data.objects["STU_Designer_Headphones_Head_HoodDown"], [(1, True), (ev, False)])
    key_visibility(bpy.data.objects["STU_Designer_Headphones_Neck"], [(1, False), (ev, True)])
    other = bpy.data.objects["STU_Designer_Headphones_Head"]
    other.hide_render = other.hide_viewport = True


# ---------------------------------------------------------------- build
def build(ctx):
    rig = bpy.data.objects[ep4.GIRL_RIG]
    tmpl_eye = bpy.data.objects["STU_Designer_Face_Eyes_neutral"]
    tmpl_mouth = bpy.data.objects["STU_Designer_Face_Mouth_neutral"]

    for ob in rig.children:                    # her Studio eyes and mouths are replaced; the brows stay
        if "_Face_Mouth_" in ob.name or "_Face_Eyes_" in ob.name:
            ob.hide_render = ob.hide_viewport = True

    whites, pupils, lids, closed = build_eyes(ctx, rig, tmpl_eye)
    cry_eyes, tears = build_cry(ctx, rig, tmpl_eye)
    mouth_ob = build_mouth(ctx, rig, tmpl_mouth)
    build_angry_brows(ctx, rig)
    parts = {
        "whites": whites, "pupils": pupils, "lids": lids, "closed": closed, "cry": cry_eyes, "mouth": mouth_ob,
        "brows": {o.name.rsplit("_", 1)[1]: o for o in rig.children if "_Face_Brows_" in o.name},
    }

    body = Body(rig)
    script = Script()
    perform(script, ctx, body)
    girl_board16.Board16(script, ctx, body, sys.modules[__name__]).build()

    key_body(rig, script, body, ctx.frame_end)
    key_face(ctx, rig, script, parts)
    key_tears(ctx, script, cry_eyes, tears)
    build_fists(rig, script)
    key_headphones(script)
    print("[anim_girl] hits on", script.hits, "lens look from", script.lens_from)
    return rig
