"""EP4 stage: scene settings, sound strips, day/evening light, the whiteboard, the evening mess and the rage in shot 28.

Light    day through the last frame of shot 16, evening (lamp on) from the first frame of shot 27: one hard switch on
         the cut, no timelapse. The studio's lilac lamp and blue evening fills are warmed up as in ep-003.
Board    EP4_Board, a mobile whiteboard on a stand, diagonally across the back right corner in front of the floor lamp
         (ep4.BOARD_CENTRE, ep4.BOARD_YAW_DEG), clear of the posters. The plant that stood there moves forward along the
         right wall, so the board reads in the frontal two-shot. Clean white by day; from the first evening frame its
         surface shows assets/board_drawn.png (scripts/make_board.py). One keyed mix factor switches it.
Shot 16  she takes marker ep4.BOARD_MARKER off the tray and draws ep4.BOARD_STROKES_16: from "pick" the marker rides in
         her right fist (Child Of hand.R, held as ep4.BOARD_MARKER_GRIP), and each line grows behind the tip as
         ep4.drawn_length_16() says (a flat bevelled curve, keyed bevel_factor_end). From the evening cut the lines are
         part of board_drawn.png and the marker lies on the tray again.
Desk     by day only STU_Tea_Cup. From the evening: four more cups (EP4_Cup_*, copies of it), and sketch sheets
         (EP4_Paper_*) in heaps on both sides and along the front edge. The middle in front of the chair, the
         keyboard, the mouse and Clawd's dock stay free. The tea is drunk: in the evening the tea surface is gone.
Rage     shot 28, on each frame of ep4.RAGE_HITS: every cup hops 2-4 cm and tips a little, the sheets on the desk
         jump a few millimetres, and some sheets fly off the desk and land on the floor, where they stay to the end.
Sound    one strip per voice line (her on channel 2, Clawd on 3); each effect on its own channel from 5.
"""
import math
import random

import bpy
from mathutils import Euler, Matrix, Vector

import ep4

RENDER_PATH = "//renders/ep-004_"
VOICE_CHANNELS = {"girl": 2, "claude": 3}
SFX_FIRST_CHANNEL = 5

# ---------------------------------------------------------------- light (values from ep-003)
LIGHT_SETS = {"STU_Lights_Day": "day", "STU_Lights_Evening": "evening", "STU_Lights_Lamp": "evening"}
LAMP_GLOW_STRENGTH = {"STU_lamp_glow": 6.0, "STU_lamp_glow_B": 6.0}  # EMISSION in studio.py
LAMP_B_LIGHT = "STU_Lamp_Light_B"
LAMP_B_MATERIAL = "STU_lamp_glow_B"
LAMP_B_WARM = "#F7CDA4"               # the studio default is lilac (#C9A7F0)
EVENING_WARM = {"STU_Glow_Laptop": "#FFEBD8", "STU_Glow_Tablet": "#FFEBD8", "STU_Evening_Fill": "#C4A9A6"}

# ---------------------------------------------------------------- board
BOARD_SIZE = (0.85, 0.72)             # must match BOARD_SIZE_M in make_board.py
POST = 0.03                           # the stand: square posts at both ends, from the floor to above the board
POST_TOP = 1.70
FOOT_FRONT, FOOT_BACK = 0.16, 0.09    # feet under each post, into the room (short: she stands at the left end in 16)
FOOT_H = 0.035
CASTER = 0.03
PLANT = "STU_Floor_Plant"
PLANT_SPOT = Vector((1.30, -0.25))    # its new place on the floor, forward along the right wall
BOARD_FRAME = 0.025                   # aluminium edge, as seen from the front
BOARD_DEPTH = 0.025                   # surface to wall side of the backing
BOARD_LIP = 0.006                     # the frame stands this far proud of the surface
BOARD_CLEAN = "#F3F3F0"
BOARD_IMAGE = "board_drawn.png"
TRAY_LENGTH = 0.70
MARKERS = (("#22242C", -0.18), ("#2454C4", -0.08), ("#D6342C", 0.05))   # colour, x on the tray; EP4_Board_Marker_1..3
MARKER_THICK = 0.016
MARKER_TAKE_FRAMES = 3                # before "pick" the marker slides from the tray into her closing fist
STROKE_WIDTH = 0.010                  # a marker line on the board; must match MARKER_STROKE_M in make_board.py
STROKE_PROUD = 0.0012                 # the middle of a line stands this far out of the surface
STROKE_FLAT = 0.2                     # a line is a round tube squashed to this share of its width across the board

