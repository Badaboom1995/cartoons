"""EP4 Clawd: appended from clawd.blend, on the dock, calm and kind, with a block face. All frames come from the timeline.

  turns   yaw of the rig, held exactly between moves (yaw_keys): the laptop, then her, a small follow when she turns
          her chair to him (15) and back (20), into the lens in 29, and a step on the 29/30 cut to the lens of 30.
          Shot 16: as she gets up he follows her from the chair to ep4.BOARD_STAND_SPOT and is looking at the board when
          she starts to draw; a small nod on his line; on the cut to 27 he is back on her in her chair
  pitch   the body bone: nods in 19 and under her line in 25, and the tilt that points his face into the lens in 29-30
  face    pixel_face.py: eyes per beat (eye_beats), blinks, a short flat mouth with lip sync from the wav. No smiles.
          Shot 23 opens with a two-frame "reboot" of the eyes
  speech  a tiny squash and a faint warm glow, driven by the same wav envelope, only inside the frames of his lines
  breath  a very slow, barely visible rise and fall, so the long holds stay alive
  still   in shot 28, while she hits the desk, nothing on him moves or changes, not even the breath or a blink
"""
import math
import sys

import bpy
from mathutils import Matrix, Vector

import ep4

_FACE_SCRIPTS = str(ep4.CHARACTER / "scene" / "characters" / "clawd" / "scripts")
if _FACE_SCRIPTS not in sys.path:
    sys.path.insert(0, _FACE_SCRIPTS)
import pixel_face  # noqa: E402
from pixel_face import fcurves_of, read_envelope  # noqa: E402

CLAWD_SCALE = 0.18
ANCHOR = "STU_Claude_Dock_Anchor"
SOURCE_COLLECTION = "MSC_Character"
LAPTOP_SCREEN = "STU_Screen_Laptop"
HEAD_BONE = "head"

SPEECH_SQUASH = 0.016     # body height change at full voice
SPEECH_GLOW = 0.18        # emission strength at full voice
SPEECH_TAPER = 3          # the last frames of a line fade the speech out, so it is zero on the frame after the line
NOD_DEGREES = 8.0         # "Теперь помню."
LISTEN_NOD_DEGREES = 3.5  # under her line in shot 25
NOD_DOWN_FRAMES = 5
NOD_FRAMES = 13           # a nod lasts more than half a second
TURN_FRAMES = 14          # a calm turn
TO_HER_FRAMES = 18        # end of shot 2: from the laptop to her, a wider turn
FOLLOW_FRAMES = 17        # he follows her chair in 15 and 20: 0.7 s, so it reads
FOLLOW_DELAY_15 = 6       # frames after the cut into 15: her chair turn starts on the cut, he follows a beat later
FOLLOW_DELAY_20 = 8       # frames after the cut into 20: she turns back to the laptop during her line
FOLLOW_MIN_DEGREES = 4.0  # the follow must read, even if her head hardly moves as the chair turns under her
LENS_TURN_FRAMES = 17     # shot 29: into the lens in 0.7 s, done on the first word of the line
BOARD_FOLLOW_16 = dict(start=2, up=14, walk=28, spot=42, board=52)   # frames into shot 16 (ep4.BOARD_BEATS)
BOARD_NOD_DELAY = 2       # frames after the start of v11 «Я внимательно слушаю»
SETTLE_BEFORE_CUT = 3     # a move ends this many frames before the cut
BLINK_FRAMES = 4
BLINK_MIN_GAP = 18
IDLE_BLINK_START = 20     # frames into a shot
IDLE_BLINK_GAPS = (52, 38, 64)   # uneven, so the blinks do not tick
IDLE_BLINK_MIN_SHOT = 30
REBOOT = (("blink", 2), ("wide", 2))   # shot 23 opens with these eyes, then the friendly look
BREATH = 0.004            # body height change at the top of a breath
BREATH_FRAMES = 96
BREATH_FADE = 24          # frames for the breath to settle before shot 28 and return after it

