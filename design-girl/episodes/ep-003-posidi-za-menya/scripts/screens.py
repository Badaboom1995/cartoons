"""EP3 screens: image planes on the laptop and the gold sparkles of «Красиво» on camera 27.

The images come from make_screens.py. Every frame number comes from the timeline. Paths are stored relative to the open
.blend, so the build must keep Blender's default relative_remap when it saves to ep-003.blend.

The finished layout is never shown: from the middle of the timelapse to the end the laptop keeps its evening image,
because Clawd's close-ups in shots 28 and 30 see the front of the screen. This part must run after stage and anim_girl, the sparkles measure them.
"""
import math
import wave

import bpy
import numpy as np
from bpy_extras import anim_utils
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

import ep3

LAPTOP_W, LAPTOP_H = 0.272, 0.17     # local size of the STU_Screen_Laptop quad
LAPTOP_LIFT = 0.0006                 # towards the viewer, along the screen's -Y

SPEAKER_LINE = "v01"
SPEAKER_THRESHOLDS = (0.16, 0.42, 0.72)   # share of the loud level of the line that lights highlight 1, 2 and 3
MIC_PRESS = 1                        # frames into shot 3 when the bar starts, her key press is in shot 2
MIC_STRIKE_STEPS = 7                 # the bar crosses the mic over this many frames, one image each

FRAME_W, FRAME_H = 1080, 1920
SPARKLE_LINE = "v21"
SPARKLE_FILL, SPARKLE_RIM = (255, 226, 60), (222, 150, 28)
SPARKLE_TALL = 1.15                  # the stars are a little taller than wide
SPARKLE_POP = (0.35, 0.95, 1.28, 1.08)    # scale on the first frames of a star, then it twinkles around 1
SPARKLE_TWINKLE = 8.5                # frames per twinkle
# Radius in pixels, frames after the line starts, and where it wants to sit: fractions of her head box, from its
# outer side, so (1, 0.16) is beside the right edge near the top and (-1, 1.3) is left of the head at shoulder height.
SPARKLES = ((88, 0, (1, 0.16)), (58, 1, (-1, 0.30)), (66, 3, (1, 0.82)), (78, 2, (-1, 1.30)), (62, 4, (1, 1.38)))
SPARKLE_GAP = 26                     # clear pixels between a star and her head, her fists or another star


def load_image(name):
    path = ep3.OVERLAYS / f"{name}.png"
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing, run make_screens.py first")
    img = bpy.data.images.load(str(path), check_existing=True)
    img.name = f"{ep3.PREFIX}{name}"
    if bpy.data.filepath:
        img.filepath = bpy.path.relpath(str(path))
    return img


def image_material(name, img):
    """A flat emissive image: scene lights do not touch it."""
    mat = bpy.data.materials.new(f"{ep3.PREFIX}{name}")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emit = nt.nodes.new("ShaderNodeEmission")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Linear"
    tex.extension = "EXTEND"
    emit.inputs["Strength"].default_value = 1.0
    nt.links.new(tex.outputs["Color"], emit.inputs["Color"])
    nt.links.new(emit.outputs[0], out.inputs["Surface"])
    mat.use_backface_culling = False
    return mat


def add_plane(ctx, name, corners, image, parent):
    """corners run bottom left, bottom right, top right, top left."""
    mesh = bpy.data.meshes.new(f"{ep3.PREFIX}{name}")
    mesh.from_pydata(corners, [], [(0, 1, 2, 3)])
    uv = mesh.uv_layers.new(name="UVMap")
    for loop, co in zip(uv.data, ((0, 0), (1, 0), (1, 1), (0, 1))):
        loop.uv = co
    mesh.materials.append(image_material(name, load_image(image)))
    mesh.update()
    ob = bpy.data.objects.new(f"{ep3.PREFIX}{name}", mesh)
    ctx.collection("Screens").objects.link(ob)
    ob.parent = parent
    ob.matrix_parent_inverse = Matrix.Identity(4)
    for attr in ("visible_shadow", "visible_diffuse", "visible_glossy", "visible_transmission",
                 "visible_volume_scatter"):
        setattr(ob, attr, False)
    return ob


def key_visible(ob, spans, frame_start):
    """Visible only inside the (first, last) frame spans, with constant keys."""
    changes = {frame_start: False}
    for first, last in spans:
        changes[last + 1] = False
    for first, _ in spans:
        changes[first] = True
    for frame, visible in sorted(changes.items()):
        ob.hide_render = ob.hide_viewport = not visible
        ob.keyframe_insert("hide_render", frame=frame)
        ob.keyframe_insert("hide_viewport", frame=frame)
    constant_keys(ob)


