"""Shared contract of the EP4 Blender build. Every part is a module with build(ctx).

Build order (build_blend.py): stage -> anim_clawd -> anim_girl -> cameras. The build always starts from a fresh
studio.blend, so a part does not need to clean up after itself. Everything a part adds is named EP4_*.

Who owns what:
- stage:      scene settings, sound strips, day/evening light, props (board, papers, extra cups) and their motion.
- anim_clawd: Clawd (appended and rigged on STU_Claude_Dock_Anchor), his turns, nods, speech glow, looks to camera.
- anim_girl:  her body, face, lip sync, the chair (STU_Chair) she sits on and turns.
- cameras:    one camera per shot, EP4_Cam_<id>, switched on the shot's first frame. Runs last, so it can read the
              animated poses of both characters.

Numbers that two parts must agree on live here and nowhere else. Change them only here.
"""
import json
from pathlib import Path

import bpy

EP = Path(__file__).resolve().parents[1]
CHARACTER = EP.parents[1]
STUDIO_BLEND = CHARACTER / "scene" / "locations" / "studio" / "studio.blend"
CLAWD_BLEND = CHARACTER / "scene" / "characters" / "clawd" / "clawd.blend"
OUTPUT_BLEND = EP / "ep-004.blend"
OVERLAYS = EP / "overlays"

PREFIX = "EP4_"
SCENE = "EP4_Pomnish"
ROOT_COLLECTION = "EP4_Episode"
GIRL_RIG = "STU_Designer_Rig"     # already in studio.blend
CLAWD_RIG = "EP4_Clawd_Rig"       # created by anim_clawd on STU_Claude_Dock_Anchor
CHAIR = "STU_Chair"               # animated by anim_girl
CUP = "STU_Tea_Cup"               # the day cup; stage adds the evening ones

# ---------------------------------------------------------------- agreements between parts
# The evening frontal two-shot repeats the day one exactly: cameras 15, 27 and 25 share one pose.
LOCKED_FRONTAL_SHOTS = (15, 27, 25)
# Shot 27 is the "One Eternity Later" card. It is laid over the frame in post; Blender only needs a camera there.
CARD_SHOT = 27
# Where the camera stands in the shots where a character looks straight into the lens (world space, metres).
# anim_girl and anim_clawd aim the gaze here; cameras puts the camera of that shot exactly here (aim and lens are free).
LOOK_INTO_LENS = {
    24: (0.0, -0.55, 1.18),       # she looks into the lens: close-up from across the desk
    29: (-0.20, -0.78, 0.97),     # Clawd turns to the lens: on the line from his face to point 30, so no jump at 29/30
    30: (0.0, -2.75, 1.30),       # Clawd keeps looking at the lens in the closing wide (STU_Cam_Wide's spot)
}
# Shot 28: her fists hit the desk on these frames, counted from the shot's first frame.
# anim_girl lands the fists here; stage makes the cups jump and the papers fly on the same frames.
RAGE_HITS = (4, 16, 30)
# How far she turns the chair towards Clawd when she sits facing him (shots 15-16 and 25-19), degrees about Z.
# The value is a size, not a sign: Clawd stands at -X, so turning towards him is a NEGATIVE rotation about Z
# (a positive one turns her -Y gaze towards +X, away from him). anim_girl owns the chair; cameras frame her accordingly.
CHAIR_TOWARDS_CLAWD_DEG = 30.0

# Shot 16: after «Расскажу в двух словах» she gets up, walks to the board, takes a marker and starts drawing; Clawd
# says «Я внимательно слушаю» while she draws. Frames are counted from the shot's first frame.
# anim_girl: her body and hand, the marker tip follows marker_tip_16(). stage: the marker object rides in her hand
# from "pick" on, the lines appear behind the tip. anim_clawd: his head follows her from the chair to the board.
BOARD_SHOT = 16
BOARD_BEATS = dict(stand=(0, 14), walk=(14, 42), pick=(42, 50), draw=(52, 95))
BOARD_CENTRE = (1.17, 1.17, 1.28)       # the writing surface; stage.py places the board here
BOARD_YAW_DEG = -45.0                   # the surface faces the room along the corner's diagonal
# Floor point where she stands to draw, facing the board: near its left end (board x -0.42, 0.48 m out), so the drawing
# is to her right, in reach of her right hand, and the camera of 16 sees it past her head. anim_girl pushes the chair
# back and to the left as she gets up, so the way from the chair to here is free. (anim_girl, round 11)
BOARD_STAND_SPOT = (0.53, 1.13)
BOARD_MARKER = 1                        # the tray marker she takes: EP4_Board_Marker_<n>
# How the marker sits in her right fist, in the space of the pose bone hand.R (origin at the bone's head, the wrist;
# +Y along the bone towards the fingertips; the mitt ends at y 0.14). stage: from "pick" the marker is held exactly
# like this (Child Of hand.R). anim_girl: the tip point below, carried by hand.R, is the marker tip; it points along
# +Y, out of the end of the fist. Tip in world = rig.matrix_world @ pose_bones["hand.R"].matrix @ Vector(tip).
BOARD_MARKER_GRIP = dict(tip=(-0.02, 0.18, 0.0), axis=(0.0, 1.0, 0.0), length=0.11)
# What she draws, in order: polylines in board coordinates, metres from the surface's centre, x to the right and
# y up as one faces the board. The evening board (board_drawn.png) shows this drawing in the same place.
# Right of her stand spot, below her glasses (z 1.14-1.28), where her right arm reaches it without crossing her face;
# the arrow is short. Was y 0.0..0.14 with the arrow to x 0.27 (anim_girl, round 11).
BOARD_STROKES_16 = (
    ((-0.10, 0.0), (0.12, 0.0), (0.12, -0.14), (-0.10, -0.14), (-0.10, 0.0)),     # the banner, a box
    ((0.15, -0.07), (0.22, -0.07)),                                                # an arrow out of it
    ((0.19, -0.045), (0.22, -0.07), (0.19, -0.095)),                               # the arrow's head
)
BOARD_LIFT_FRAMES = 3                   # the marker leaves the board between two lines