# Shots he is on camera in, for the idle blinks. 7, 8 and 28 hold dead still, 27 is under the card.
ON_CAMERA = (1, 5, 10, 13, 14, 15, 16, 25, 19, 21, 23, 29, 30)
NO_BLINK_SHOTS = (7, 8, 28)


def first(item):
    return item["first_frame"]


def last(item):
    return item["last_frame"]


def name_action(idb, name):
    idb.animation_data.action.name = ep4.PREFIX + name


def set_interpolation(idb, data_path, kind):
    for fc in fcurves_of(idb):
        if data_path in fc.data_path:
            for kp in fc.keyframe_points:
                kp.interpolation = kind


# ---------------------------------------------------------------- model
def append_clawd(ctx):
    with bpy.data.libraries.load(str(ep4.CLAWD_BLEND), link=False) as (src, dst):
        dst.collections = [SOURCE_COLLECTION]
    source = dst.collections[0]
    parts = list(source.objects)
    target = ctx.collection("Clawd")
    for ob in parts:
        target.objects.link(ob)
    bpy.data.collections.remove(source)

    rig = next(o for o in parts if o.type == "ARMATURE")
    old_eyes = [o for o in parts if "expression" in o.keys()]
    for ob in parts:
        short = ob.name.removeprefix("MSC_")
        ob.name = ep4.CLAWD_RIG if ob is rig else f"{ep4.PREFIX}Clawd_{short}"
        ob.data.name = ob.name
    glow = []
    for mat in {s.material for o in parts for s in o.material_slots if s.material}:
        is_eye = mat.name.endswith("_eye")
        mat.name = f"{ep4.PREFIX}Clawd_{mat.name.removeprefix('MSC_')}"
        if not is_eye:
            bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
            bsdf.inputs["Emission Color"].default_value = bsdf.inputs["Base Color"].default_value
            bsdf.inputs["Emission Strength"].default_value = 0.0
            glow.append((mat, bsdf.inputs["Emission Strength"]))

    rig.parent = bpy.data.objects[ANCHOR]
    rig.matrix_parent_inverse = Matrix.Identity(4)
    rig.matrix_basis = Matrix.Diagonal((CLAWD_SCALE, CLAWD_SCALE, CLAWD_SCALE, 1))
    rig.rotation_mode = "XYZ"
    rig.hide_render = True
    for pb in rig.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    face = pixel_face.build(rig, old_eyes, target, f"{ep4.PREFIX}Clawd_")
    return rig, face, glow


# ---------------------------------------------------------------- voice
def line_envelope(ctx, line):
    env = read_envelope(ctx.audio_path(line), last(line) - first(line) + 1, ctx.fps)
    n = min(SPEECH_TAPER, len(env))
    for k in range(n):                      # last frame * 1/4, the one before * 2/4, ...
        env[len(env) - 1 - k] *= (k + 1) / (SPEECH_TAPER + 1)
    return env


def speech_curve(ctx):
    """{frame: 0..1} over all of Clawd's lines. Zero outside the frames of his lines."""
    curve = {}
    for line in ctx.lines("claude"):
        for i, v in enumerate(line_envelope(ctx, line)):
            curve[first(line) + i] = max(curve.get(first(line) + i, 0.0), v)
    return {f: v for f, v in curve.items() if v > 0.01 and ctx.frame_start <= f <= ctx.frame_end}


def last_syllable_frame(ctx, line):
    """Where the last syllable starts: the last sharp rise of the voice."""
    env = read_envelope(ctx.audio_path(line), last(line) - first(line) + 1, ctx.fps)
    rises = [i for i in range(1, len(env)) if env[i] - env[i - 1] > 0.25]
    return first(line) + (rises[-1] if rises else int(0.7 * len(env)))


def still_window(ctx):
    """(first, last) frame in which nothing on him changes: shot 28, while she hits the desk and screams."""
    s = ctx.shot(28)
    return first(s), last(s)