def constant_keys(ob):
    ad = ob.animation_data
    ad.action.name = f"{ob.name}_Anim"
    bag = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    for curve in bag.fcurves:
        for point in curve.keyframe_points:
            point.interpolation = "CONSTANT"


def shot_frames(ctx, first_shot, last_shot):
    return range(ctx.shot(first_shot)["first_frame"], ctx.shot(last_shot)["last_frame"] + 1)


def voice_envelope(ctx, line):
    """Loudness of the line per video frame, 0..1."""
    with wave.open(str(ctx.audio_path(line)), "rb") as wav:
        rate, channels, width = wav.getframerate(), wav.getnchannels(), wav.getsampwidth()
        raw = wav.readframes(wav.getnframes())
    if width != 2:
        raise ValueError(f"{line['file']}: expected 16-bit audio")
    samples = np.frombuffer(raw, dtype="<i2")[::channels].astype(float)
    per_frame = rate / ctx.fps
    count = line["last_frame"] - line["first_frame"] + 1
    rms = np.zeros(count)
    for i in range(count):
        chunk = samples[int(i * per_frame):int((i + 1) * per_frame)]
        if chunk.size:
            rms[i] = np.sqrt(np.mean(chunk ** 2))
    loud = np.percentile(rms, 92) or 1.0
    return np.clip(rms / loud, 0.0, 1.0)


def speaker_levels(ctx):
    """Highlight level (0-3) per frame of v01. He talks through the mute, then the pulse settles by the end of shot 3."""
    line = ctx.line(SPEAKER_LINE)
    envelope = voice_envelope(ctx, line)
    levels, current = {}, 0
    for frame in range(line["first_frame"], ctx.shot(3)["last_frame"] + 1):
        value = envelope[frame - line["first_frame"]] if frame <= line["last_frame"] else 0.0
        target = sum(value >= threshold for threshold in SPEAKER_THRESHOLDS)
        current = max(target, current - 1)                  # jumps up on the voice, falls one step per frame
        levels[frame] = current
    return levels


def evening_frame(ctx):
    """The middle of the timelapse at the end of shot 8."""
    shot = ctx.shot(8)
    length = round(shot["transition"]["seconds"] * ctx.fps)
    return shot["last_frame"] - length + 1 + length // 2


def laptop_states(ctx):
    """The image on the laptop for every frame of the episode."""
    join = ctx.sfx("join")["first_frame"]
    mic_first = ctx.shot(3)["first_frame"]
    press = mic_first + MIC_PRESS
    evening = evening_frame(ctx)
    states = {frame: "connecting" for frame in range(ctx.frame_start, join)}
    states.update({frame: "call" for frame in range(join, ctx.line(SPEAKER_LINE)["first_frame"])})
    for frame, level in speaker_levels(ctx).items():
        if frame < mic_first:
            states[frame] = f"viktor_{level}"
        else:
            states[frame] = f"mic_{max(0, min(frame - press + 1, MIC_STRIKE_STEPS))}_{level}"
    states.update({frame: "muted" for frame in range(ctx.shot(3)["last_frame"] + 1, evening)})
    states.update({frame: "evening" for frame in range(evening, ctx.frame_end + 1)})
    return states


def spans_by_state(states):
    spans = {}
    for frame in sorted(states):
        runs = spans.setdefault(states[frame], [])
        if runs and runs[-1][1] == frame - 1:
            runs[-1][1] = frame
        else:
            runs.append([frame, frame])
    return spans


def build_laptop(ctx):
    screen = bpy.data.objects[ep3.SCREEN]
    w, h = LAPTOP_W / 2, LAPTOP_H / 2
    corners = [(-w, -LAPTOP_LIFT, -h), (w, -LAPTOP_LIFT, -h), (w, -LAPTOP_LIFT, h), (-w, -LAPTOP_LIFT, h)]
    for state, spans in spans_by_state(laptop_states(ctx)).items():
        ob = add_plane(ctx, f"Screen_{state}", corners, f"laptop_{state}", screen)
        key_visible(ob, spans, ctx.frame_start)


