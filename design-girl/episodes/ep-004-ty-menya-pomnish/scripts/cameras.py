"""EP4 cameras: one camera per shot, EP4_Cam_NN, bound to a timeline marker on the shot's first frame.

Runs last, so it frames the poses the characters really have: for each shot it samples her head (and hands where they
matter) and Clawd over the shot's frames, places the camera by a simple rule per kind of shot, aims it at the middle
of what must be seen and picks the longest lens that keeps all of it inside the safe part of the 9:16 frame (the top
and bottom of a Reel are covered by its interface). Without the characters' animation it frames their rest poses;
without Clawd's rig it uses his dock.

  her close-ups   from the window side, beyond her line to Clawd: she looks screen right, he looks screen left
  his close-ups   from her side of the desk, turned towards the window so the camera stays clear of her hands
  16              through Clawd onto the board: he is in the foreground, she gets up, walks to the board in the corner
                  and draws in the depth. Static; the side angle is the one that keeps the board and her clear
  8               a steep high angle onto her face from his side: she looks down at him, deadpan "-_-". No focus pull
  15, 27, 25      one locked frontal two-shot, the same pose to the millimetre (ep4.LOCKED_FRONTAL_SHOTS), with the
                  whole board in the corner in the frame
  24, 29, 30      the camera stands exactly in ep4.LOOK_INTO_LENS
  1               the room from STU_Cam_Wide's spot, slow push in
"""
import math

import bpy
from mathutils import Matrix, Vector

import ep4

HEAD = "STU_Designer_Head"
HANDS = ("STU_Designer_Hand.L", "STU_Designer_Hand.R")
WIDE = "STU_Cam_Wide"
DOCK_ANCHOR = "STU_Claude_Dock_Anchor"
LAPTOP = "STU_Laptop"

SENSOR = 36.0                          # AUTO fit: the 36 mm side is the frame's height
HALF_H = SENSOR / 2
HALF_W = SENSOR / 2 * 9 / 16
LENS_RANGE = (14.0, 80.0)
SAMPLES = 5                            # frames sampled per shot to find where the characters are

# Her head in the head mesh's space (the mesh faces -Y). Face: between her eyes.
FACE_ON_HEAD = Vector((0.0, -0.242, 0.20))
HEAD_FRAME_POINTS = [Vector(p) for p in ((0, -0.06, 0.52), (0, -0.27, -0.03), (0.23, -0.12, 0.22),
                                          (-0.23, -0.12, 0.22))]
# Clawd in his rig's space (scale 0.18 in the rig object; the model is 0.75 tall, face on -Y).
CLAWD_CENTRE = Vector((0.0, 0.0, 0.42))
CLAWD_FACE = Vector((0.0, -0.2, 0.50))
CLAWD_FRAME_POINTS = [Vector(p) for p in ((0, 0, 0.0), (0, 0, 0.80), (0.6, 0, 0.4), (-0.6, 0, 0.4),
                                           (0, -0.22, 0.45), (0, 0.22, 0.45))]
CLAWD_HEIGHT_ON_DOCK = 0.076           # fallback without the rig: his centre above the dock anchor

HER_CU = dict(distance=0.92, rise=0.11, beyond_clawd_deg=25.0, safe=(0.95, 0.58))
HER_HANDS = dict(distance=1.12, rise=0.06, beyond_clawd_deg=22.0, safe=(0.92, 0.66))
CLAWD_CU = dict(distance=0.30, rise=0.04, side_deg=25.0, safe=(0.85, 0.55))
CLAWD_LOW = dict(distance=0.30, side_deg=30.0, height=0.755, safe=(0.85, 0.5))   # from the desk's surface
RAY_GRID = (7, 12)                     # rays across the frame that look for her between him and the lens
SIDE_STEP_DEG, SIDE_MAX_DEG = 5.0, 80.0
HIGH_8 = dict(distance=0.46, rise=0.36, towards_window_deg=12.0, safe=(0.9, 0.55))   # about 38 degrees above her face; she lifts her chin to him, so the face reads
BOARD = "EP4_Board"
BOARD_FRAME = "EP4_Board_Frame"
# shot 16: behind Clawd on the line from the board through him, swung round him by a side angle and raised (tried in
# order) until the lines she draws, her head on her way and the board are seen on the sampled frames. Her standing
# height is not known before anim_girl: the guess keeps room for it.
THROUGH_CLAWD_16 = dict(distance=0.52, heights=(1.04, 1.15, 1.25), sides=(16, 8, 24, 0, 32, 40), safe=(0.92, 0.6),
                        samples=9, standing_guess=(0.95, 1.75))