def breath(ctx, frame):
    """Slow squash offset. It eases to exactly zero for the still window and eases back in after it."""
    a, b = still_window(ctx)
    if a <= frame <= b:
        return 0.0
    w = min(1.0, (a - frame if frame < a else frame - b) / BREATH_FADE)
    return BREATH * w * w * (3 - 2 * w) * math.sin(2 * math.pi * (frame - b) / BREATH_FRAMES)


def key_speech(ctx, rig, glow):
    curve = speech_curve(ctx)
    for f in range(ctx.frame_start, ctx.frame_end + 1):
        sq = SPEECH_SQUASH * curve.get(f, 0.0) + breath(ctx, f)
        wide = CLAWD_SCALE * (1 + 0.5 * sq)
        rig.scale = (wide, wide, CLAWD_SCALE * (1 - sq))
        rig.keyframe_insert("scale", frame=f)
    frames = set(curve)
    frames |= {f - 1 for f in curve if f - 1 not in curve} | {f + 1 for f in curve if f + 1 not in curve}
    frames = sorted(f for f in frames | {ctx.frame_start} if ctx.frame_start <= f <= ctx.frame_end)
    for f in frames:
        v = curve.get(f, 0.0)
        for _, strength in glow:
            strength.default_value = SPEECH_GLOW * v
            strength.keyframe_insert("default_value", frame=f)
    rig.scale = (CLAWD_SCALE, CLAWD_SCALE, CLAWD_SCALE)
    set_interpolation(rig, "scale", "LINEAR")
    for mat, strength in glow:
        strength.default_value = 0.0
        set_interpolation(mat.node_tree, "default_value", "LINEAR")
        name_action(mat.node_tree, mat.name.removeprefix(ep4.PREFIX) + "_glow")


# ---------------------------------------------------------------- where he looks
def pitch_basis(rig, degrees):
    """Pose-space basis for the body bone leaning forward (face down) around its base. Negative looks up."""
    rest = rig.data.bones["body"].matrix_local
    m = (Matrix.Rotation(math.radians(degrees), 3, "X") @ rest.to_3x3()).to_4x4()
    m.translation = rest.translation
    return rest.inverted() @ m


def face_ray(face):
    """World point between his eyes and the direction his face points (the pixel face's front normal, local -Y)."""
    ob = face.eyes["neutral"]
    mw = ob.matrix_world
    centre = mw @ Vector((0.0, pixel_face.FACE_Y, pixel_face.EYE_TOP - 2 * pixel_face.PIXEL))
    normal = (mw.to_3x3() @ Vector((0.0, -1.0, 0.0))).normalized()
    return centre, normal


def pose(rig, yaw, pitch):
    rig.rotation_euler = (0.0, 0.0, math.radians(yaw))
    pb = rig.pose.bones["body"]
    pb.rotation_mode = "QUATERNION"
    pb.rotation_quaternion = pitch_basis(rig, pitch).to_quaternion()
    bpy.context.view_layer.update()


def aim(rig, face, anchor, point, yaw_ref):
    """(yaw, pitch) in degrees that point his face straight at a world point. Solved on the real rig, before any keys."""
    point = Vector(point)
    anchor_yaw = math.degrees(anchor.matrix_world.to_euler().z)
    yaw, pitch = yaw_ref, 0.0
    for _ in range(8):
        pose(rig, yaw, pitch)
        centre, normal = face_ray(face)
        d = point - centre
        yaw = nearest(math.degrees(math.atan2(d.x, -d.y)) - anchor_yaw, yaw_ref)
        want = math.degrees(math.atan2(d.z, math.hypot(d.x, d.y)))
        have = math.degrees(math.atan2(normal.z, math.hypot(normal.x, normal.y)))
        pitch -= want - have
    pose(rig, 0.0, 0.0)
    return yaw, pitch


def yaw_to(anchor, xy):
    """Rig yaw (degrees, in the anchor's space) that points his face, -Y at rest, at a world point, level."""
    p = anchor.matrix_world.translation
    world = math.degrees(math.atan2(xy[0] - p.x, -(xy[1] - p.y)))
    return world - math.degrees(anchor.matrix_world.to_euler().z)


