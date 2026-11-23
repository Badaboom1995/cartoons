"""EP3 Clawd: appended from clawd.blend, on the dock, serious and kind, with a block face. All frames come from the timeline.

  turns   yaw of the rig, held exactly between moves (yaw_keys)
  nods    the body bone: shots 7 and 30, two tiny listening nods, a tiny one on «да» in v17 and on each item of v20,
          and a small lift of his gaze as she rises in shot 29
  face    pixel_face.py: eyes per beat (eye_beats), blinks, a short flat mouth with lip sync from the wav. No smiles
  speech  a tiny squash and a faint warm glow, driven by the same wav envelope
  breath  a very slow, barely visible rise and fall, so the long holds stay alive
  still   from the start of the timelapse through the 8/9 cut nothing on him moves, so only the light changes
"""
import math
import sys

import bpy
from mathutils import Matrix

import ep3

_FACE_SCRIPTS = str(ep3.CHARACTER / "scene" / "characters" / "clawd" / "scripts")
if _FACE_SCRIPTS not in sys.path:
    sys.path.insert(0, _FACE_SCRIPTS)
import pixel_face  # noqa: E402
from pixel_face import fcurves_of, read_envelope  # noqa: E402

CLAWD_SCALE = 0.18
ANCHOR = "STU_Claude_Dock_Anchor"
SOURCE_COLLECTION = "MSC_Character"

# Where she stands at the edge of the frame in shot 29, when she asks "Завтра снова меня подменишь?".
# The girl is built after Clawd, so this is a fixed point: the end of her shot 29 walk.
HER_EXIT_XY = (-0.93, 0.46)

SPEECH_SQUASH = 0.016     # body height change at full voice
SPEECH_GLOW = 0.18        # emission strength at full voice
NOD_DEGREES = 9.0
LISTEN_NOD_DEGREES = 3.0
LIST_NOD_DEGREES = 2.5    # one on each thing he lists in v20: three in a row, so smaller
LIST_NOD_BEFORE_END = 8   # its lowest point, in frames before the item's phrase ends
NOD_DOWN_FRAMES = 4
NOD_FRAMES = 11
TURN_FRAMES = 12          # a calm turn
FOLLOW_TURN_FRAMES = 16   # he follows her walk to the mark in shot 29
RISE_LOOK_DEGREES = 3.0   # he looks up a little as she stands
RISE_LOOK_DELAY = 2       # frames after her line starts
RISE_LOOK_FRAMES = 14
BLINK_FRAMES = 4
BLINK_MIN_GAP = 18
IDLE_BLINK_START = 20     # frames into a shot
IDLE_BLINK_GAPS = (52, 38, 64)   # uneven, so the blinks do not tick
IDLE_BLINK_MIN_SHOT = 30
BREATH = 0.004            # body height change at the top of a breath
BREATH_FRAMES = 96
BREATH_FADE = 24          # frames for the breath to settle before the timelapse and return after it

# Shots he is on camera in, for the idle blinks.
ON_CAMERA = (0, 5, 7, 8, 9, 10, 15, 19, 21, 22, 24, 28, 29, 30, 31)


def first(item):
    return item["first_frame"]


def last(item):
    return item["last_frame"]


def name_action(idb, name):
    idb.animation_data.action.name = ep3.PREFIX + name


def set_interpolation(idb, data_path, kind):
    for fc in fcurves_of(idb):
        if data_path in fc.data_path:
            for kp in fc.keyframe_points:
                kp.interpolation = kind


# ---------------------------------------------------------------- model
def append_clawd(ctx):
    with bpy.data.libraries.load(str(ep3.CLAWD_BLEND), link=False) as (src, dst):
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
        ob.name = ep3.CLAWD_RIG if ob is rig else f"{ep3.PREFIX}Clawd_{short}"
        ob.data.name = ob.name
    glow = []
    for mat in {s.material for o in parts for s in o.material_slots if s.material}:
        is_eye = mat.name.endswith("_eye")
        mat.name = f"{ep3.PREFIX}Clawd_{mat.name.removeprefix('MSC_')}"
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
    face = pixel_face.build(rig, old_eyes, target, f"{ep3.PREFIX}Clawd_")
    return rig, face, glow