def board_point(x, y, off=0.0):
    """World point of board coordinates (x, y); off metres out of the surface towards the room."""
    from mathutils import Matrix, Vector
    rot = Matrix.Rotation(__import__("math").radians(BOARD_YAW_DEG), 3, "Z")
    return Vector(BOARD_CENTRE) + rot @ Vector((x, -off, y))


def marker_tip_16(t):
    """Where the marker tip is at frame offset t into shot 16, while she draws: (x, y, touching).
    None before the drawing starts. The lines share the drawing time by length; between two lines the tip is
    lifted for BOARD_LIFT_FRAMES and travels to the next line's start. After the last line it stays at its end."""
    a, z = BOARD_BEATS["draw"]
    if t < a:
        return None
    lens = []
    for line in BOARD_STROKES_16:
        lens.append(sum(((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5 for p, q in zip(line, line[1:])))
    pen_time = (z - a) - BOARD_LIFT_FRAMES * (len(BOARD_STROKES_16) - 1)
    f = a
    for i, (line, length) in enumerate(zip(BOARD_STROKES_16, lens)):
        dur = pen_time * length / sum(lens)
        if t <= f + dur:
            d = length * (t - f) / dur
            for p, q in zip(line, line[1:]):
                seg = ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5
                if d <= seg:
                    k = d / seg if seg else 0.0
                    return (p[0] + (q[0] - p[0]) * k, p[1] + (q[1] - p[1]) * k, True)
                d -= seg
            return (line[-1][0], line[-1][1], True)
        f += dur
        if i + 1 < len(BOARD_STROKES_16):
            if t <= f + BOARD_LIFT_FRAMES:
                k = (t - f) / BOARD_LIFT_FRAMES
                p, q = line[-1], BOARD_STROKES_16[i + 1][0]
                return (p[0] + (q[0] - p[0]) * k, p[1] + (q[1] - p[1]) * k, False)
            f += BOARD_LIFT_FRAMES
    return (BOARD_STROKES_16[-1][-1][0], BOARD_STROKES_16[-1][-1][1], False)


def drawn_length_16(t):
    """How much of each line is on the board at frame offset t into shot 16: a list of 0..1 per line."""
    a, z = BOARD_BEATS["draw"]
    out = []
    lens = [sum(((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5 for p, q in zip(l, l[1:])) for l in BOARD_STROKES_16]
    pen_time = (z - a) - BOARD_LIFT_FRAMES * (len(BOARD_STROKES_16) - 1)
    f = a
    for length in lens:
        dur = pen_time * length / sum(lens)
        out.append(min(1.0, max(0.0, (t - f) / dur)))
        f += dur + BOARD_LIFT_FRAMES
    return out


def camera_name(shot_id):
    return f"EP4_Cam_{shot_id:02d}"


class Ctx:
    def __init__(self, scene=None):
        self.scene = scene or bpy.context.scene
        self.timeline = json.loads((EP / "timeline.json").read_text(encoding="utf-8"))
        self.fps = self.timeline["fps"]
        self.frame_start = self.timeline["frame_start"]
        self.frame_end = self.timeline["frame_end"]
        self.shots = self.timeline["shots"]

    def shot(self, shot_id):
        return next(s for s in self.shots if s["id"] == shot_id)

    def line(self, line_id):
        return next(l for s in self.shots for l in s["lines"] if l["id"] == line_id)

    def lines(self, who=None):
        return [l for s in self.shots for l in s["lines"] if who is None or l["who"] == who]

    def sfx(self, sfx_id):
        """A sound effect of the timeline: {"id", "file", "gain", "first_frame"}."""
        return next(f for s in self.shots for f in s.get("sfx", []) if f["id"] == sfx_id)

    def all_sfx(self):
        return [f for s in self.shots for f in s.get("sfx", [])]

    def audio_path(self, item):
        """Voice lines and effects: the path in the timeline is relative to the episode folder."""
        return (EP / item["file"]).resolve()

    def is_evening(self, shot_id):
        return self.shot(shot_id)["setting"] == "вечер"

    def collection(self, name):
        """EP4_<name> under the episode's root collection, created on first use."""
        root = bpy.data.collections.get(ROOT_COLLECTION)
        if root is None:
            root = bpy.data.collections.new(ROOT_COLLECTION)
            self.scene.collection.children.link(root)
        full = PREFIX + name
        col = bpy.data.collections.get(full)
        if col is None:
            col = bpy.data.collections.new(full)
            root.children.link(col)
        return col