def nearest(angle, ref):
    while angle - ref > 180:
        angle -= 360
    while angle - ref < -180:
        angle += 360
    return angle


def her_head():
    """Her head at rest, and where it goes when her chair turns towards him by the agreed angle."""
    rig = bpy.data.objects[ep4.GIRL_RIG]
    head = rig.matrix_world @ rig.pose.bones[HEAD_BONE].head
    pivot = bpy.data.objects[ep4.CHAIR].matrix_world.translation
    turn = Matrix.Rotation(math.radians(-ep4.CHAIR_TOWARDS_CLAWD_DEG), 3, "Z")   # towards him is negative about Z
    turned = pivot + turn @ (head - pivot)
    return head, turned


def her_standing_rise():
    """How much higher her head is once she stands: legs straight under the hips, the soles on the floor."""
    rig = bpy.data.objects[ep4.GIRL_RIG]
    bones = rig.data.bones
    leg = bones["thigh.R"].length + bones["shin.R"].length
    foot = bpy.data.objects.get("STU_Designer_Foot.R") or bpy.data.objects["STU_Designer_Foot.L"]
    sole = min((foot.matrix_world @ Vector(c)).z for c in foot.bound_box)
    ankle = (rig.matrix_world @ bones["foot.R"].head_local).z - sole
    hip = (rig.matrix_world @ bones["thigh.R"].head_local).z
    return max(0.0, leg + ankle - hip)