# ---------------------------------------------------------------- sparkles
def projected_box(scene, camera, objects):
    """Pixel box (left, top, right, bottom) of the objects that are visible on the current frame."""
    xs, ys = [], []
    for ob in objects:
        if ob.hide_render or ob.hide_viewport:
            continue
        for corner in ob.bound_box:
            p = world_to_camera_view(scene, camera, ob.matrix_world @ Vector(corner))
            if p.z > 0:
                xs.append(p.x * FRAME_W)
                ys.append((1 - p.y) * FRAME_H)
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def union(a, b):
    if a is None or b is None:
        return a or b
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def measure_her(ctx, camera, first, last):
    """Her head over the whole phrase, her fists once they are up, the lens per frame and the frame at star distance."""
    scene = ctx.scene
    rig = bpy.data.objects[ep3.GIRL_RIG]
    parts = [o for o in bpy.data.objects if o.parent == rig and o.type == "MESH"]
    # her face, without the bun and the headphones: a star may sit over those, as in the reference
    head_parts = [o for o in parts if o.parent_bone == "head" and not any(k in o.name for k in ("Hair", "Headphones"))]
    hands = {bone: [o for o in parts if o.parent_bone == bone] for bone in ("hand.L", "hand.R")}
    fists_up = first + (last - first) // 2
    head, fists, lenses = None, {bone: None for bone in hands}, {}
    keep = scene.frame_current
    for frame in range(first, last + 1):
        scene.frame_set(frame)
        lenses[frame] = camera.data.lens
        head = union(head, projected_box(scene, camera, head_parts))
        if frame >= fists_up:
            for bone, objects in hands.items():
                fists[bone] = union(fists[bone], projected_box(scene, camera, objects))
    distance = max(camera.data.clip_start * 2.0, 0.03)
    corners = camera.data.view_frame(scene=scene)        # still on the last frame: the final framing
    scale = distance / abs(corners[0].z)
    xs, ys = [p.x * scale for p in corners], [p.y * scale for p in corners]
    scene.frame_set(keep)
    return head, [box for box in fists.values() if box], lenses, (min(xs), min(ys), max(xs), max(ys)), distance


def clear_of(x, y, r, head, fists):
    """Her head is round, so it blocks an ellipse. That leaves the corners of its box free for the stars."""
    tall = r * SPARKLE_TALL
    a = (head[2] - head[0]) / 2 + r + SPARKLE_GAP
    b = (head[3] - head[1]) / 2 + tall + SPARKLE_GAP
    if ((x - (head[0] + head[2]) / 2) / a) ** 2 + ((y - (head[1] + head[3]) / 2) / b) ** 2 < 1:
        return False
    return not any(f[0] - r - SPARKLE_GAP < x < f[2] + r + SPARKLE_GAP and
                   f[1] - tall - SPARKLE_GAP < y < f[3] + tall + SPARKLE_GAP for f in fists)


def place_star(target, radius, head, fists, placed):
    """The free spot near the target. A smaller star close to its place beats a full-size one across the frame."""
    best, best_cost = None, None
    for shrink in (1.0, 0.85, 0.7, 0.55):
        r = radius * shrink
        tall = r * SPARKLE_TALL
        for y in range(int(190 + tall), int(1600 - tall), 12):       # inside the Reels interface zones
            for x in range(int(36 + r), int(FRAME_W - 36 - r), 12):
                if not clear_of(x, y, r, head, fists):
                    continue
                if any(math.hypot(x - px, y - py) < r + pr + SPARKLE_GAP for px, py, pr in placed):
                    continue
                cost = math.hypot(x - target[0], y - target[1]) + (1 - shrink) * 300
                if best is None or cost < best_cost:
                    best, best_cost = (x, y, r), cost
    return best


def star_mesh(fill, rim):
    """A flat four-pointed star in the XY plane, facing the camera: concave sides and a thin darker rim."""
    count = 48
    ring = [(math.copysign(abs(math.cos(a)) ** 3, math.cos(a)),
             SPARKLE_TALL * math.copysign(abs(math.sin(a)) ** 3, math.sin(a)))
            for a in (2 * math.pi * i / count for i in range(count))]
    verts = [(0.0, 0.0, 0.0)] + [(x * 0.82, y * 0.82, 0.0) for x, y in ring] + [(x, y, 0.0) for x, y in ring]
    inner = [(0, 1 + i, 1 + (i + 1) % count) for i in range(count)]
    band = [(1 + i, 1 + count + i, 1 + count + (i + 1) % count, 1 + (i + 1) % count) for i in range(count)]
    mesh = bpy.data.meshes.new(f"{ep3.PREFIX}Sparkle")
    mesh.from_pydata(verts, [], inner + band)
    mesh.materials.append(fill)
    mesh.materials.append(rim)
    for polygon in mesh.polygons:
        polygon.material_index = 0 if polygon.index < count else 1
    mesh.update()
    return mesh