# ---------------------------------------------------------------- desk
TEA_MATERIAL = "STU_tea"
STEAM = "STU_Tea_Steam"
DESK_LIFT = "STU_Desk_Lift"
PAPER_SIZE = (0.19, 0.265)            # sketch sheets, a bit under A4
PAPER_Z = 0.7245                      # just above the desk mat (0.723), so no sheet ever dips into it
PAPER_LAYER = 0.0009                  # each sheet in a heap sits this much above the one below
FLOOR_Z = 0.0135                      # on the rug (0.012)

# (x, y, yaw degrees) on the desk, world space. Checked against the desk items in the self-check.
EXTRA_CUPS = (
    ("EP4_Cup_1", (0.66, 0.29, 35.0)),
    ("EP4_Cup_2", (-0.53, 0.22, 160.0)),
    ("EP4_Cup_3", (0.28, -0.27, -60.0)),
    ("EP4_Cup_4", (-0.57, -0.28, 100.0)),
)
# name, texture index, (x, y, yaw), layer in its heap
PAPERS = (
    ("EP4_Paper_01", 1, (-0.57, 0.09, 14.0), 0),
    ("EP4_Paper_02", 3, (-0.62, 0.17, -24.0), 1),
    ("EP4_Paper_03", 2, (-0.07, -0.31, 93.0), 0),
    ("EP4_Paper_04", 4, (0.17, -0.31, 97.0), 1),
    ("EP4_Paper_05", 3, (0.63, 0.24, 8.0), 0),
    ("EP4_Paper_06", 1, (0.68, -0.01, 31.0), 2),
    ("EP4_Paper_07", 4, (-0.64, -0.27, 82.0), 0),
    ("EP4_Paper_08", 2, (0.62, 0.19, -38.0), 1),
)
# Sheets that fly off in shot 28: name -> (hit index in ep4.RAGE_HITS, where it leaves the desk (x, y),
# where it lands (x, y, yaw)). They leave over the nearest edge and land on the rug clear of the chair and legs.
FLYING = {
    "EP4_Paper_03": (0, (-0.05, -0.52), (-0.12, -0.52, 128.0)),
    "EP4_Paper_06": (1, (0.92, -0.06), (0.90, -0.20, 70.0)),
    "EP4_Paper_02": (2, (-0.92, 0.20), (-0.98, 0.10, -60.0)),
    "EP4_Paper_04": (2, (0.16, -0.53), (0.30, -0.56, 40.0)),
}
SLIDE_FRAMES = 3                      # the kick off the edge
FALL_FRAMES = 15                      # flutter down to the floor
CUP_HOP = (0.02, 0.04)                # metres, the brief's 2-4 cm
CUP_TIP_DEG = 5.0
PAPER_HOP = 0.004


# ---------------------------------------------------------------- small helpers
def srgb_channel(v):
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def hex_rgba(value):
    value = value.lstrip("#")
    return tuple(srgb_channel(int(value[i:i + 2], 16) / 255) for i in (0, 2, 4)) + (1.0,)


def luminance(rgb):
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


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


def set_interpolation(idb, kind, path_part=None):
    for fc in fcurves_of(idb):
        if path_part is None or path_part in fc.data_path:
            for kp in fc.keyframe_points:
                kp.interpolation = kind


def name_action(idb, name):
    if idb.animation_data and idb.animation_data.action:
        idb.animation_data.action.name = ep4.PREFIX + name


