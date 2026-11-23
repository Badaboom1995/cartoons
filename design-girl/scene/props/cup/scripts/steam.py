"""Animated steam for a cup, for any episode.

    add_steam(scene, cup, frame_start, frame_end)

Adds 2-3 thin, pale, warm wisps rising from the liquid. Everything is keyed, with no drivers or frame handlers, so it
plays in any Blender and works in EEVEE:

Shape    each wisp is a flat quad; its shader draws a soft line that curls and rises, moved by one keyed linear time value.
Follow   the wisps copy the position of a point on the liquid, so they follow the cup but stay upright when it tilts.
         They lean a little against the direction of travel.
Facing   constant yaw keys turn them to the active camera on every cut and keep them facing it as the cup moves.
Fade     one keyed level. `hidden_spans` and `fade_near` fade them out before they could cross something, such as a face.
"""
import math

import bpy
from bpy_extras import anim_utils
from mathutils import Vector

HEIGHT = 0.14                  # metres above the liquid
HALF_WIDTH = 0.045             # half the quad: the room a wisp has to curl in
OPACITY = 0.42                 # at the densest point of a wisp: keeps it subtle, never a white cloud
COLOUR = (1.0, 0.86, 0.72, 1.0)   # pale warm, linear
LIQUID_NAMES = ("tea", "coffee", "liquid", "water")

#         across  depth   height width  phase  opacity
WISPS = ((-0.014, 0.004, 1.00, 1.00, 0.08, 1.00),
         (0.013, -0.005, 0.86, 0.85, 0.47, 0.78),
         (0.001, 0.009, 0.93, 0.70, 0.79, 0.62))

SAMPLE_STEP = 2                # frames between samples of the cup's path
FADE_FRAMES = 14               # length of a fade out or in
LEAN_PER_SPEED = math.radians(9.0)   # lean per metre per second of travel
MAX_LEAN = math.radians(12.0)
LEAN_SMOOTH = 3                # samples on each side
YAW_STEP = math.radians(1.5)   # a new facing key once the camera has moved this far around the wisps
JUMP_SPEED = 2.5               # m/s: faster than this is a cut or a re-parent, not a walk, so it adds no lean


# ---------------------------------------------------------------- animation helpers
def fcurves_of(idb):
    ad = idb.animation_data
    if not ad or not ad.action:
        return []
    try:
        return list(ad.action.fcurves)
    except AttributeError:
        bag = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
        return list(bag.fcurves) if bag else []


def set_interpolation(idb, kind, data_path=None, index=None):
    for fc in fcurves_of(idb):
        if (data_path is None or fc.data_path == data_path) and (index is None or fc.array_index == index):
            for kp in fc.keyframe_points:
                kp.interpolation = kind


def key_socket(sock, keys):
    for frame, value in keys:
        sock.default_value = value
        sock.keyframe_insert("default_value", frame=frame)