def flat_color(name, srgb):
    mat = bpy.data.materials.new(f"{ep3.PREFIX}{name}")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emit = nt.nodes.new("ShaderNodeEmission")
    linear = [(c / 255 / 12.92) if c / 255 <= 0.04045 else ((c / 255 + 0.055) / 1.055) ** 2.4 for c in srgb]
    emit.inputs["Color"].default_value = (*linear, 1.0)
    emit.inputs["Strength"].default_value = 1.0
    nt.links.new(emit.outputs[0], out.inputs["Surface"])
    mat.use_backface_culling = False
    return mat


def key_star(ob, size, appear, last, index):
    for frame in range(appear, last + 1):
        age = frame - appear
        if age < len(SPARKLE_POP):
            amount, tilt = SPARKLE_POP[age], math.radians(-24) * (1 - age / len(SPARKLE_POP))
        else:
            settle = min(1.0, (age - len(SPARKLE_POP) + 1) / 4)  # eases from the end of the pop into the twinkle
            wave_now = math.sin(2 * math.pi * ((age - len(SPARKLE_POP)) / SPARKLE_TWINKLE + index * 0.23))
            amount = 1 + (SPARKLE_POP[-1] - 1) * (1 - settle) + 0.14 * wave_now * settle
            tilt = math.radians(7) * wave_now * settle
        ob.scale = (size * amount, size * amount, 1.0)
        ob.rotation_euler = (0.0, 0.0, tilt)
        ob.keyframe_insert("scale", frame=frame)
        ob.keyframe_insert("rotation_euler", frame=frame)


def build_sparkles(ctx):
    first = ctx.line(SPARKLE_LINE)["first_frame"]
    last = ctx.line("v27")["first_frame"] - 1
    camera = bpy.data.objects[ep3.camera_name(27)]
    head, fists, lenses, (x0, y0, x1, y1), distance = measure_her(ctx, camera, first, last)
    if head is None:
        raise RuntimeError("sparkles: her head is not in front of camera 27")

    root = bpy.data.objects.new(f"{ep3.PREFIX}Sparkles", None)
    ctx.collection("Screens").objects.link(root)
    root.parent = camera
    root.matrix_parent_inverse = Matrix.Identity(4)
    final_lens = lenses[last]
    if max(lenses.values()) - min(lenses.values()) > 1e-4:   # a zoom must not slide the stars across the frame
        for frame, lens in lenses.items():
            root.scale = (final_lens / lens, final_lens / lens, 1.0)
            root.keyframe_insert("scale", frame=frame)
        constant_keys(root)

    mesh = star_mesh(flat_color("Sparkle_Fill", SPARKLE_FILL), flat_color("Sparkle_Rim", SPARKLE_RIM))
    head_w, head_h = head[2] - head[0], head[3] - head[1]
    chest = None                                             # the fists and the space between them stay clear
    for box in fists:
        chest = union(chest, box)
    placed = []
    for index, (radius, delay, (side, height)) in enumerate(SPARKLES):
        edge = head[2] + 0.12 * head_w if side > 0 else head[0] - 0.12 * head_w
        spot = place_star((edge, head[1] + height * head_h), radius, head, [chest] if chest else [], placed)
        if spot is None:
            print(f"screens: no room for sparkle {index} in camera 27, skipped")
            continue
        x, y, r = spot
        placed.append(spot)
        ob = bpy.data.objects.new(f"{ep3.PREFIX}Sparkle_{index}", mesh)
        ctx.collection("Screens").objects.link(ob)
        ob.parent = root
        ob.matrix_parent_inverse = Matrix.Identity(4)
        ob.location = (x0 + x / FRAME_W * (x1 - x0), y1 - y / FRAME_H * (y1 - y0), -distance)
        for attr in ("visible_shadow", "visible_diffuse", "visible_glossy", "visible_transmission",
                     "visible_volume_scatter"):
            setattr(ob, attr, False)
        appear = min(first + delay, last)
        key_star(ob, r / FRAME_W * (x1 - x0), appear, last, index)
        key_visible(ob, [(appear, last)], ctx.frame_start)
    print(f"screens: {len(placed)} sparkles, frames {first}-{last}")


def build(ctx):
    build_laptop(ctx)
    build_sparkles(ctx)