FRONTAL = dict(offset=Vector((0.03, -1.75, 0.0)), height=1.55, safe=(0.94, 0.62))
MEDIUM_28 = dict(offset=Vector((0.06, -1.65, 0.0)), height=1.42, safe=(0.94, 0.66))
SIDE_13 = dict(x_from_clawd=-0.62, y_shift=-0.10, height=1.07, safe=(0.94, 0.70))
WIDE_PUSH = 0.6                        # metres the opening shot travels
MOVE_KEY_STEP = 3


# ---------------------------------------------------------------- helpers
def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def fcurves_of(idb):
    ad = idb.animation_data
    if not ad or not ad.action:
        return []
    try:
        return list(ad.action.fcurves)
    except AttributeError:
        from bpy_extras import anim_utils
        bag = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
        return list(bag.fcurves) if bag else []


def set_interpolation(idb, kind):
    for fc in fcurves_of(idb):
        for kp in fc.keyframe_points:
            kp.interpolation = kind


def name_action(idb, name):
    if idb.animation_data and idb.animation_data.action:
        idb.animation_data.action.name = ep4.PREFIX + name


def horizontal(v):
    v = Vector((v.x, v.y, 0.0))
    return v.normalized() if v.length > 1e-6 else Vector((0.0, -1.0, 0.0))


def rot_z(v, degrees):
    return Matrix.Rotation(math.radians(degrees), 3, "Z") @ v