# ---------------------------------------------------------------- shader
class Nodes:
    """Math nodes written as expressions. An operand is a number or a socket."""

    def __init__(self, tree):
        self.tree = tree

    def new(self, kind, **props):
        node = self.tree.nodes.new(kind)
        count = len(self.tree.nodes)
        node.location = (200 * (count % 8), -170 * (count // 8))
        for key, value in props.items():
            setattr(node, key, value)
        return node

    def feed(self, sock, value):
        if isinstance(value, bpy.types.NodeSocket):
            self.tree.links.new(value, sock)
        else:
            sock.default_value = value

    def math(self, operation, a, b=None):
        node = self.new("ShaderNodeMath", operation=operation)
        self.feed(node.inputs[0], a)
        if b is not None:
            self.feed(node.inputs[1], b)
        return node.outputs[0]

    def add(self, *terms):
        total = terms[0]
        for term in terms[1:]:
            total = self.math("ADD", total, term)
        return total

    def mul(self, *terms):
        total = terms[0]
        for term in terms[1:]:
            total = self.math("MULTIPLY", total, term)
        return total

    def smooth(self, value, low, high):
        node = self.new("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
        self.feed(node.inputs["Value"], value)
        node.inputs["From Min"].default_value = low
        node.inputs["From Max"].default_value = high
        node.inputs["To Min"].default_value = 0.0
        node.inputs["To Max"].default_value = 1.0
        return node.outputs[0]

    def value(self, name, default):
        node = self.new("ShaderNodeValue")
        node.name = node.label = name
        node.outputs[0].default_value = default
        return node.outputs[0]


def build_material(name):
    """Returns the material and its keyable time, level and strength sockets."""
    material = bpy.data.materials.new(name)
    try:
        material.use_nodes = True
    except Exception:
        pass
    material.surface_render_method = "BLENDED"
    material.use_backface_culling = False
    tree = material.node_tree
    tree.nodes.clear()
    g = Nodes(tree)

    uv = g.new("ShaderNodeSeparateXYZ")
    tree.links.new(g.new("ShaderNodeTexCoord").outputs["UV"], uv.inputs[0])
    u, v = uv.outputs["X"], uv.outputs["Y"]
    own = g.new("ShaderNodeSeparateXYZ")                    # each wisp keeps its phase and opacity in its object colour
    tree.links.new(g.new("ShaderNodeObjectInfo").outputs["Color"], own.inputs[0])
    phase = g.mul(own.outputs["X"], math.tau)
    time = g.value("Steam_Time", 0.0)
    level = g.value("Steam_Level", 1.0)
    strength = g.value("Steam_Strength", 1.0)

    def wave(cycles, rate, phase_share, shift):
        """A sine that travels up the wisp."""
        travel = g.math("SUBTRACT", g.mul(v, cycles), g.mul(time, rate))
        return g.math("SINE", g.add(g.mul(travel, math.tau), g.mul(phase, phase_share), shift))

    reach = g.add(0.10, g.mul(g.math("POWER", v, 1.3), 0.60))    # steady at the liquid, curling more as it rises
    curl = g.add(g.mul(wave(1.35, 0.95, 1.0, 0.0), 0.62), g.mul(wave(2.7, 1.63, 2.3, 1.0), 0.38))
    centre = g.mul(reach, curl)
    across = g.math("SUBTRACT", g.mul(u, 2.0), 1.0)
    off_line = g.math("ABSOLUTE", g.math("SUBTRACT", across, centre))
    thickness = g.add(0.06, g.mul(v, 0.11))
    line = g.math("EXPONENT", g.mul(g.math("POWER", g.math("DIVIDE", off_line, thickness), 2.0), -1.0))
    fade_in = g.smooth(v, 0.0, 0.16)
    fade_out = g.math("SUBTRACT", 1.0, g.smooth(v, 0.5, 1.0))
    puffs = g.add(0.66, g.mul(wave(2.2, 1.45, 1.7, 0.0), 0.34))
    alpha = g.mul(line, fade_in, fade_out, puffs, own.outputs["Y"], level, OPACITY)

    emission = g.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = COLOUR
    tree.links.new(strength, emission.inputs["Strength"])
    clear = g.new("ShaderNodeBsdfTransparent")
    mix = g.new("ShaderNodeMixShader")
    tree.links.new(alpha, mix.inputs[0])
    tree.links.new(clear.outputs[0], mix.inputs[1])
    tree.links.new(emission.outputs[0], mix.inputs[2])
    out = g.new("ShaderNodeOutputMaterial")
    tree.links.new(mix.outputs[0], out.inputs["Surface"])
    return material, time, level, strength


# ---------------------------------------------------------------- objects
def liquid_point(cup):
    """Middle of the liquid's surface in the cup's space, or the top of the cup if no material is named as a liquid."""
    mesh = cup.data
    slots = {i for i, m in enumerate(mesh.materials) if m and any(n in m.name.lower() for n in LIQUID_NAMES)}
    points = [mesh.vertices[i].co for p in mesh.polygons if p.material_index in slots for i in p.vertices]
    if not points:
        return Vector((0.0, 0.0, max(c[2] for c in cup.bound_box)))
    span = lambda axis: (min(q[axis] for q in points) + max(q[axis] for q in points)) / 2
    return Vector((span(0), span(1), max(q.z for q in points)))


def wisp_mesh(name):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([(-HALF_WIDTH, 0, 0), (HALF_WIDTH, 0, 0), (HALF_WIDTH, 0, HEIGHT), (-HALF_WIDTH, 0, HEIGHT)],
                     [], [(0, 1, 2, 3)])
    uv = mesh.uv_layers.new(name="UVMap")
    for loop, corner in zip(uv.data, ((0, 0), (1, 0), (1, 1), (0, 1))):
        loop.uv = corner
    mesh.update()
    return mesh


def camera_spans(scene, frame_start, frame_end, camera_by_frame):
    """[(first, last, camera)] from a {frame: camera} dict, a list of (frame, camera), or the timeline's camera markers."""
    if camera_by_frame is None:
        cuts = [(m.frame, m.camera) for m in scene.timeline_markers if m.camera] or [(frame_start, scene.camera)]
    elif hasattr(camera_by_frame, "items"):
        cuts = list(camera_by_frame.items())
    else:
        cuts = list(camera_by_frame)
    cuts.sort(key=lambda c: c[0])
    spans = []
    for i, (frame, camera) in enumerate(cuts):
        last = cuts[i + 1][0] - 1 if i + 1 < len(cuts) else frame_end
        first = max(frame, frame_start) if i else frame_start
        if first <= min(last, frame_end):
            spans.append((first, min(last, frame_end), camera))
    return spans


# ---------------------------------------------------------------- motion
def sample(scene, anchor, near, spans, frames):
    """World positions of the liquid, of the thing to avoid and of the active camera on the frames given."""
    path, avoid, seen = {}, {}, {}
    for frame in sorted(frames):
        scene.frame_set(frame)
        dg = bpy.context.evaluated_depsgraph_get()
        path[frame] = anchor.evaluated_get(dg).matrix_world.translation.copy()
        if near:
            avoid[frame] = near.evaluated_get(dg).matrix_world.translation.copy()
        camera = next(c for first, last, c in spans if first <= frame <= last)
        seen[frame] = camera.evaluated_get(dg).matrix_world.translation.copy()
    return path, avoid, seen


def yaw_keys(path, seen, spans):
    """(frame, yaw) turning the quad's -Y to the lens: always on a cut, and between cuts only when it has drifted."""
    cuts = {first for first, _, _ in spans}
    keys = []
    for frame in sorted(path):
        to_camera = seen[frame] - path[frame]
        yaw = math.atan2(to_camera.x, -to_camera.y)
        if frame in cuts or not keys or abs(math.remainder(yaw - keys[-1][1], math.tau)) > YAW_STEP:
            keys.append((frame, yaw))
    return keys


def lean_keys(path, fps):
    """(frame, x angle, y angle), so the top of the wisps trails behind the cup's horizontal travel."""
    frames = sorted(path)
    raw = []
    for a, b in zip(frames, frames[1:] + frames[-1:]):
        step = max(1, b - a)
        move = (path[b] - path[a]) / step * fps
        fast = move.length > JUMP_SPEED
        raw.append((0.0, 0.0) if fast else (LEAN_PER_SPEED * move.y, -LEAN_PER_SPEED * move.x))
    keys = []
    for i, frame in enumerate(frames):
        near = raw[max(0, i - LEAN_SMOOTH):i + LEAN_SMOOTH + 1]
        x, y = (sum(r[axis] for r in near) / len(near) for axis in (0, 1))
        size = math.hypot(x, y)
        scale = min(1.0, MAX_LEAN / size) if size > 0 else 1.0
        keys.append((frame, x * scale, y * scale))
    return keys


def distance_to_column(point, base):
    up = max(0.0, min(HEIGHT, point.z - base.z))
    return (point - (base + Vector((0.0, 0.0, up)))).length


def level_keys(path, avoid, radius, hidden_spans):
    frames = sorted(path)
    hidden = [any(a <= f <= b for a, b in hidden_spans) or (bool(avoid) and distance_to_column(avoid[f], path[f]) < radius)
              for f in frames]
    marks = [f for f, h in zip(frames, hidden) if h]
    for a, b in zip(marks, marks[1:]):             # never flicker back on for a moment between two hidden stretches
        if 1 < b - a <= 2 * FADE_FRAMES:
            hidden = [h or a <= f <= b for f, h in zip(frames, hidden)]
    marks = [f for f, h in zip(frames, hidden) if h]
    if not marks:
        return [(frames[0], 1.0), (frames[-1], 1.0)]
    keys = []
    for f in frames:
        gap = min(abs(f - m) for m in marks)
        t = max(0.0, min(1.0, gap / FADE_FRAMES))
        keys.append((f, t * t * (3 - 2 * t)))
    return [k for i, k in enumerate(keys)                # only where the level changes
            if i in (0, len(keys) - 1) or not keys[i - 1][1] == k[1] == keys[i + 1][1]]


# ---------------------------------------------------------------- the one call
def add_steam(scene, cup, frame_start, frame_end, camera_by_frame=None, name="Steam", collection=None,
              fade_near=None, hidden_spans=(), strength_keys=None):
    """Adds steam to `cup` on frames frame_start..frame_end. Call it after the cup is animated.

    camera_by_frame  {first frame: camera} or [(first frame, camera)]; by default the timeline's camera markers.
    name             prefix of everything it creates.
    collection       where the objects go; by default the scene's root collection.
    fade_near        (object, radius): the wisps fade out while their column comes within radius metres of the object.
    hidden_spans     [(first, last)]: frames on which the wisps are fully faded out.
    strength_keys    [(frame, brightness)], e.g. dimmer in the evening; 1.0 by default.

    Returns a dict with the root, wisps, material and anchor.
    """
    collection = collection or scene.collection
    anchor = bpy.data.objects.new(name + "_Anchor", None)
    anchor.empty_display_size = 0.01
    collection.objects.link(anchor)
    anchor.parent = cup
    anchor.location = liquid_point(cup)

    root = bpy.data.objects.new(name + "_Root", None)
    root.empty_display_size = 0.02
    root.rotation_mode = "ZYX"                     # yaw first, then the lean in world axes
    collection.objects.link(root)
    follow = root.constraints.new("COPY_LOCATION")
    follow.target = anchor

    material, time, level, strength = build_material(name)
    mesh = wisp_mesh(name)
    mesh.materials.append(material)
    wisps = []
    for i, (across, depth, height, width, phase, opacity) in enumerate(WISPS):
        wisp = bpy.data.objects.new("%s_Wisp_%d" % (name, i + 1), mesh)
        wisp.parent = root
        wisp.location = (across, depth, 0.0)
        wisp.scale = (width, 1.0, height)
        wisp.color = (phase, opacity, 0.0, 1.0)
        wisp.visible_shadow = False
        collection.objects.link(wisp)
        wisps.append(wisp)

    spans = camera_spans(scene, frame_start, frame_end, camera_by_frame)
    frames = set(range(frame_start, frame_end + 1, SAMPLE_STEP)) | {frame_end} | {first for first, _, _ in spans}
    for a, b in hidden_spans:
        frames |= {max(frame_start, a), min(frame_end, b)}
    near, radius = fade_near if fade_near else (None, 0.0)
    path, avoid, seen = sample(scene, anchor, near, spans, frames)

    fps = scene.render.fps / scene.render.fps_base
    for frame, x, y in lean_keys(path, fps):
        root.rotation_euler[0], root.rotation_euler[1] = x, y
        root.keyframe_insert("rotation_euler", index=0, frame=frame)
        root.keyframe_insert("rotation_euler", index=1, frame=frame)
    for frame, yaw in yaw_keys(path, seen, spans):
        root.rotation_euler[2] = yaw
        root.keyframe_insert("rotation_euler", index=2, frame=frame)
    set_interpolation(root, "LINEAR")
    set_interpolation(root, "CONSTANT", "rotation_euler", 2)

    key_socket(time, [(frame_start, 0.0), (frame_end, (frame_end - frame_start) / fps)])
    key_socket(level, level_keys(path, avoid, radius, hidden_spans))
    key_socket(strength, strength_keys or [(frame_start, 1.0)])
    set_interpolation(material.node_tree, "LINEAR")

    scene.frame_set(frame_start)
    return dict(root=root, wisps=wisps, material=material, anchor=anchor)