# ---------------------------------------------------------------- voice
def line_envelope(ctx, line):
    return read_envelope(ctx.audio_path(line), last(line) - first(line) + 1, ctx.fps)


def speech_curve(ctx):
    """{frame: 0..1} over all of Clawd's lines, with a short fade after each."""
    curve = {}
    for line in ctx.lines("claude"):
        env = line_envelope(ctx, line)
        for i, v in enumerate(env):
            curve[first(line) + i] = max(curve.get(first(line) + i, 0.0), v)
        v = env[-1]
        for f in range(last(line) + 1, last(line) + 4):
            v *= 0.45
            curve[f] = max(curve.get(f, 0.0), v)
    return {f: v for f, v in curve.items() if v > 0.01 and f <= ctx.frame_end}


def phrases(ctx, line):
    """The spoken phrases of a line as (first, last) frames, split at the silences in its wav."""
    return [(first(line) + a, first(line) + b) for a, b in pixel_face.voice_phrases(ctx.audio_path(line), ctx.fps)]


def second_phrase_frame(ctx, line):
    """First frame of the second phrase ("Не переживай. | Я уже сделал...")."""
    parts = phrases(ctx, line)
    return parts[1][0] if len(parts) > 1 else first(line) + int(0.3 * (last(line) - first(line)))


def list_item_ends(ctx):
    """Last frame of each thing he lists in v20: «...сайта», «приложение», «...пятницу»."""
    line = ctx.line("v20")
    parts = phrases(ctx, line)
    if len(parts) >= 4:
        return [b for _, b in parts[-3:]]
    start, n = second_phrase_frame(ctx, line), last(line) - 7
    return [start + round((n - start) * k) for k in (0.45, 0.67, 1.0)]


def last_syllable_frame(ctx, line):
    """Where the last syllable starts: the last sharp rise of the voice ("Я отвечал | да")."""
    env = line_envelope(ctx, line)
    rises = [i for i in range(1, len(env)) if env[i] - env[i - 1] > 0.25]
    return first(line) + (rises[-1] if rises else int(0.7 * len(env)))