def board_drawing_centre():
    xs = [x for line in ep4.BOARD_STROKES_16 for x, _ in line]
    ys = [y for line in ep4.BOARD_STROKES_16 for _, y in line]
    return ep4.board_point((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)


# ---------------------------------------------------------------- turns and tilts
def windows(ctx):
    """Every move as (start, end) frames."""
    s2, s15, s16, s20, s29 = (ctx.shot(i) for i in (2, 15, ep4.BOARD_SHOT, 20, 29))
    to_her = last(s2) - SETTLE_BEFORE_CUT
    b = BOARD_FOLLOW_16
    return {
        "follow_16": (first(s16) + b["start"], first(s16) + b["board"]),   # from her chair to the board
        "to_her_2": (to_her - TO_HER_FRAMES, to_her),           # she turns her eyes to him at the end of v01
        "follow_15": (first(s15) + FOLLOW_DELAY_15, first(s15) + FOLLOW_DELAY_15 + FOLLOW_FRAMES),
        "follow_20": (first(s20) + FOLLOW_DELAY_20, first(s20) + FOLLOW_DELAY_20 + FOLLOW_FRAMES),
        "to_lens_29": (first(s29), first(s29) + LENS_TURN_FRAMES),
    }


def targets(ctx, rig, face, anchor):
    """(yaw, pitch) of each thing he looks at."""
    screen = bpy.data.objects[LAPTOP_SCREEN].matrix_world.translation
    laptop = yaw_to(anchor, screen)
    head, turned = her_head()
    her = nearest(yaw_to(anchor, head), laptop)
    follow = nearest(yaw_to(anchor, turned), her) - her
    if abs(follow) < FOLLOW_MIN_DEGREES:
        follow = math.copysign(FOLLOW_MIN_DEGREES, follow if follow else 1.0)
    lens_29 = aim(rig, face, anchor, ep4.LOOK_INTO_LENS[29], nearest(0.0, her))
    lens_30 = aim(rig, face, anchor, ep4.LOOK_INTO_LENS[30], lens_29[0])
    # shot 16: her head rises over the chair, crosses the room, stands at the spot; then the drawing on the board
    up = Vector((0.0, 0.0, her_standing_rise()))
    spot = Vector((*ep4.BOARD_STAND_SPOT, turned.z)) + up
    her_up = aim(rig, face, anchor, turned + up, her + follow)
    walk = aim(rig, face, anchor, (turned + up + spot) / 2, her_up[0])
    at_spot = aim(rig, face, anchor, spot, walk[0])
    board = aim(rig, face, anchor, board_drawing_centre(), at_spot[0])
    return {
        "laptop": (laptop, 0.0),
        "her": (her, 0.0),
        "her_turned": (her + follow, 0.0),
        "lens_29": lens_29,
        "lens_30": lens_30,
        "her_up_16": her_up,
        "walk_16": walk,
        "spot_16": at_spot,
        "board_16": board,
    }


def nods(ctx, t):
    """(start, degrees, base pitch). The 25 nod is lowest on the last word of her line; 19 nods from the cut on
    «Теперь помню»; in 16 a small one on «Я внимательно слушаю», from his look at the board."""
    v12 = ctx.line("v12")
    low_25 = min(last_syllable_frame(ctx, v12), last(v12) - (NOD_FRAMES - NOD_DOWN_FRAMES))
    v11 = next(l for l in ctx.shot(ep4.BOARD_SHOT)["lines"] if l["who"] == "claude")
    return [
        (low_25 - NOD_DOWN_FRAMES, LISTEN_NOD_DEGREES, 0.0),
        (first(ctx.shot(19)), NOD_DEGREES, 0.0),
        (first(v11) + BOARD_NOD_DELAY, LISTEN_NOD_DEGREES, t["board_16"][1]),
    ]


def look_keys(ctx, t):
    """[(frame, yaw, pitch)] plus the frames whose key steps (constant) into the next one: the 29/30 cut."""
    w = windows(ctx)
    cut_30 = first(ctx.shot(30))
    s16 = first(ctx.shot(ep4.BOARD_SHOT))
    cut_27 = last(ctx.shot(ep4.BOARD_SHOT)) + 1        # the evening: she sits in her chair again
    b = BOARD_FOLLOW_16
    seq = [
        (ctx.frame_start, "laptop"),
        (w["to_her_2"][0], "laptop"), (w["to_her_2"][1], "her"),
        (w["follow_15"][0], "her"), (w["follow_15"][1], "her_turned"),
        (s16 + b["start"], "her_turned"), (s16 + b["up"], "her_up_16"), (s16 + b["walk"], "walk_16"),
        (s16 + b["spot"], "spot_16"), (s16 + b["board"], "board_16"), (cut_27 - 1, "board_16"), (cut_27, "her_turned"),
        (w["follow_20"][0], "her_turned"), (w["follow_20"][1], "her"),
        (w["to_lens_29"][0], "her"), (w["to_lens_29"][1], "lens_29"),
        (cut_30 - 1, "lens_29"), (cut_30, "lens_30"),
        (ctx.frame_end, "lens_30"),
    ]
    return [(f, *t[name]) for f, name in seq], {cut_27 - 1, cut_30 - 1}


def key_look(ctx, rig, t):
    keys, steps = look_keys(ctx, t)
    nod_list = nods(ctx, t)
    pb = rig.pose.bones["body"]
    pb.rotation_mode = "QUATERNION"
    pitch_keys = {f: p for f, _, p in keys}
    nod_frames = set()
    for start, degrees, base in nod_list:
        for f, d in ((start, base), (start + NOD_DOWN_FRAMES, base + degrees), (start + NOD_FRAMES, base)):
            pitch_keys[f] = d
            nod_frames.add(f)
    for f, yaw, _ in keys:
        rig.rotation_euler = (0.0, 0.0, math.radians(yaw))
        rig.keyframe_insert("rotation_euler", index=2, frame=f)
    for f, deg in sorted(pitch_keys.items()):
        pb.rotation_quaternion = pitch_basis(rig, deg).to_quaternion()
        pb.keyframe_insert("rotation_quaternion", frame=f)
    for fc in fcurves_of(rig):
        if fc.data_path == "rotation_euler" or "rotation_quaternion" in fc.data_path:
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT" if int(round(kp.co.x)) in steps else "BEZIER"
                kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"
            fc.update()
    rig.rotation_euler = (0.0, 0.0, 0.0)
    pb.rotation_quaternion = (1, 0, 0, 0)


# ---------------------------------------------------------------- face
def eye_beats(ctx):
    """(frame, eyes), in order. His mouth stays flat, so all the warmth is here."""
    shot = lambda i: first(ctx.shot(i))
    w = windows(ctx)
    reboot_end = shot(23) + sum(n for _, n in REBOOT)
    beats = [
        (ctx.frame_start, "neutral"),
        (w["to_her_2"][1], "attentive"),     # he has turned to her as she retells the letter
        (shot(5), "neutral"),                # v03, a plain status
                                             # 7, 8, 14: the same flat face on every blow
        (shot(10), "happy"),                 # v07 "Уверен, это были наши лучшие месяцы", friendly
        (shot(13), "neutral"),
        (w["follow_15"][0], "attentive"),    # she sits facing him; v11 "Я внимательно слушаю"
                                             # 27, 25, 18: he has listened all day with the same look
        (shot(19), "soft"),                  # v14 "Теперь помню. Спасибо, это было важно.", warm
        (shot(20), "neutral"),               # 21, 28: flat
    ]
    f = shot(23)
    for eye, n in REBOOT:                    # the screen comes back up: a line, a full block, then the welcome
        beats.append((f, eye))
        f += n
    beats += [
        (reboot_end, "happy"),               # v21 "Здравствуйте! Чем могу помочь?", a little brighter than usual
        (shot(24), "neutral"),               # off camera
        (w["to_lens_29"][1], "happy"),       # to the viewer, warm and businesslike
        (shot(30), "soft"),
    ]
    return beats


def blink_frames(ctx):
    """Mid-turn blinks first, then idle blinks in the longer shots. None in 7, 8, 28 or over the shot 23 reboot."""
    w = windows(ctx)
    wanted = [(a + b) // 2 - BLINK_FRAMES // 2 for a, b in w.values()]
    for shot_id in ON_CAMERA:
        s = ctx.shot(shot_id)
        if last(s) - first(s) + 1 >= IDLE_BLINK_MIN_SHOT:
            f, i = first(s) + IDLE_BLINK_START, shot_id
            while f < last(s) - BLINK_FRAMES - SETTLE_BEFORE_CUT:
                wanted.append(f)
                f += IDLE_BLINK_GAPS[i % len(IDLE_BLINK_GAPS)]
                i += 1
    banned = [(first(ctx.shot(i)) - BLINK_FRAMES, last(ctx.shot(i))) for i in NO_BLINK_SHOTS]
    reboot = first(ctx.shot(23))
    chosen = [reboot]                        # keeps the idle blinks clear of the reboot
    for f in wanted:
        if any(a < f <= b for a, b in banned):
            continue
        if all(abs(f - c) >= BLINK_MIN_GAP for c in chosen):
            chosen.append(f)
    return sorted(c for c in chosen if c != reboot)


def key_face(ctx, face):
    beats = eye_beats(ctx)
    eyes = {}
    for (start, eye), following in zip(beats, beats[1:] + [(ctx.frame_end + 1, None)]):
        for f in range(start, following[0]):
            eyes[f] = eye
    mouth = {f: "flat" for f in eyes}
    for f in blink_frames(ctx):
        for b in range(f, min(f + BLINK_FRAMES, ctx.frame_end + 1)):
            eyes[b] = "blink"
    for line in ctx.lines("claude"):
        pixel_face.lip_sync(mouth, first(line), line_envelope(ctx, line))
    face.key(eyes, mouth)


def build(ctx):
    rig, face, glow = append_clawd(ctx)
    anchor = bpy.data.objects[ANCHOR]
    t = targets(ctx, rig, face, anchor)
    key_look(ctx, rig, t)
    key_speech(ctx, rig, glow)
    name_action(rig, "Clawd")
    key_face(ctx, face)
    print("[anim_clawd] rig %s; looks %s" % (rig.name, {k: tuple(round(v, 1) for v in yp) for k, yp in t.items()}))
    return rig