def look_rotation(loc, target):
    return (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_matrix()


def frame_points(loc, points, safe, lens=None):
    """Aims from loc at the middle of the points (in angle) and picks the longest lens that keeps every point inside
    the safe share of the frame. Returns (rotation matrix, lens)."""
    loc = Vector(loc)
    centre = sum(points, Vector()) / len(points)
    rot = look_rotation(loc, centre)
    for _ in range(4):
        inv = rot.transposed()
        local = [inv @ (p - loc) for p in points]
        tx = [v.x / -v.z for v in local if v.z < -1e-4]
        ty = [v.y / -v.z for v in local if v.z < -1e-4]
        mid = Vector(((max(tx) + min(tx)) / 2, (max(ty) + min(ty)) / 2, -1.0))
        rot = look_rotation(loc, loc + rot @ mid)
    inv = rot.transposed()
    local = [inv @ (p - loc) for p in points]
    span_x = max(abs(v.x / -v.z) for v in local if v.z < -1e-4)
    span_y = max(abs(v.y / -v.z) for v in local if v.z < -1e-4)
    fit = min(HALF_W * safe[0] / max(span_x, 1e-4), HALF_H * safe[1] / max(span_y, 1e-4))
    if lens is None:
        lens = max(LENS_RANGE[0], min(LENS_RANGE[1], fit))
    return rot, lens


# ---------------------------------------------------------------- where the characters are
class Poses:
    """Reads the evaluated poses of both characters on sampled frames of each shot."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.cache = {}

    def at(self, frame):
        if frame in self.cache:
            return self.cache[frame]
        sc = self.ctx.scene
        sc.frame_set(frame)
        dg = bpy.context.evaluated_depsgraph_get()
        head = bpy.data.objects[HEAD].evaluated_get(dg).matrix_world.copy()
        hands = [bpy.data.objects[n].evaluated_get(dg).matrix_world.translation.copy() for n in HANDS]
        rig = bpy.data.objects.get(ep4.CLAWD_RIG)
        face = head @ FACE_ON_HEAD
        if rig is not None:
            m = rig.evaluated_get(dg).matrix_world.copy()
            clawd = m @ CLAWD_CENTRE
            clawd_face = m @ CLAWD_FACE
            clawd_points = [m @ p for p in CLAWD_FRAME_POINTS]
            clawd_facing = horizontal(m.to_3x3() @ Vector((0, -1, 0)))
        else:                                       # no rig in this build: his size on the dock, facing her
            base = bpy.data.objects[DOCK_ANCHOR].matrix_world.translation.copy()
            clawd = base + Vector((0, 0, CLAWD_HEIGHT_ON_DOCK))
            clawd_facing = horizontal(face - clawd)
            side = Vector((-clawd_facing.y, clawd_facing.x, 0))
            clawd_face = clawd + clawd_facing * 0.036 + Vector((0, 0, 0.01))
            clawd_points = [base, base + Vector((0, 0, 0.145)), clawd + side * 0.11, clawd - side * 0.11,
                            clawd + clawd_facing * 0.04, clawd - clawd_facing * 0.04]
        pose = dict(face=face, head_points=[head @ p for p in HEAD_FRAME_POINTS], hands=hands,
                    clawd=clawd, clawd_face=clawd_face, clawd_points=clawd_points, clawd_facing=clawd_facing)
        self.cache[frame] = pose
        return pose

    def frames(self, shot_id, n=SAMPLES):
        s = self.ctx.shot(shot_id)
        a, b = s["first_frame"], s["last_frame"]
        return sorted({round(a + (b - a) * i / (n - 1)) for i in range(n)})

    def over(self, shot_id, key, n=SAMPLES):
        """All values of one pose key over the shot's samples (lists are flattened)."""
        out = []
        for f in self.frames(shot_id, n):
            v = self.at(f)[key]
            out += v if isinstance(v, list) else [v]
        return out

    def mean(self, shot_id, key):
        vals = self.over(shot_id, key)
        return sum(vals, Vector()) / len(vals)

    def last(self, shot_id, key):
        return self.at(self.ctx.shot(shot_id)["last_frame"])[key]


# ---------------------------------------------------------------- setups per kind of shot
def her_close_up(p, sid, spec, with_hands=False):
    face = p.mean(sid, "face")
    clawd = p.mean(sid, "clawd")
    to_clawd = horizontal(clawd - face)
    direction = rot_z(to_clawd, -spec["beyond_clawd_deg"])    # further round to the window side
    loc = face + direction * spec["distance"] + Vector((0, 0, spec["rise"]))
    points = p.over(sid, "head_points") + (p.over(sid, "hands") if with_hands else [])
    rot, lens = frame_points(loc, points, spec["safe"])
    return dict(loc=loc, rot=rot, lens=lens)


def her_in_front(ctx, loc, rot, lens, frames, depth):
    """True if, on any of the frames, a ray through the frame hits her before it reaches Clawd's depth."""
    sc = ctx.scene
    for f in frames:
        sc.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        for i in range(RAY_GRID[0]):
            for j in range(RAY_GRID[1]):
                tx = (2 * i / (RAY_GRID[0] - 1) - 1) * HALF_W / lens
                ty = (2 * j / (RAY_GRID[1] - 1) - 1) * HALF_H / lens
                direction = (rot @ Vector((tx, ty, -1.0))).normalized()
                hit, _, _, _, ob, _ = sc.ray_cast(dg, loc, direction, distance=depth)
                if hit and ob.name.startswith("STU_Designer"):
                    return True
    return False


def clawd_close_up_at(p, sid, side, spec, low):
    clawd = p.last(sid, "clawd")                   # where he is once any turn in the shot has settled
    facing = p.last(sid, "clawd_facing")
    loc = clawd + rot_z(facing, side) * spec["distance"]
    loc.z = spec["height"] if low else clawd.z + spec["rise"]
    rot, lens = frame_points(loc, p.over(sid, "clawd_points"), spec["safe"])
    return dict(loc=loc, rot=rot, lens=lens)


def clawd_close_ups(p, ctx, shots, spec=CLAWD_CU, low=False, also_seen_in=None):
    """In front of his face, turned towards the window side, and further round while her arms or head would come
    between him and the lens. One angle for the whole group, so his close-ups in a scene match.
    also_seen_in: {shot: other shot that reuses its camera}, whose frames are checked as well."""
    also_seen_in = also_seen_in or {}
    side = spec["side_deg"]
    while side < SIDE_MAX_DEG:
        blocked = False
        for sid in shots:
            setup = clawd_close_up_at(p, sid, side, spec, low)
            frames = p.frames(sid) + (p.frames(also_seen_in[sid]) if sid in also_seen_in else [])
            depth = (p.last(sid, "clawd") - setup["loc"]).length
            if her_in_front(ctx, setup["loc"], setup["rot"], setup["lens"], frames, depth):
                blocked = True
                break
        if not blocked:
            break
        side += SIDE_STEP_DEG
    print("cameras: Clawd close-ups %s at %.0f degrees off his facing" % (list(shots), side))
    return {sid: clawd_close_up_at(p, sid, side, spec, low) for sid in shots}


def fixed_point_close_up(p, sid, key, safe):
    loc = Vector(ep4.LOOK_INTO_LENS[sid])
    rot, lens = frame_points(loc, p.over(sid, key), safe)
    return dict(loc=loc, rot=rot, lens=lens)


def desk_front_points(half_width=0.62):
    return [Vector((x, -0.36, 0.72)) for x in (-half_width, half_width)]


def board_points():
    """The corners of the board's frame and the tops of its stand, if the stage part has built it."""
    board = bpy.data.objects.get(BOARD)
    if board is None:
        return []
    pts = []
    for ob in [board] + list(board.children):
        pts += [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    xs = sorted(pts, key=lambda v: v.x)
    top = max(v.z for v in pts)
    return [xs[0], xs[-1], max(pts, key=lambda v: v.z), Vector((xs[0].x, xs[0].y, top)), Vector((xs[-1].x, xs[-1].y, top))]


def board_surface_points(nx=7, ny=5):
    board = bpy.data.objects.get(BOARD)
    if board is None:
        return []
    xs = [v.co.x for v in board.data.vertices]
    zs = [v.co.z for v in board.data.vertices]
    at = lambda lo, hi, k, n: lo + (hi - lo) * (0.05 + 0.9 * k / (n - 1))     # inset: the frame's lip is proud
    return [board.matrix_world @ Vector((at(min(xs), max(xs), i, nx), 0.0, at(min(zs), max(zs), j, ny)))
            for i in range(nx) for j in range(ny)]


def frame_corners(name):
    ob = bpy.data.objects.get(name)
    return [ob.matrix_world @ Vector(c) for c in ob.bound_box] if ob else []


def stroke_points(step=0.02):
    out = []
    for line in ep4.BOARD_STROKES_16:
        for a, b in zip(line, line[1:]):
            n = max(1, round(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 / step))
            out += [ep4.board_point(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n)]
    return out


def seen_shares(ctx, loc, frames, draw_frames, p):
    """(lines, her face, board): shares of sample points a ray from loc reaches unblocked. The lines on the frames
    she draws, her face on all sampled frames, the board once she has left the chair (until then her head in the
    chair is in front of it, as it should be)."""
    sc = ctx.scene
    board_pts, lines = board_surface_points(), stroke_points()
    counts = {"lines": [0, 0], "face": [0, 0], "board": [0, 0]}

    def clear(dg, q, key):
        d = q - loc
        hit, *_ = sc.ray_cast(dg, loc, d.normalized(), distance=d.length - 0.01)
        counts[key][0] += not hit
        counts[key][1] += 1

    for f in sorted(set(frames) | set(draw_frames)):
        sc.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        if f in draw_frames:
            for q in lines:
                clear(dg, q, "lines")
        if f in frames:
            if f >= draw_frames[0] - (ep4.BOARD_BEATS["draw"][0] - ep4.BOARD_BEATS["walk"][1]):
                for q in board_pts:
                    clear(dg, q, "board")
            q = p.at(f)["face"]
            d = q - loc
            hit, _, _, _, ob, _ = sc.ray_cast(dg, loc, d.normalized(), distance=d.length + 0.05)
            counts["face"][0] += bool(hit and ob.name.startswith("STU_Designer"))
            counts["face"][1] += 1
    return tuple(counts[k][0] / max(1, counts[k][1]) for k in ("lines", "face", "board"))


def through_clawd_16(p, ctx):
    """Behind Clawd, looking past him at the board; framed on him, her head on the way and at the board, the board."""
    spec = THROUGH_CLAWD_16
    sid = ep4.BOARD_SHOT
    frames = p.frames(sid, spec["samples"])
    clawd = p.at(frames[0])["clawd"]
    centre = Vector(ep4.BOARD_CENTRE)
    back = horizontal(clawd - centre)
    spot = Vector((*ep4.BOARD_STAND_SPOT, 0.0))
    guess = [Vector((spot.x, spot.y, z)) for z in spec["standing_guess"]]
    points = (p.over(sid, "clawd_points", spec["samples"]) + p.over(sid, "head_points", spec["samples"]) + guess
              + frame_corners(BOARD_FRAME))
    first = ctx.shot(sid)["first_frame"]
    a, z = ep4.BOARD_BEATS["draw"]
    draw_frames = [first + t for t in range(a + 8, z + 1, 8)] + [first + z]
    best = None
    for side in spec["sides"]:
        for height in spec["heights"]:
            loc = clawd + rot_z(back, side) * spec["distance"]
            loc.z = height
            shares = seen_shares(ctx, loc, frames, draw_frames, p)
            score = 2 * shares[0] + shares[1] + shares[2]          # the lines she draws matter most
            if best is None or score > best[0] + 1e-9:
                best = (score, shares, side, loc)
            if min(shares) >= 0.999:
                break
        if best[1] and min(best[1]) >= 0.999:
            break
    _, shares, side, loc = best
    rot, lens = frame_points(loc, points, spec["safe"])
    print("cameras: 16 through Clawd at %+.0f degrees, height %.2f; seen: lines %.0f%%, her face %.0f%%, board %.0f%%;"
          " lens %.1f" % (side, loc.z, 100 * shares[0], 100 * shares[1], 100 * shares[2], lens))
    return dict(loc=loc, rot=rot, lens=lens)


def locked_frontal(p, ctx):
    """One pose for 15, 27 and 25: framed on her at the end of 15 (turned to Clawd) and in 25 (slumped), Clawd,
    and the front of the desk, so the cups and the sheets of the evening are in the frame."""
    s15, s25 = ctx.shot(15), ctx.shot(25)
    frames = [s15["last_frame"], (s25["first_frame"] + s25["last_frame"]) // 2, s25["last_frame"]]
    poses = [p.at(f) for f in frames]
    head_points = [q for pose in poses for q in pose["head_points"]]
    clawd_points = [q for pose in poses for q in pose["clawd_points"]]
    face = sum((pose["face"] for pose in poses), Vector()) / len(poses)
    clawd = sum((pose["clawd"] for pose in poses), Vector()) / len(poses)
    middle = (face + clawd) / 2
    loc = Vector((middle.x, middle.y, 0)) + FRONTAL["offset"]
    loc.z = FRONTAL["height"]
    points = head_points + clawd_points + desk_front_points() + board_points()
    rot, lens = frame_points(loc, points, FRONTAL["safe"])
    return dict(loc=loc, rot=rot, lens=lens)


def medium_28(p, ctx):
    sid = 28
    face = p.mean(sid, "face")
    clawd = p.mean(sid, "clawd")
    middle = (face + clawd) / 2
    loc = Vector((middle.x, middle.y, 0)) + MEDIUM_28["offset"]
    loc.z = MEDIUM_28["height"]
    cups = [bpy.data.objects[ep4.CUP].matrix_world.translation.copy()]
    cups += [ob.matrix_world.translation.copy() for ob in bpy.data.objects if ob.name.startswith(ep4.PREFIX + "Cup_")]
    points = (p.over(sid, "head_points", 9) + p.over(sid, "hands", 9) + p.over(sid, "clawd_points")
              + cups + desk_front_points(0.55))
    rot, lens = frame_points(loc, points, MEDIUM_28["safe"])
    return dict(loc=loc, rot=rot, lens=lens)


def side_13(p, ctx):
    sid = 13
    clawd = p.mean(sid, "clawd")
    face = p.mean(sid, "face")
    laptop = bpy.data.objects[LAPTOP]
    lid = [laptop.matrix_world @ Vector(c) for c in laptop.bound_box]
    loc = Vector((clawd.x + SIDE_13["x_from_clawd"], (clawd.y + face.y) / 2 + SIDE_13["y_shift"], SIDE_13["height"]))
    points = p.over(sid, "clawd_points") + [max(lid, key=lambda v: v.z), min(lid, key=lambda v: v.y)]
    points += [face] + p.over(sid, "hands")        # her face and pointing hand, not her whole head: "partly her"
    rot, lens = frame_points(loc, points, SIDE_13["safe"])
    return dict(loc=loc, rot=rot, lens=lens)


def high_on_her_8(p, ctx):
    """Steep from above, in front of her face on his side of her, a little round to the window."""
    sid = 8
    face = p.mean(sid, "face")
    clawd = p.mean(sid, "clawd")
    direction = rot_z(horizontal(clawd - face), -HIGH_8["towards_window_deg"])
    loc = face + direction * HIGH_8["distance"] + Vector((0, 0, HIGH_8["rise"]))
    rot, lens = frame_points(loc, p.over(sid, "head_points"), HIGH_8["safe"])
    return dict(loc=loc, rot=rot, lens=lens)


def wide(ctx, p):
    cam = bpy.data.objects[WIDE]
    return dict(loc=cam.matrix_world.translation.copy(), rot=cam.matrix_world.to_3x3().normalized(), lens=cam.data.lens)


def shot_setups(ctx, p):
    setups = {}
    for sid in (2, 4, 6, 9, 18):
        setups[sid] = her_close_up(p, sid, HER_CU)
    for sid in (20, 22):
        setups[sid] = her_close_up(p, sid, HER_HANDS, with_hands=True)
    setups.update(clawd_close_ups(p, ctx, (5, 7, 10)))
    setups[16] = through_clawd_16(p, ctx)
    setups.update(clawd_close_ups(p, ctx, (19, 21), also_seen_in={21: 23}))
    setups[23] = dict(setups[21])                  # the same frame as 21
    setups.update(clawd_close_ups(p, ctx, (14,), CLAWD_LOW, low=True))
    setups[13] = side_13(p, ctx)
    setups[8] = high_on_her_8(p, ctx)
    frontal = locked_frontal(p, ctx)
    for sid in ep4.LOCKED_FRONTAL_SHOTS:
        setups[sid] = dict(frontal)
    setups[28] = medium_28(p, ctx)
    setups[24] = fixed_point_close_up(p, 24, "head_points", HER_CU["safe"])
    setups[29] = fixed_point_close_up(p, 29, "clawd_points", (0.8, 0.5))
    w = wide(ctx, p)
    setups[30] = dict(w, loc=Vector(ep4.LOOK_INTO_LENS[30]))
    end = w["loc"] + (w["rot"] @ Vector((0, 0, -1))) * WIDE_PUSH
    setups[1] = dict(w, to_loc=end)
    return setups


# ---------------------------------------------------------------- building
def make_camera(ctx, sid, setup, clip_end):
    name = ep4.camera_name(sid)
    data = bpy.data.cameras.new(name)
    data.lens = setup["lens"]
    data.sensor_fit = "AUTO"
    data.sensor_width = SENSOR
    data.clip_start = 0.01
    data.clip_end = clip_end
    ob = bpy.data.objects.new(name, data)
    ctx.collection("Cameras").objects.link(ob)
    ob.rotation_mode = "XYZ"
    ob.location = setup["loc"]
    ob.rotation_euler = setup["rot"].to_euler("XYZ")
    return ob


def key_push(ob, shot, setup):
    a, b = shot["first_frame"], shot["last_frame"]
    frames = list(range(a, b + 1, MOVE_KEY_STEP))
    if frames[-1] != b:
        frames.append(b)
    for f in frames:
        ob.location = setup["loc"].lerp(setup["to_loc"], ease((f - a) / max(1, b - a)))
        ob.keyframe_insert("location", frame=f)
    set_interpolation(ob, "LINEAR")
    name_action(ob, ob.name[len(ep4.PREFIX):] + "_push")


def build(ctx):
    sc = ctx.scene
    p = Poses(ctx)
    setups = shot_setups(ctx, p)
    clip_end = bpy.data.objects[WIDE].data.clip_end
    cameras = {}
    for shot in ctx.shots:
        sid = shot["id"]
        setup = setups[sid]
        ob = make_camera(ctx, sid, setup, clip_end)
        cameras[sid] = ob
        if "to_loc" in setup:
            key_push(ob, shot, setup)
        marker = sc.timeline_markers.new("%sS%02d" % (ep4.PREFIX, sid), frame=shot["first_frame"])
        marker.camera = ob
    bpy.context.view_layer.update()
    sc.camera = cameras[ctx.shots[0]["id"]]
    sc.frame_set(ctx.frame_start)
    return cameras