def midline_pause(ctx, line):
    """The deepest dip of the voice in the middle half of a line ("Тогда на сегодня всё. | Завтра снова...")."""
    env = line_envelope(ctx, line)
    return first(line) + min(range(len(env) // 4, 3 * len(env) // 4), key=env.__getitem__)


def still_window(ctx):
    """(first, last) frame in which he does not move at all: the timelapse at the end of shot 8, through the cut."""
    shot_8 = ctx.shot(8)
    return last(shot_8) - round(shot_8["transition"]["seconds"] * ctx.fps) + 1, first(ctx.shot(9))


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
        name_action(mat.node_tree, mat.name.removeprefix(ep3.PREFIX) + "_glow")


# ---------------------------------------------------------------- turns
def yaw_to(anchor, xy):
    """Rig yaw (degrees, in the anchor's space) that points his face, -Y at rest, at a world point."""
    p = anchor.matrix_world.translation
    world = math.degrees(math.atan2(xy[0] - p.x, -(xy[1] - p.y)))
    return world - math.degrees(anchor.matrix_world.to_euler().z)


def nearest(angle, ref):
    while angle - ref > 180:
        angle -= 360
    while angle - ref < -180:
        angle += 360
    return angle


def turn_windows(ctx):
    """Every turn as (start, end). Calm, and reactions start on the cut."""
    v06, v26 = ctx.line("v06"), ctx.line("v26")
    walk_29 = midline_pause(ctx, ctx.line("v23"))      # she rises on the first phrase and walks on «Завтра снова»
    s5, s24 = first(ctx.shot(5)), first(ctx.shot(24))
    back_8 = last(v26) + 3                             # after her line, settled before the timelapse
    return {
        "to_her_5": (s5, s5 + TURN_FRAMES),
        "to_laptop_8": (back_8, min(back_8 + TURN_FRAMES + 2, still_window(ctx)[0] - 2)),
        "to_her_9": (first(v06) + 3, first(v06) + 3 + TURN_FRAMES),
        "to_her_24": (s24, s24 + TURN_FRAMES),
        "to_exit_29": (walk_29, walk_29 + FOLLOW_TURN_FRAMES),       # settled on her before «...подменишь?»
    }


def yaw_keys(ctx, anchor):
    laptop_ob = bpy.data.objects[ep3.SCREEN].matrix_world.translation
    her_ob = bpy.data.objects[ep3.GIRL_RIG].matrix_world.translation
    laptop = yaw_to(anchor, (laptop_ob.x, laptop_ob.y))
    her = nearest(yaw_to(anchor, (her_ob.x, her_ob.y)), laptop)
    door = nearest(yaw_to(anchor, HER_EXIT_XY), her)
    t = turn_windows(ctx)
    cut_22 = first(ctx.shot(22))
    keys = [
        (ctx.frame_start, laptop),
        (t["to_her_5"][0], laptop), (t["to_her_5"][1], her),
        (t["to_laptop_8"][0], her), (t["to_laptop_8"][1], laptop),
        (t["to_her_9"][0], laptop), (t["to_her_9"][1], her),
        (cut_22 - 1, her), (cut_22, laptop),           # on the cut: back at the laptop, so shot 24 can turn to her
        (t["to_her_24"][0], laptop), (t["to_her_24"][1], her),
        (t["to_exit_29"][0], her), (t["to_exit_29"][1], door),
        (ctx.frame_end, door),                         # the episode ends with him still looking after her
    ]
    return keys, cut_22 - 1


def key_turns(ctx, rig, anchor):
    keys, step_frame = yaw_keys(ctx, anchor)
    for f, deg in keys:
        rig.rotation_euler = (0, 0, math.radians(deg))
        rig.keyframe_insert("rotation_euler", index=2, frame=f)
    for fc in fcurves_of(rig):
        if fc.data_path == "rotation_euler":
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT" if int(kp.co.x) == step_frame else "BEZIER"
                kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"
            fc.update()


# ---------------------------------------------------------------- nods
def pitch_basis(rig, degrees):
    """Pose-space basis for the body bone leaning forward (towards his face) around its base."""
    rest = rig.data.bones["body"].matrix_local
    m = (Matrix.Rotation(math.radians(degrees), 3, "X") @ rest.to_3x3()).to_4x4()
    m.translation = rest.translation
    return rest.inverted() @ m


def nods(ctx):
    return sorted([
        (first(ctx.shot(7)), NOD_DEGREES),                   # "Понял.", from the cut: the shot is short
        (first(ctx.line("v26")) + 13, LISTEN_NOD_DEGREES),   # listening to "Я за кофе, скоро буду."
        (last_syllable_frame(ctx, ctx.line("v17")) - NOD_DOWN_FRAMES, LISTEN_NOD_DEGREES),  # lowest on «да»
        (first(ctx.line("v18")) + 18, LISTEN_NOD_DEGREES),   # listening to "Зато не уволили"
        (first(ctx.shot(30)), NOD_DEGREES),                  # "Конечно!", from the cut, lowest on the stress
    ] + [(end - LIST_NOD_BEFORE_END - NOD_DOWN_FRAMES, LIST_NOD_DEGREES) for end in list_item_ends(ctx)])


def rise_look(ctx):
    """His gaze lifts a little as she stands in shot 29, and comes level again as he follows her to the mark."""
    start = first(ctx.line("v23")) + RISE_LOOK_DELAY
    walk, settled = turn_windows(ctx)["to_exit_29"]
    return [(start, 0.0), (start + RISE_LOOK_FRAMES, -RISE_LOOK_DEGREES), (walk, -RISE_LOOK_DEGREES), (settled, 0.0)]


def key_nods(ctx, rig):
    pb = rig.pose.bones["body"]
    pb.rotation_mode = "QUATERNION"
    keys = [(ctx.frame_start, 0.0)] + rise_look(ctx)
    for start, degrees in nods(ctx):
        keys += [(start, 0.0), (start + NOD_DOWN_FRAMES, degrees), (start + NOD_FRAMES, 0.0)]
    for f, deg in keys:
        pb.rotation_quaternion = pitch_basis(rig, deg).to_quaternion()
        pb.keyframe_insert("rotation_quaternion", frame=f)
    pb.rotation_quaternion = (1, 0, 0, 0)


# ---------------------------------------------------------------- face
def eye_beats(ctx):
    """(frame, eyes), in order. His mouth stays flat, so all the warmth is here."""
    shot = lambda i: first(ctx.shot(i))
    line = lambda i: first(ctx.line(i))
    return [
        (ctx.frame_start, "neutral"),
        (shot(5), "attentive"),                                   # v03 "Конечно. Что мне делать?"
        (shot(7), "neutral"),                                     # v05 "Понял."; unchanged across the 8/9 cut
        (line("v06"), "attentive"),                               # she is back and asks
        (shot(10), "happy"),                                      # v07 "Отлично": pleased, which is the joke
        (second_phrase_frame(ctx, ctx.line("v07")), "neutral"),   # "...объявили о сокращениях"
                                                                  # shot 15, v10 and v12: stays flat and serious
        (shot(19), "attentive"),                                  # the list, v13 and v15
        (shot(21), "neutral"),                                    # v17 «Я отвечал «да».», totally flat
        (line("v18"), "concerned"),                               # "Ну. Зато не уволили."
        (shot(24), "concerned"),                                  # "Не переживай."
        (second_phrase_frame(ctx, ctx.line("v20")), "soft"),      # from «Я уже сделал...», through the whole list
        (shot(25), "neutral"),
                                                                  # shot 28, v22 «Проведу я.»: stays flat and serious
        (line("v23"), "attentive"),                               # he follows her as she rises and walks to her mark
        (shot(30), "soft"),                                       # "Конечно!": kind and serious, no smile
        (shot(31) + 16, "neutral"),                               # she is leaving, back to his usual face
    ]


def blink_frames(ctx):
    """Into the soft look and in the breaths of the v20 list first, then on each turn, then idle blinks in the longer shots. None in the still window."""
    turns = turn_windows(ctx).values()
    items = list_item_ends(ctx)
    wanted = [second_phrase_frame(ctx, ctx.line("v20")) - (BLINK_FRAMES - 1), items[0] + 1, items[-1] + 1]
    wanted += [(a + b) // 2 for a, b in turns]
    for shot_id in ON_CAMERA:
        s = ctx.shot(shot_id)
        if shot_id != 24 and last(s) - first(s) + 1 >= IDLE_BLINK_MIN_SHOT:      # shot 24 blinks in the breaths of the list
            f, i = first(s) + IDLE_BLINK_START, shot_id
            while f < last(s) - BLINK_FRAMES:
                wanted.append(f)
                f += IDLE_BLINK_GAPS[i % len(IDLE_BLINK_GAPS)]
                i += 1
    still_a, still_b = still_window(ctx)
    chosen = []
    for f in wanted:
        if not still_a - BLINK_FRAMES < f <= still_b and all(abs(f - c) >= BLINK_MIN_GAP for c in chosen):
            chosen.append(f)
    return sorted(chosen)


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
    key_turns(ctx, rig, anchor)
    key_nods(ctx, rig)
    key_speech(ctx, rig, glow)
    name_action(rig, "Clawd")
    key_face(ctx, face)
    print(f"[anim_clawd] rig {rig.name}, {len(face.eyes)} eye shapes, {len(face.mouths)} mouth shapes")
    return rig