def principled(material):
    return next(n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED")


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def evening_frame(ctx):
    """First frame of the first evening shot, in screen order: the cut where everything changes."""
    return next(s for s in ctx.shots if ctx.is_evening(s["id"]))["first_frame"]


def rage_frames(ctx):
    start = ctx.shot(28)["first_frame"]
    return [start + h for h in ep4.RAGE_HITS]


def key_shown(ob, frame, shown):
    ob.hide_render = ob.hide_viewport = not shown
    ob.keyframe_insert("hide_render", frame=frame)
    ob.keyframe_insert("hide_viewport", frame=frame)


def key_shown_from(ctx, ob, on, off=None):
    """Hidden outside on..off-1, on constant keys."""
    if on > ctx.frame_start:
        key_shown(ob, ctx.frame_start, False)
    key_shown(ob, on, True)
    if off is not None:
        key_shown(ob, off, False)
    set_interpolation(ob, "CONSTANT", "hide_")


def material(name, colour, roughness=0.6, metallic=0.0):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    bsdf = principled(m)
    rgba = hex_rgba(colour) if isinstance(colour, str) else colour
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    m.diffuse_color = rgba
    return m


def box_mesh(name, lo, hi):
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    verts = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
             (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    return mesh


def join_boxes(name, boxes):
    verts, faces = [], []
    for lo, hi in boxes:
        (x0, y0, z0), (x1, y1, z1) = lo, hi
        base = len(verts)
        verts += [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                  (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        faces += [tuple(base + i for i in f) for f in
                  ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    return mesh


def load_image(filename):
    path = ep4.EP / "assets" / filename
    if not path.exists():
        raise FileNotFoundError("%s is missing: run python3 EP/scripts/make_board.py" % path)
    image = bpy.data.images.load(str(path), check_existing=True)
    image.name = ep4.PREFIX + path.stem
    return image


# ---------------------------------------------------------------- scene
def setup_scene(ctx):
    sc = ctx.scene
    sc.name = ep4.SCENE
    sc.render.resolution_x, sc.render.resolution_y = 1080, 1920
    sc.render.resolution_percentage = 100
    sc.render.fps, sc.render.fps_base = ctx.fps, 1.0
    sc.frame_start, sc.frame_end = ctx.frame_start, ctx.frame_end
    sc.render.filepath = RENDER_PATH
    sc.sync_mode = "AUDIO_SYNC"


# ---------------------------------------------------------------- light
def warm_evening():
    """Only the lights that are off in the day change colour, so the day look stays as it is in the studio."""
    lamp = bpy.data.objects[LAMP_B_LIGHT].data
    old = luminance(lamp.color)
    warm = hex_rgba(LAMP_B_WARM)
    lamp.color = warm[:3]
    lamp.energy *= old / luminance(warm)           # same brightness, only the hue moves
    m = bpy.data.materials[LAMP_B_MATERIAL]
    bsdf = principled(m)
    bsdf.inputs["Base Color"].default_value = warm
    bsdf.inputs["Emission Color"].default_value = warm
    m.diffuse_color = warm
    for name, colour in EVENING_WARM.items():
        bpy.data.objects[name].data.color = hex_rgba(colour)[:3]


def key_two_states(owner, path, frame_start, switch, day_value, evening_value):
    setattr(owner, path, day_value)
    owner.keyframe_insert(path, frame=frame_start)
    setattr(owner, path, evening_value)
    owner.keyframe_insert(path, frame=switch)


def build_light(ctx):
    sc = ctx.scene
    switch = evening_frame(ctx)
    for coll_name in LIGHT_SETS:                   # visibility moves from the collections to keys on each light
        coll = bpy.data.collections[coll_name]
        coll.hide_render = coll.hide_viewport = False
    warm_evening()
    for coll_name, belongs_to in LIGHT_SETS.items():
        for ob in list(bpy.data.collections[coll_name].all_objects):   # hiding rebuilds this list: iterate a copy
            if belongs_to == "day":
                key_shown_from(ctx, ob, ctx.frame_start, switch)
            else:
                key_shown_from(ctx, ob, switch)
            name_action(ob, "Light_" + ob.name)

    for name, strength in LAMP_GLOW_STRENGTH.items():
        m = bpy.data.materials[name]
        sock = principled(m).inputs["Emission Strength"]
        key_two_states(sock, "default_value", ctx.frame_start, switch, 0.0, strength)
        set_interpolation(m.node_tree, "CONSTANT")
        name_action(m.node_tree, "Light_" + m.name)

    for m in bpy.data.materials:                   # the city outside the window
        if m.name.startswith("STU_") and m.get("exterior"):
            sock = principled(m).inputs["Emission Color"]
            day, evening = hex_rgba(m["day_color"]), hex_rgba(m["evening_color"])
            key_two_states(sock, "default_value", ctx.frame_start, switch, day, evening)
            key_two_states(m, "diffuse_color", ctx.frame_start, switch, day, evening)
            set_interpolation(m.node_tree, "CONSTANT")
            set_interpolation(m, "CONSTANT")
            name_action(m.node_tree, "Light_" + m.name)
            name_action(m, "Light_view_" + m.name)

    sc["lighting"] = "keyed: day %d-%d, evening with the lamp from %d" % (ctx.frame_start, switch - 1, switch)
    return switch


# ---------------------------------------------------------------- board
def board_surface_material(switch, frame_start):
    m = bpy.data.materials.new(ep4.PREFIX + "Board_Surface")
    try:
        m.use_nodes = True
    except Exception:
        pass
    nodes, links = m.node_tree.nodes, m.node_tree.links
    bsdf = principled(m)
    bsdf.inputs["Roughness"].default_value = 0.42
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = load_image(BOARD_IMAGE)
    tex.interpolation = "Cubic"
    mix = nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.name = mix.label = "Drawn"
    clean = hex_rgba(BOARD_CLEAN)
    mix.inputs[6].default_value = clean                    # A
    links.new(tex.outputs["Color"], mix.inputs[7])         # B
    links.new(mix.outputs[2], bsdf.inputs["Base Color"])
    factor = mix.inputs[0]
    key_two_states(factor, "default_value", frame_start, switch, 0.0, 1.0)
    set_interpolation(m.node_tree, "CONSTANT")
    name_action(m.node_tree, "Board_drawn")
    m.diffuse_color = clean
    return m


def build_board(ctx, switch):
    col = ctx.collection("Board")
    w, h = BOARD_SIZE
    c = Vector(ep4.BOARD_CENTRE)
    # the writing surface, facing the room (-Y), UVs over the whole picture
    hw, hh = w / 2, h / 2
    mesh = bpy.data.meshes.new(ep4.PREFIX + "Board")
    mesh.from_pydata([(-hw, 0, -hh), (hw, 0, -hh), (hw, 0, hh), (-hw, 0, hh)], [], [(0, 1, 2, 3)])
    uv = mesh.uv_layers.new(name="UVMap")
    for loop, xy in zip(mesh.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[loop.index].uv = xy
    mesh.update()
    if mesh.polygons[0].normal.y > 0:                      # face the room
        mesh.flip_normals()
    mesh.materials.append(board_surface_material(switch, ctx.frame_start))
    board = bpy.data.objects.new(ep4.PREFIX + "Board", mesh)
    board.location = c
    board.rotation_euler = (0.0, 0.0, math.radians(ep4.BOARD_YAW_DEG))
    col.objects.link(board)

    metal = material(ep4.PREFIX + "Board_Frame", "#C9CDD2", roughness=0.35, metallic=0.6)
    backing = material(ep4.PREFIX + "Board_Backing", "#E4E4E0", roughness=0.7)
    f, lip, d = BOARD_FRAME, BOARD_LIP, BOARD_DEPTH
    y0, y1 = -lip, d                                       # local: the surface is at y 0, the wall behind +y
    frame = join_boxes(ep4.PREFIX + "Board_Frame", [
        ((-hw - f, y0, hh), (hw + f, y1, hh + f)),
        ((-hw - f, y0, -hh - f), (hw + f, y1, -hh)),
        ((-hw - f, y0, -hh), (-hw, y1, hh)),
        ((hw, y0, -hh), (hw + f, y1, hh)),
    ])
    frame.materials.append(metal)
    ob = bpy.data.objects.new(ep4.PREFIX + "Board_Frame", frame)
    ob.parent = board
    col.objects.link(ob)

    back = box_mesh(ep4.PREFIX + "Board_Backing", (-hw, 0.002, -hh), (hw, d, hh))
    back.materials.append(backing)
    ob = bpy.data.objects.new(ep4.PREFIX + "Board_Backing", back)
    ob.parent = board
    col.objects.link(ob)

    tray = join_boxes(ep4.PREFIX + "Board_Tray", [
        ((-TRAY_LENGTH / 2, -0.045, -hh - f - 0.012), (TRAY_LENGTH / 2, y0, -hh - f)),
        ((-TRAY_LENGTH / 2, -0.045, -hh - f), (TRAY_LENGTH / 2, -0.040, -hh - f + 0.012)),
    ])
    tray.materials.append(metal)
    ob = bpy.data.objects.new(ep4.PREFIX + "Board_Tray", tray)
    ob.parent = board
    col.objects.link(ob)

    # the stand: a post at each end, a foot under each post, a caster at each end of a foot
    px = hw + f + 0.004 + POST / 2
    floor = -c.z
    boxes = []
    for sx in (-1, 1):
        x = sx * px
        boxes.append(((x - POST / 2, d - POST, floor + FOOT_H), (x + POST / 2, d, POST_TOP - c.z)))
        boxes.append(((x - POST / 2, d - POST / 2 - FOOT_FRONT, floor + CASTER), (x + POST / 2, d - POST / 2 + FOOT_BACK,
                                                                                  floor + CASTER + FOOT_H)))
        for y in (d - POST / 2 - FOOT_FRONT + CASTER / 2 + 0.005, d - POST / 2 + FOOT_BACK - CASTER / 2 - 0.005):
            boxes.append(((x - CASTER / 2, y - CASTER / 2, floor), (x + CASTER / 2, y + CASTER / 2, floor + CASTER)))
    stand = join_boxes(ep4.PREFIX + "Board_Stand", boxes)
    stand.materials.append(metal)
    ob = bpy.data.objects.new(ep4.PREFIX + "Board_Stand", stand)
    ob.parent = board
    col.objects.link(ob)

    cap = material(ep4.PREFIX + "Board_Marker_Body", "#F2F2EE", roughness=0.5)
    length = ep4.BOARD_MARKER_GRIP["length"]
    for i, (colour, x) in enumerate(MARKERS):
        name = ep4.PREFIX + "Board_Marker_%d" % (i + 1)
        r = MARKER_THICK / 2
        cap_from = length / 2 - 0.025                     # the coloured end is the tip
        mk = join_boxes(name, [((-length / 2, -r, -r), (cap_from, r, r)), ((cap_from, -r, -r), (length / 2, r, r))])
        mk.materials.append(cap)
        mk.materials.append(material(ep4.PREFIX + "Board_Marker_Cap_%d" % (i + 1), colour, roughness=0.4))
        for poly in mk.polygons[6:]:
            poly.material_index = 1
        ob = bpy.data.objects.new(name, mk)
        ob.parent = board
        ob.location = (x, -0.027, -hh - f + r)            # lying on the tray, tip to the right
        col.objects.link(ob)
    return board


# ---------------------------------------------------------------- shot 16: she draws on the board
def board_frame(ctx, t):
    return ctx.shot(ep4.BOARD_SHOT)["first_frame"] + t


def grip_matrix():
    """The marker object's matrix in hand.R's pose-bone space: its +X (towards the coloured tip) along the grip axis,
    the tip on the grip's tip point."""
    g = ep4.BOARD_MARKER_GRIP
    axis = Vector(g["axis"]).normalized()
    side = Vector((0.0, 0.0, 1.0)).cross(axis)
    if side.length < 1e-6:
        side = Vector((0.0, 1.0, 0.0)).cross(axis)
    side.normalize()
    up = axis.cross(side)
    m = Matrix((axis, side, up)).transposed().to_4x4()      # columns: local x, y, z
    m.translation = Vector(g["tip"]) - axis * g["length"] / 2
    return m


def key_influence(ob, con, frame, value):
    con.influence = value
    ob.keyframe_insert('constraints["%s"].influence' % con.name, frame=frame)


def hand_the_marker(ctx, switch):
    """From the first frame of "pick" the marker rides in her right fist, exactly as BOARD_MARKER_GRIP says; from the
    evening cut it lies on the tray again. Child Of with an inverse that cancels its tray pose."""
    rig = bpy.data.objects[ep4.GIRL_RIG]
    ob = bpy.data.objects[ep4.PREFIX + "Board_Marker_%d" % ep4.BOARD_MARKER]
    bpy.context.view_layer.update()
    con = ob.constraints.new("CHILD_OF")
    con.name = "In her hand"
    con.target = rig
    con.subtarget = "hand.R"
    con.inverse_matrix = grip_matrix() @ ob.matrix_world.inverted()
    pick = board_frame(ctx, ep4.BOARD_BEATS["pick"][0])
    key_influence(ob, con, ctx.frame_start, 0.0)
    key_influence(ob, con, pick - MARKER_TAKE_FRAMES, 0.0)
    key_influence(ob, con, pick, 1.0)
    key_influence(ob, con, switch, 0.0)
    set_interpolation(ob, "CONSTANT", "influence")
    for fc in fcurves_of(ob):                              # the take: tray -> fist over MARKER_TAKE_FRAMES, linear
        for kp in fc.keyframe_points:
            if int(round(kp.co.x)) == pick - MARKER_TAKE_FRAMES:
                kp.interpolation = "LINEAR"
    name_action(ob, "Marker_in_hand")
    return ob


def stroke_material():
    colour = MARKERS[ep4.BOARD_MARKER - 1][0]
    return material(ep4.PREFIX + "Board_Stroke_16", colour, roughness=0.55)


def draw_lines_16(ctx, board, switch):
    """One flat curve per line of BOARD_STROKES_16, on the surface, growing behind the tip frame by frame."""
    col = ctx.collection("Board")
    mat = stroke_material()
    first = ctx.shot(ep4.BOARD_SHOT)["first_frame"]
    a, z = ep4.BOARD_BEATS["draw"]
    lines = []
    for i, stroke in enumerate(ep4.BOARD_STROKES_16):
        name = ep4.PREFIX + "Board_Line16_%d" % (i + 1)
        cu = bpy.data.curves.new(name, "CURVE")
        cu.dimensions = "3D"
        cu.bevel_mode = "ROUND"
        cu.bevel_depth = STROKE_WIDTH / 2
        cu.bevel_resolution = 2
        cu.use_fill_caps = True
        cu.bevel_factor_mapping_start = cu.bevel_factor_mapping_end = "SPLINE"
        sp = cu.splines.new("POLY")
        sp.points.add(len(stroke) - 1)
        for pt, (x, y) in zip(sp.points, stroke):
            pt.co = (x, -STROKE_PROUD / STROKE_FLAT, y, 1.0)
        cu.materials.append(mat)
        ob = bpy.data.objects.new(name, cu)
        ob.parent = board
        ob.scale = (1.0, STROKE_FLAT, 1.0)                   # flat across the board: a line of ink, not a rope
        col.objects.link(ob)
        shares = [(t, ep4.drawn_length_16(t)[i]) for t in range(a, z + 1)]
        starts = next(t for t, v in shares if v > 0)
        for t, v in shares:                                  # every frame of the drawing: the line ends at the tip
            cu.bevel_factor_end = v
            cu.keyframe_insert("bevel_factor_end", frame=first + t)
        set_interpolation(cu, "LINEAR")
        name_action(cu, "Board_Line16_%d_grows" % (i + 1))
        key_shown_from(ctx, ob, first + starts, switch)      # the evening picture has the same lines
        name_action(ob, "Board_Line16_%d_shown" % (i + 1))
        lines.append(ob)
    return lines


# ---------------------------------------------------------------- the evening desk
def desk_local(world_xyz):
    lift = bpy.data.objects[DESK_LIFT]
    return lift.matrix_world.inverted() @ Vector(world_xyz)


def parent_to_lift(ob):
    lift = bpy.data.objects[DESK_LIFT]
    ob.parent = lift
    ob.matrix_parent_inverse = Matrix.Identity(4)


def empty_the_tea(ctx, switch):
    """The tea surface turns invisible in the evening: all five cups are drunk dry."""
    m = bpy.data.materials[TEA_MATERIAL]
    m.surface_render_method = "DITHERED"
    sock = principled(m).inputs["Alpha"]
    key_two_states(sock, "default_value", ctx.frame_start, switch, 1.0, 0.0)
    set_interpolation(m.node_tree, "CONSTANT")
    name_action(m.node_tree, "Tea_drunk")
    steam = bpy.data.objects.get(STEAM)
    if steam is not None:
        key_shown_from(ctx, steam, ctx.frame_start, switch)
        name_action(steam, "Tea_steam_shown")


def build_cups(ctx, switch):
    col = ctx.collection("Props")
    source = bpy.data.objects[ep4.CUP]
    cups = [source]
    for name, (x, y, yaw) in EXTRA_CUPS:
        ob = source.copy()                         # shares the mesh: same cup, same drunk tea
        ob.name = name
        ob.animation_data_clear()
        col.objects.link(ob)
        parent_to_lift(ob)
        ob.location = desk_local((x, y, source.matrix_world.translation.z))
        ob.rotation_euler = Euler((0, 0, math.radians(yaw)))
        key_shown_from(ctx, ob, switch)
        name_action(ob, name[len(ep4.PREFIX):])
        cups.append(ob)
    return cups


def paper_material(index):
    name = ep4.PREFIX + "Paper_%d" % index
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    bsdf = principled(m)
    bsdf.inputs["Roughness"].default_value = 0.8
    tex = m.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = load_image("paper_%d.png" % index)
    m.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    m.diffuse_color = (0.95, 0.95, 0.93, 1.0)
    return m


def paper_mesh(index):
    name = ep4.PREFIX + "Paper_%d" % index
    mesh = bpy.data.meshes.get(name)
    if mesh:
        return mesh
    hx, hy = PAPER_SIZE[0] / 2, PAPER_SIZE[1] / 2
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([(-hx, -hy, 0), (hx, -hy, 0), (hx, hy, 0), (-hx, hy, 0)], [], [(0, 1, 2, 3)])
    uv = mesh.uv_layers.new(name="UVMap")
    for loop, xy in zip(mesh.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[loop.index].uv = xy
    mesh.update()
    mesh.materials.append(paper_material(index))
    return mesh


def paper_rest(x, y, yaw, layer):
    return Vector((x, y, PAPER_Z + layer * PAPER_LAYER)), Euler((0, 0, math.radians(yaw)))


def build_papers(ctx, switch):
    col = ctx.collection("Props")
    papers = {}
    for name, index, (x, y, yaw), layer in PAPERS:
        ob = bpy.data.objects.new(name, paper_mesh(index))
        col.objects.link(ob)
        ob.location, ob.rotation_euler = paper_rest(x, y, yaw, layer)
        ob.rotation_mode = "XYZ"
        ob["rest"] = (x, y, yaw, layer)
        key_shown_from(ctx, ob, switch)
        papers[name] = ob
    return papers


# ---------------------------------------------------------------- the rage in shot 28
def hop_profile():
    """(frame offset from the hit, share of the hop height). The fists land on the hit frame."""
    return ((0, 0.0), (2, 1.0), (4, 0.35), (5, 0.0), (6, 0.12), (7, 0.0))


def key_cup_hops(ctx, cups):
    rnd = random.Random(28)
    hits = rage_frames(ctx)
    for cup in cups:
        base_loc = cup.location.copy()
        base_rot = cup.rotation_euler.copy()
        cup.keyframe_insert("location", frame=hits[0] - 1)
        cup.keyframe_insert("rotation_euler", frame=hits[0] - 1)
        for hit in hits:
            height = rnd.uniform(*CUP_HOP)
            tip = (math.radians(rnd.uniform(-CUP_TIP_DEG, CUP_TIP_DEG)),
                   math.radians(rnd.uniform(-CUP_TIP_DEG, CUP_TIP_DEG)))
            for offset, share in hop_profile():
                cup.location = base_loc + Vector((0, 0, height * share))
                cup.rotation_euler = Euler((base_rot.x + tip[0] * share, base_rot.y + tip[1] * share, base_rot.z))
                cup.keyframe_insert("location", frame=hit + offset)
                cup.keyframe_insert("rotation_euler", frame=hit + offset)
        cup.location, cup.rotation_euler = base_loc, base_rot
        for fc in fcurves_of(cup):
            if fc.data_path in ("location", "rotation_euler"):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
                    kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"
                fc.update()
        name_action(cup, "Rage_" + cup.name.replace(ep4.PREFIX, "").replace("STU_", ""))


def flight_pose(rest_loc, rest_yaw, edge_xy, land, t_frames, sway_sign):
    """Pose at t frames after the hit. Slides to the edge with a little lift, then flutters down and lands flat."""
    lx, ly, lyaw = land
    edge = Vector((edge_xy[0], edge_xy[1], rest_loc.z + 0.03))
    floor = Vector((lx, ly, FLOOR_Z))
    if t_frames <= SLIDE_FRAMES:
        s = t_frames / SLIDE_FRAMES
        loc = rest_loc.lerp(edge, 1 - (1 - s) ** 2)
        tilt = 0.0
        yaw = rest_yaw
    else:
        s = min(1.0, (t_frames - SLIDE_FRAMES) / FALL_FRAMES)
        across = ease(s)
        drop = s ** 1.6                               # accelerates, but air holds it back
        loc = Vector((edge.x + (floor.x - edge.x) * across, edge.y + (floor.y - edge.y) * across,
                      edge.z + (floor.z - edge.z) * drop))
        side = Vector((-(floor.y - edge.y), floor.x - edge.x, 0))
        if side.length:
            loc += side.normalized() * 0.05 * math.sin(math.pi * 2 * s) * (1 - s) * sway_sign
        tilt = math.radians(55) * math.sin(math.pi * s) * sway_sign        # flat again when it lands
        yaw = rest_yaw + (math.radians(lyaw) - rest_yaw) * ease(s)
    return loc, Euler((tilt, tilt * 0.4, yaw))


def key_paper_motion(ctx, papers):
    hits = rage_frames(ctx)
    end = ctx.shot(28)["last_frame"]
    for name, ob in papers.items():
        rest_loc, rest_rot = ob.location.copy(), ob.rotation_euler.copy()
        ob.keyframe_insert("location", frame=hits[0] - 1)
        ob.keyframe_insert("rotation_euler", frame=hits[0] - 1)
        flying = FLYING.get(name)
        stop = hits[flying[0]] if flying else end + 1
        for hit in hits:                               # the heaps jump a little on every hit while it lies there
            if hit >= stop:
                break
            for offset, share in hop_profile():
                if hit + offset >= stop:
                    break
                ob.location = rest_loc + Vector((0, 0, PAPER_HOP * share))
                ob.keyframe_insert("location", frame=hit + offset)
        if flying:
            hit_index, edge_xy, land = flying
            hit = hits[hit_index]
            sway = 1 if hit_index % 2 == 0 else -1
            for t in range(0, SLIDE_FRAMES + FALL_FRAMES + 1):
                loc, rot = flight_pose(rest_loc, rest_rot.z, edge_xy, land, t, sway)
                ob.location, ob.rotation_euler = loc, rot
                ob.keyframe_insert("location", frame=hit + t)
                ob.keyframe_insert("rotation_euler", frame=hit + t)
            set_interpolation(ob, "LINEAR", "location")
            set_interpolation(ob, "LINEAR", "rotation")
        ob.location, ob.rotation_euler = rest_loc, rest_rot
        name_action(ob, "Rage_" + name[len(ep4.PREFIX):])


def build_props(ctx, switch):
    empty_the_tea(ctx, switch)
    cups = build_cups(ctx, switch)
    papers = build_papers(ctx, switch)
    key_cup_hops(ctx, cups)
    key_paper_motion(ctx, papers)


# ---------------------------------------------------------------- sound
def build_sound(ctx):
    sc = ctx.scene
    editor = sc.sequence_editor or sc.sequence_editor_create()
    strips = editor.strips if hasattr(editor, "strips") else editor.sequences
    for line in ctx.lines():
        path = ctx.audio_path(line)
        strip = strips.new_sound(name="%sVO_%s" % (ep4.PREFIX, line["id"]), filepath=str(path),
                                 channel=VOICE_CHANNELS[line["who"]], frame_start=line["first_frame"])
        spoken_to = strip.frame_final_end - 1
        if spoken_to > line["last_frame"] + 1:
            print("stage: %s runs to %d, the timeline says %d" % (line["id"], spoken_to, line["last_frame"]))
    for channel, effect in enumerate(ctx.all_sfx(), SFX_FIRST_CHANNEL):
        strip = strips.new_sound(name="%sSFX_%s" % (ep4.PREFIX, effect["id"]), filepath=str(ctx.audio_path(effect)),
                                 channel=channel, frame_start=effect["first_frame"])
        strip.volume = effect["gain"]


def move_plant():
    """The plant in the back right corner stood between the frontal camera and the board: it goes forward along the
    right wall, keeping its height and turn."""
    plant = bpy.data.objects[PLANT]
    pts = [plant.matrix_world @ Vector(c) for c in plant.bound_box]
    centre = Vector(((min(p.x for p in pts) + max(p.x for p in pts)) / 2, (min(p.y for p in pts) + max(p.y for p in pts)) / 2))
    shift = PLANT_SPOT - centre
    plant.location += Vector((shift.x, shift.y, 0.0))


def build(ctx):
    setup_scene(ctx)
    move_plant()
    switch = build_light(ctx)
    board = build_board(ctx, switch)
    draw_lines_16(ctx, board, switch)
    hand_the_marker(ctx, switch)
    build_props(ctx, switch)
    build_sound(ctx)
    ctx.scene.frame_set(ctx.frame_start)
