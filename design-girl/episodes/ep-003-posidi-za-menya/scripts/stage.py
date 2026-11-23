"""EP3 stage: scene and render settings, day/evening light, one camera per shot, voice strips.

Light    day until the timelapse at the end of shot 8, then one value per frame blends the lights, world, lamp glow and
         city colours through a golden sunset. Its last frame is already the evening look that shot 9 starts on.
         The studio's lamp fades to lilac and its evening fills are blue; here they are warmed up.
Cameras  EP3_Cam_NN, bound to timeline markers. Her close-ups, Clawd's close-ups and the side shot stay on the window
         side of the line between them, so she looks screen right and he looks screen left. The frontal shots
         (11, 12, 22, 26, 27) and the wides look at the room from the front. Shots 1 and 3 are a real camera on the laptop.
         Shot 0 pushes in on the whole room. Shot 2 holds her face and her hand on the keyboard in one frame.
         Shots 11-12 are one move: camera 12 starts exactly where 11 ends, then dollies in while the lens opens.
         Shots 26-27 are one push from behind the laptop lid: the screen is never seen, her face is.
Gold     shots 26-27 only: an area light at the screen, a soft halo around the lid and slightly dimmer room lights, all
         on constant keys, so shot 28 is exactly the normal evening.
Sound    one strip per voice line: her on channel 2, Clawd on 3, Viktor on 4. Each sound effect has its own channel from 5.
"""
import math

import bpy
from mathutils import Matrix, Vector

import ep3

RENDER_PATH = "//renders/ep-003_"
VOICE_CHANNELS = {"girl": 2, "claude": 3, "viktor": 4}
SFX_FIRST_CHANNEL = 5

LIGHT_SETS = {"STU_Lights_Day": "day", "STU_Lights_Evening": "evening", "STU_Lights_Lamp": "evening"}
LAMP_GLOW_STRENGTH = {"STU_lamp_glow": 6.0, "STU_lamp_glow_B": 6.0}  # EMISSION in studio.py

LAMP_B_LIGHT = "STU_Lamp_Light_B"
LAMP_B_MATERIAL = "STU_lamp_glow_B"
LAMP_B_WARM = "#F7CDA4"               # the studio default is lilac (#C9A7F0)
EVENING_WARM = {"STU_Glow_Laptop": "#FFEBD8", "STU_Glow_Tablet": "#FFEBD8", "STU_Evening_Fill": "#C4A9A6"}

SUNSET_GOLD = "#FFAE5A"               # the colour the daylight warms to on its way out
SUNSET_TINT = (1.0, 0.82, 0.55, 1.0)  # how far the sky, city and world lean to gold in the middle of the timelapse
DAYLIGHT_WARM_BY = 0.55               # share of the timelapse at which the daylight has fully turned gold
EVENING_LIGHTS_FROM = 0.35            # the screen glows and evening fill start to come up here
LAMP_ON_FROM = 2 / 3                  # the lamp comes on in the last third
CITY_WINDOWS_FROM = 0.6               # the lit windows in the city come on here

MOVE_KEY_STEP = 3                     # a camera move is sampled every few frames, already eased
FISHEYE_SHOTS = (11, 12)
FACE_ON_HEAD = Vector((0.0, -0.242, 0.20))   # between her eyes, in the head mesh's space
FISHEYE_MOVE_FRAMES = 24              # how long camera 12 takes to reach the fisheye
FISHEYE_CREEP = 0.05                  # then it keeps drifting this share closer, so the silent hold is not a dead freeze
PORTRAIT_SENSOR_WIDTH = 36.0 * 9 / 16 # with AUTO sensor fit the 36 mm side is the frame's height
LAPTOP_CAM_DISTANCE = 0.46            # square on to the screen, still in front of her face
LAPTOP_FRAME_MARGIN = 1.05            # frame width / laptop width: the lid fills the frame edge to edge
LAPTOP_FRAME_DROP = 0.03              # the frame sits this far below the screen, to show the laptop body and desk

PAYOFF_SHOTS = (26, 27)               # one push from behind the lid, with an invisible cut
PAYOFF_LENS = 19                      # wide enough for her head, both fists and the sparkles
PAYOFF_AT_LINE = 0.92                 # share of the push done when «Красиво» starts: the lid is low enough for her fists
PAYOFF_DRIFT = 0.10                   # share of the push spread evenly over both shots, so it never quite stops

GOLD_COLOUR = "#FFC861"
GOLD_PEAK_WATTS = 3.2                 # the one number to change if the glow on her face is too weak or too strong
GOLD_GROW_FRAMES = 16                 # from nothing to GOLD_BUILD at the start of shot 26
GOLD_BUILD = 0.7                      # share of the peak after the first growth; the rest arrives on «Красиво»
GOLD_TAIL = 0.1                       # what is left on the last frame of shot 27, before the hard off
GOLD_OFF_SCREEN = 0.03                # the light sits this far in front of the screen images, so they don't shadow it
ROOM_DIM = 0.75                       # room lights during shots 26-27
HALO_WIDTH = 0.018                    # reach beyond the lid's edge, metres
HALO_TUCK = 0.008                     # the halo starts this far behind the lid's edge, so no seam shows
HALO_CORNER = 0.018
HALO_TAPER = 0.07                     # both ends of the horseshoe thin out over this length
HALO_STRENGTH = 1.2                   # emission at the lid's edge at the glow's peak


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


def set_interpolation(idb, kind):
    for fc in fcurves_of(idb):
        for kp in fc.keyframe_points:
            kp.interpolation = kind


def name_action(idb, name):
    if idb.animation_data and idb.animation_data.action:
        idb.animation_data.action.name = ep3.PREFIX + name


def principled(material):
    return next(n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED")


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- scene
def setup_scene(ctx):
    sc = ctx.scene
    sc.name = ep3.SCENE
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


def timelapse_frames(ctx):
    shot = ctx.shot(8)
    count = round(shot["transition"]["seconds"] * ctx.fps)
    return shot["last_frame"] - count + 1, shot["last_frame"]


def rise(u, start):
    return ease((u - start) / (1 - start))


def mix(a, b, s):
    return tuple(x + (y - x) * s for x, y in zip(a, b))


def sunset_tint(colour, u):
    """Leans to gold in the middle and is exactly the colour itself at both ends."""
    glow = 4 * u * (1 - u)
    return tuple(min(1.0, x * (1 + (t - 1) * glow)) for x, t in zip(colour, SUNSET_TINT))


def city_colour(m, u):
    day, evening = hex_rgba(m["day_color"]), hex_rgba(m["evening_color"])
    if "_win_lit" not in m.name:
        return sunset_tint(mix(day, evening, ease(u)), u)
    dark = hex_rgba(bpy.data.materials[m.name.replace("_win_lit", "_win_dark")]["evening_color"])
    return mix(sunset_tint(mix(day, dark, ease(u)), u), evening, rise(u, CITY_WINDOWS_FROM))


def light_energy(coll_name, full, u):
    if coll_name == "STU_Lights_Day":
        return full * (1 - ease(u))
    return full * rise(u, LAMP_ON_FROM if coll_name == "STU_Lights_Lamp" else EVENING_LIGHTS_FROM)


def key_light_state(ob, coll_name, full, day_colour, frames_u):
    data = ob.data
    gold = hex_rgba(SUNSET_GOLD)[:3]
    for frame, u in frames_u:
        data.energy = light_energy(coll_name, full, u)
        data.keyframe_insert("energy", frame=frame)
        if coll_name == "STU_Lights_Day":
            data.color = mix(day_colour, gold, ease(u / DAYLIGHT_WARM_BY))
            data.keyframe_insert("color", frame=frame)


def key_shown_from(ob, frame_start, on, off=None):
    """Hidden outside on..off. Each light is on from the first frame it can add anything."""
    keys = [(frame_start, True), (on, False)] if on > frame_start else [(frame_start, False)]
    if off is not None:
        keys.append((off, True))
    for frame, hidden in keys:
        ob.hide_render = ob.hide_viewport = hidden
        ob.keyframe_insert("hide_render", frame=frame)
        ob.keyframe_insert("hide_viewport", frame=frame)


def build_light(ctx):
    """Returns each evening light's full energy: the gold payoff dims the room from these values."""
    sc = ctx.scene
    for coll_name in LIGHT_SETS:                   # visibility moves from the collections to keys on each light
        coll = bpy.data.collections[coll_name]
        coll.hide_render = coll.hide_viewport = False
    warm_evening()
    first, last = timelapse_frames(ctx)
    frames_u = [(ctx.frame_start, 0.0)] + [(f, (f - first + 1) / (last - first + 1)) for f in range(first, last + 1)]

    evening_energy = {}
    for coll_name, belongs_to in LIGHT_SETS.items():
        for ob in list(bpy.data.collections[coll_name].all_objects):   # hiding rebuilds this list: iterate a copy
            full, day_colour = ob.data.energy, tuple(ob.data.color)
            key_light_state(ob, coll_name, full, day_colour, frames_u)
            if belongs_to == "day":
                key_shown_from(ob, ctx.frame_start, ctx.frame_start, last)     # already at zero on the last frame
            else:
                key_shown_from(ob, ctx.frame_start, first)
                evening_energy[ob.name] = full
            set_interpolation(ob, "CONSTANT")
            set_interpolation(ob.data, "CONSTANT")
            name_action(ob, "Light_" + ob.name)
            name_action(ob.data, "Light_values_" + ob.name)

    for name, strength in LAMP_GLOW_STRENGTH.items():
        m = bpy.data.materials[name]
        sock = principled(m).inputs["Emission Strength"]
        for frame, u in frames_u:
            sock.default_value = strength * rise(u, LAMP_ON_FROM)
            sock.keyframe_insert("default_value", frame=frame)
        set_interpolation(m.node_tree, "CONSTANT")
        name_action(m.node_tree, "Light_" + m.name)

    for m in bpy.data.materials:                   # the city outside the window
        if m.name.startswith("STU_") and m.get("exterior"):
            sock = principled(m).inputs["Emission Color"]
            for frame, u in frames_u:
                colour = city_colour(m, u)
                sock.default_value = colour
                sock.keyframe_insert("default_value", frame=frame)
                m.diffuse_color = colour
                m.keyframe_insert("diffuse_color", frame=frame)
            set_interpolation(m.node_tree, "CONSTANT")
            set_interpolation(m, "CONSTANT")
            name_action(m.node_tree, "Light_" + m.name)
            name_action(m, "Light_view_" + m.name)

    world = sc.world
    sock = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND").inputs["Color"]
    base = tuple(sock.default_value)               # the studio's world is the same by day and by evening
    for frame, u in frames_u:
        sock.default_value = sunset_tint(base, u)
        sock.keyframe_insert("default_value", frame=frame)
    set_interpolation(world.node_tree, "CONSTANT")
    name_action(world.node_tree, "Light_World")

    sc["lighting"] = "keyed: day, timelapse %d-%d, evening" % (first, last)
    sc.frame_set(ctx.frame_start)
    return evening_energy


# ---------------------------------------------------------------- cameras
def aim(loc, target):
    direction = (Vector(target) - Vector(loc)).normalized()
    return direction.to_track_quat("-Z", "Y").to_euler("XYZ")


def set_pose(ob, loc, target):
    ob.location = Vector(loc)
    ob.rotation_euler = aim(loc, target).copy()


def key_pose(ob, frame, loc, target):
    ob.location = Vector(loc)
    ob.rotation_euler = aim(loc, target).to_matrix().to_euler("XYZ", ob.rotation_euler)
    ob.keyframe_insert("location", frame=frame)
    ob.keyframe_insert("rotation_euler", frame=frame)


def key_move(ob, a, b, pose_at):
    frames = list(range(a, b + 1, MOVE_KEY_STEP))
    if frames[-1] != b:
        frames.append(b)
    for f in frames:
        key_pose(ob, f, *pose_at(f))
    set_interpolation(ob, "LINEAR")
    name_action(ob, ob.name[len(ep3.PREFIX):])


def stage_points(ctx):
    sc = ctx.scene
    sc.frame_set(ctx.frame_start)
    dg = bpy.context.evaluated_depsgraph_get()
    head = bpy.data.objects["STU_Designer_Head"].evaluated_get(dg)
    face = head.matrix_world @ FACE_ON_HEAD                   # seated
    screen = bpy.data.objects[ep3.SCREEN]
    wide = bpy.data.objects["STU_Cam_Wide"]
    laptop = bpy.data.objects["STU_Laptop"]
    laptop_x = [(laptop.matrix_world @ Vector(c)).x for c in laptop.bound_box]
    centre = screen.matrix_world.translation.copy()
    axes = screen.matrix_world.to_3x3()
    side, up, normal = ((axes @ Vector(a)).normalized() for a in ((1, 0, 0), (0, 0, 1), (0, -1, 0)))
    lid = [laptop.matrix_world @ v.co - centre for v in laptop.data.vertices]
    lid = [v for v in lid if abs(v.dot(normal)) < 0.02]       # the base lies far from the screen's plane
    return dict(
        face=face.copy(),
        head=face + Vector((0.0, 0.087, 0.046)),              # middle of her big head: what a close-up centres on
        clawd=bpy.data.objects["STU_Claude_Dock_Anchor"].matrix_world.translation + Vector((0, 0, 0.09)),
        screen=screen.matrix_world.translation.copy(),
        screen_normal=(screen.matrix_world.to_3x3() @ Vector((0, -1, 0))).normalized(),
        screen_up=(screen.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized(),
        laptop_width=max(laptop_x) - min(laptop_x),
        screen_side=side,
        lid_half_width=max(abs(v.dot(side)) for v in lid),
        lid_top=max(v.dot(up) for v in lid),
        lid_bottom=min(v.dot(up) for v in lid),
        lid_front=max(v.dot(normal) for v in lid),
        wide=wide.matrix_world.translation.copy(),
        wide_forward=(wide.matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized(),
        clip_end=wide.data.clip_end,
    )


def shot_setups(p):
    """shot id -> dict(loc, target, lens, and for a move: to_loc, to_target)."""
    head, face, clawd = p["head"], p["face"], p["clawd"]
    her_loc = head + Vector((-0.68, -0.62, 0.11))             # off her line to Clawd: turned to him, she misses the lens
    her = dict(loc=her_loc, target=head, lens=32)
    claude = dict(loc=clawd + Vector((0.01, 0.25, 0.04)), target=clawd, lens=24)
    lid_edge = p["screen"] + p["screen_up"] * p["lid_top"]
    payoff = dict(loc=Vector((face.x, lid_edge.y - 0.30, lid_edge.z + 0.105)),   # her chin just clears the lid
                  target=Vector((face.x, 0.42, 1.20)), lens=PAYOFF_LENS,
                  to_loc=Vector((face.x, lid_edge.y - 0.10, lid_edge.z + 0.085)),  # close: the lid sinks below her fists
                  to_target=Vector((face.x, 0.44, 1.10)))
    laptop_centre = p["screen"] - p["screen_up"] * LAPTOP_FRAME_DROP
    laptop_lens = PORTRAIT_SENSOR_WIDTH * LAPTOP_CAM_DISTANCE / (p["laptop_width"] * LAPTOP_FRAME_MARGIN)
    on_laptop = dict(loc=laptop_centre + p["screen_normal"] * LAPTOP_CAM_DISTANCE, target=laptop_centre, lens=laptop_lens)
    wide_target = p["wide"] + p["wide_forward"] * 3.0
    wide = dict(loc=p["wide"], target=wide_target, lens=26)
    hands_target = head + Vector((0.0, -0.07, -0.14))         # face and the keyboard in one frame
    hands_loc = head + Vector((-0.70, -0.64, 0.08))
    key_hand = Vector((-0.13, 0.19, 0.80))                    # her right hand on the keyboard
    press_target = head.lerp(key_hand, 0.46) + Vector((-0.05, 0.06, 0.0))   # her face above, the pressing hand below
    press_loc = head + Vector((-0.78, -0.70, 0.05))
    her_cu_push = dict(her, to_loc=her_loc.lerp(face, 0.08), to_target=head.lerp(face, 0.4), steady=True)

    setups = {
        # the whole room, then closer on the two of them at the desk
        0: dict(wide, to_loc=p["wide"] + p["wide_forward"] * 0.6, to_target=Vector((clawd.x / 2, 0.25, 1.12))),
        1: on_laptop, 3: on_laptop, 26: payoff, 27: payoff,
        2: dict(loc=press_loc, target=press_target, lens=26,
                to_loc=press_loc.lerp(press_target, 0.08), to_target=press_target, steady=True),
        4: her, 20: her,
        6: dict(loc=her_loc, target=head + Vector((0, 0, 0.10)), lens=27),      # room above her: she is getting up
        5: claude, 7: claude, 10: claude, 15: claude, 24: claude, 28: claude, 30: claude,
        8: wide, 9: wide, 29: wide,
        31: dict(wide, loc=p["wide"] + p["wide_forward"] * 0.15, target=wide_target + p["wide_forward"] * 0.15,
                 to_loc=p["wide"], to_target=wide_target),
        11: dict(loc=Vector((-0.10, -0.95, 1.32)), target=face, lens=40, clip_start=0.005),
        # no real fisheye in EEVEE: a very short lens a hand away from her nose bends her face the same way
        12: dict(loc=face + Vector((-0.03, -0.23, 0.02)), target=face, lens=9, clip_start=0.005),
        18: her_cu_push,
        # from beside her right shoulder: Clawd faces her in this shot, so his face reads from her side of the desk
        19: dict(loc=Vector((-0.82, 0.66, 1.12)), target=Vector((-0.16, 0.12, 0.97)), lens=21),
        21: dict(loc=clawd + Vector((-0.06, 0.25, -0.105)), target=clawd + Vector((0, 0, 0.03)), lens=22,
                 to_loc=clawd + Vector((-0.05, 0.19, -0.102)), to_target=clawd + Vector((0, 0, 0.03))),
        22: dict(loc=Vector((clawd.x / 2, -1.30, 1.34)), target=Vector((clawd.x / 2, 0.10, 1.03)), lens=36),
        23: dict(loc=hands_loc, target=hands_target, lens=28),
        25: dict(loc=hands_loc, target=head + Vector((0.0, -0.05, -0.08)), lens=31),
    }
    return setups


def make_camera(ctx, shot_id, setup, clip_end):
    name = ep3.camera_name(shot_id)
    data = bpy.data.cameras.new(name)
    data.lens = setup["lens"]
    data.sensor_fit = "AUTO"
    data.sensor_width = 36.0
    data.clip_start = setup.get("clip_start", 0.01)
    data.clip_end = clip_end
    ob = bpy.data.objects.new(name, data)
    ctx.collection("Cameras").objects.link(ob)
    ob.rotation_mode = "XYZ"
    set_pose(ob, setup["loc"], setup["target"])
    return ob


def carried_pose(ctx, shot_ids, setup, profile):
    """Two shots read one move measured in frames on screen: the second shot's first frame is the first shot's last."""
    first, second = (ctx.shot(i) for i in shot_ids)
    in_first = first["last_frame"] - first["first_frame"]
    total = in_first + second["last_frame"] - second["first_frame"]

    def pose(f):
        on_screen = f - first["first_frame"] if f <= first["last_frame"] else in_first + f - second["first_frame"]
        s = profile(on_screen / total)
        return setup["loc"].lerp(setup["to_loc"], s), setup["target"].lerp(setup["to_target"], s)

    return pose


def payoff_profile(ctx):
    """Eases off the cut, has PAYOFF_AT_LINE of the push done on the first frame of «Красиво», then keeps drifting."""
    first, second = (ctx.shot(i) for i in PAYOFF_SHOTS)
    in_first = first["last_frame"] - first["first_frame"]
    total = in_first + second["last_frame"] - second["first_frame"]
    at_line = (in_first + ctx.line("v21")["first_frame"] - second["first_frame"]) / total

    def shape(t, settle):
        return (1 - PAYOFF_DRIFT) * ease(t / settle) + PAYOFF_DRIFT * t

    low, high = at_line, 1.0                       # the latest settle point that still reaches the share in time
    for _ in range(30):
        middle = (low + high) / 2
        if shape(at_line, middle) >= PAYOFF_AT_LINE:
            low = middle
        else:
            high = middle
    return lambda t: shape(max(0.0, min(1.0, t)), low)


def make_face_target(ctx):
    """An empty riding on her head, so the fisheye move keeps her face centred whatever her pose is."""
    ob = bpy.data.objects.new(ep3.PREFIX + "Face_Target", None)
    ob.empty_display_size = 0.02
    ctx.collection("Cameras").objects.link(ob)
    ob.parent = bpy.data.objects["STU_Designer_Head"]
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.location = FACE_ON_HEAD
    return ob


def slow_start(t):
    """Barely moves at first, so the push in shot 11 is gentle and the cut to 12 lands while it is still slow."""
    t = max(0.0, min(1.0, t))
    return (t * t * t * (t * (6 * t - 15) + 10)) ** 3


def build_fisheye_move(ctx, cam_11, cam_12, start, end, face):
    """One move across the cut. The last frame of 11 and the first frame of 12 are the same camera state.
    Distance and lens change by ratio, so her face grows steadily while the room bends around it."""
    first, second = ctx.shot(11), ctx.shot(12)
    in_11 = first["last_frame"] - first["first_frame"]
    in_12 = min(FISHEYE_MOVE_FRAMES, second["last_frame"] - second["first_frame"])
    run = in_11 + in_12
    from_face, to_face = start["loc"] - face, end["loc"] - face

    def key(ob, frame, index, closer=1.0):
        s = slow_start(index / run)
        direction = from_face.normalized().lerp(to_face.normalized(), s).normalized()
        ob.location = face + direction * (from_face.length * (to_face.length / from_face.length) ** s) * closer
        ob.data.lens = start["lens"] * (end["lens"] / start["lens"]) ** s
        ob.keyframe_insert("location", frame=frame)
        ob.data.keyframe_insert("lens", frame=frame)

    for offset in range(in_11 + 1):
        key(cam_11, first["first_frame"] + offset, offset)
    for offset in range(in_12 + 1):
        key(cam_12, second["first_frame"] + offset, in_11 + offset)
    key(cam_12, second["last_frame"], run, 1 - FISHEYE_CREEP)

    target = make_face_target(ctx)
    for ob in (cam_11, cam_12):
        track = ob.constraints.new("TRACK_TO")
        track.target = target
        track.track_axis, track.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"
        set_interpolation(ob, "LINEAR")
        set_interpolation(ob.data, "LINEAR")
        name_action(ob, ob.name[len(ep3.PREFIX):])
        name_action(ob.data, ob.name[len(ep3.PREFIX):] + "_lens")


def build_cameras(ctx):
    sc = ctx.scene
    points = stage_points(ctx)
    setups = shot_setups(points)
    cameras = {}
    for shot in ctx.shots:
        sid = shot["id"]
        setup = setups[sid]
        ob = make_camera(ctx, sid, setup, points["clip_end"])
        cameras[sid] = ob
        a, b = shot["first_frame"], shot["last_frame"]
        if sid in PAYOFF_SHOTS:
            key_move(ob, a, b, carried_pose(ctx, PAYOFF_SHOTS, setup, payoff_profile(ctx)))
        elif sid not in FISHEYE_SHOTS and "to_loc" in setup:
            def pose(f, s=setup, a=a, b=b):
                t = (f - a) / max(1, b - a)
                t = t if s.get("steady") else ease(t)
                return s["loc"].lerp(s["to_loc"], t), Vector(s["target"]).lerp(s["to_target"], t)
            key_move(ob, a, b, pose)
        marker = sc.timeline_markers.new("%sS%02d" % (ep3.PREFIX, sid), frame=a)
        marker.camera = ob
    build_fisheye_move(ctx, cameras[11], cameras[12], setups[11], setups[12], points["face"])
    sc.camera = cameras[ctx.shots[0]["id"]]
    return cameras


# ---------------------------------------------------------------- the gold glow of shots 26-27
def gold_level(ctx, f):
    """0 to 1 on any frame: grows in shot 26, peaks on «Красиво», fades on «А корпоратив?», zero outside the two shots."""
    start, end = ctx.shot(PAYOFF_SHOTS[0])["first_frame"], ctx.shot(PAYOFF_SHOTS[1])["last_frame"]
    if f < start or f > end:
        return 0.0
    grown = start + GOLD_GROW_FRAMES
    line = ctx.line("v21")["first_frame"]
    phrase = ctx.line("v27")["first_frame"]
    if f <= grown:
        return GOLD_BUILD * ease((f - start) / GOLD_GROW_FRAMES)
    if f < line:
        return GOLD_BUILD + (1 - GOLD_BUILD) * ease((f - grown) / max(1, line - grown))
    if f < phrase:
        return 1.0
    return 1 + (GOLD_TAIL - 1) * ease((f - phrase) / max(1, end - phrase))


def halo_strip(p):
    """Inner and outer points of a horseshoe around the lid's sides and top, in (side, up) on the lid's plane."""
    x = p["lid_half_width"] - HALO_TUCK
    top = p["lid_top"] - HALO_TUCK
    bottom = p["lid_bottom"] + HALO_TAPER / 2
    r = HALO_CORNER
    path = [(-x, bottom + (top - r - bottom) * i / 8, -1.0, 0.0) for i in range(8)]
    for i in range(7):
        a = math.pi - (math.pi / 2) * i / 6
        path.append((-x + r + r * math.cos(a), top - r + r * math.sin(a), math.cos(a), math.sin(a)))
    path += [(-x + r + (2 * x - 2 * r) * i / 12, top, 0.0, 1.0) for i in range(1, 12)]
    for i in range(7):
        a = (math.pi / 2) * (1 - i / 6)
        path.append((x - r + r * math.cos(a), top - r + r * math.sin(a), math.cos(a), math.sin(a)))
    path += [(x, top - r - (top - r - bottom) * i / 8, 1.0, 0.0) for i in range(1, 9)]
    lengths = [0.0]
    for q0, q1 in zip(path, path[1:]):
        lengths.append(lengths[-1] + math.hypot(q1[0] - q0[0], q1[1] - q0[1]))
    inner, outer = [], []
    for (u, v, nu, nv), run in zip(path, lengths):
        width = (HALO_WIDTH + HALO_TUCK) * ease(min(run, lengths[-1] - run) / HALO_TAPER)
        inner.append((u, v))
        outer.append((u + nu * width, v + nv * width))
    return inner, outer


def halo_material():
    m = bpy.data.materials.new(ep3.PREFIX + "Gold_Halo")
    try:
        m.use_nodes = True
    except Exception:
        pass
    m.surface_render_method = "BLENDED"
    nodes, links = m.node_tree.nodes, m.node_tree.links
    nodes.clear()
    coords = nodes.new("ShaderNodeTexCoord")
    split = nodes.new("ShaderNodeSeparateXYZ")
    inverse = nodes.new("ShaderNodeMath")
    inverse.operation = "SUBTRACT"
    inverse.inputs[0].default_value = 1.0
    falloff = nodes.new("ShaderNodeMath")
    falloff.operation = "POWER"
    falloff.inputs[1].default_value = 2.0
    level = nodes.new("ShaderNodeMath")
    level.operation = "MULTIPLY"
    level.name = "Gold_Level"
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = hex_rgba(GOLD_COLOUR)
    clear = nodes.new("ShaderNodeBsdfTransparent")
    add = nodes.new("ShaderNodeAddShader")                     # light is added over whatever is behind it
    out = nodes.new("ShaderNodeOutputMaterial")
    links.new(coords.outputs["UV"], split.inputs[0])
    links.new(split.outputs["Y"], inverse.inputs[1])
    links.new(inverse.outputs[0], falloff.inputs[0])
    links.new(falloff.outputs[0], level.inputs[0])
    links.new(level.outputs[0], emission.inputs["Strength"])
    links.new(clear.outputs[0], add.inputs[0])
    links.new(emission.outputs[0], add.inputs[1])
    links.new(add.outputs[0], out.inputs["Surface"])
    return m, level.inputs[1]


def make_halo(ctx, p):
    inner, outer = halo_strip(p)
    place = lambda q: p["screen"] + p["screen_side"] * q[0] + p["screen_up"] * q[1] + p["screen_normal"] * (p["lid_front"] + 0.002)
    count = len(inner)
    verts = [place(q) for q in inner] + [place(q) for q in outer]
    faces = [(i, i + 1, count + i + 1, count + i) for i in range(count - 1)]
    mesh = bpy.data.meshes.new(ep3.PREFIX + "Gold_Halo")
    mesh.from_pydata([tuple(v) for v in verts], [], faces)
    uv = mesh.uv_layers.new(name="UVMap")
    for poly in mesh.polygons:
        for loop in poly.loop_indices:
            index = mesh.loops[loop].vertex_index
            uv.data[loop].uv = ((index % count) / max(1, count - 1), 0.0 if index < count else 1.0)
    mesh.update()
    material, strength = halo_material()
    mesh.materials.append(material)
    ob = bpy.data.objects.new(ep3.PREFIX + "Gold_Halo", mesh)
    ob.visible_shadow = False
    ctx.collection("Gold").objects.link(ob)
    return ob, material, strength


def make_gold_light(ctx, p):
    data = bpy.data.lights.new(ep3.PREFIX + "Gold_Glow", "AREA")
    data.shape = "RECTANGLE"
    data.size = 2 * p["lid_half_width"] * 0.9
    data.size_y = (p["lid_top"] - p["lid_bottom"]) * 0.8
    data.color = hex_rgba(GOLD_COLOUR)[:3]
    data.energy = 0.0
    ob = bpy.data.objects.new(ep3.PREFIX + "Gold_Glow", data)
    ob.location = p["screen"] + p["screen_normal"] * GOLD_OFF_SCREEN
    ob.rotation_euler = p["screen_normal"].to_track_quat("-Z", "Y").to_euler("XYZ")   # an area light shines along its -Z
    ctx.collection("Gold").objects.link(ob)
    return ob


def key_shown(ob, frame, shown):
    ob.hide_render = ob.hide_viewport = not shown
    ob.keyframe_insert("hide_render", frame=frame)
    ob.keyframe_insert("hide_viewport", frame=frame)


def dim_room(start, after, evening_energy):
    for name, full in evening_energy.items():
        data = bpy.data.objects[name].data
        for frame, energy in ((start, full * ROOM_DIM), (after, full)):
            data.energy = energy
            data.keyframe_insert("energy", frame=frame)
        set_interpolation(data, "CONSTANT")


def build_gold(ctx, evening_energy):
    points = stage_points(ctx)
    start = ctx.shot(PAYOFF_SHOTS[0])["first_frame"]
    end = ctx.shot(PAYOFF_SHOTS[1])["last_frame"]
    after = ctx.shot(28)["first_frame"]
    light = make_gold_light(ctx, points)
    halo, material, strength = make_halo(ctx, points)
    for frame in [ctx.frame_start] + list(range(start, end + 1)) + [after]:
        level = gold_level(ctx, frame)
        light.data.energy = GOLD_PEAK_WATTS * level
        light.data.keyframe_insert("energy", frame=frame)
        strength.default_value = HALO_STRENGTH * level
        strength.keyframe_insert("default_value", frame=frame)
    for ob in (light, halo):
        key_shown(ob, ctx.frame_start, False)
        key_shown(ob, start, True)
        key_shown(ob, after, False)
        set_interpolation(ob, "CONSTANT")
        name_action(ob, ob.name[len(ep3.PREFIX):] + "_shown")
    set_interpolation(light.data, "CONSTANT")
    set_interpolation(material.node_tree, "CONSTANT")
    name_action(light.data, "Gold_Glow_energy")
    name_action(material.node_tree, "Gold_Halo_level")
    dim_room(start, after, evening_energy)
    ctx.scene.frame_set(ctx.frame_start)


# ---------------------------------------------------------------- sound
def build_sound(ctx):
    sc = ctx.scene
    editor = sc.sequence_editor or sc.sequence_editor_create()
    strips = editor.strips if hasattr(editor, "strips") else editor.sequences
    for line in ctx.lines():
        path = ctx.audio_path(line)
        strip = strips.new_sound(name="%sVO_%s" % (ep3.PREFIX, path.stem), filepath=str(path),
                                 channel=VOICE_CHANNELS[line["who"]], frame_start=line["first_frame"])
        spoken_to = strip.frame_final_end - 1
        if spoken_to > line["last_frame"] + 1:
            print("stage: %s runs to %d, the timeline says %d" % (line["id"], spoken_to, line["last_frame"]))
    for channel, effect in enumerate(ctx.all_sfx(), SFX_FIRST_CHANNEL):
        strip = strips.new_sound(name="%sSFX_%s" % (ep3.PREFIX, effect["id"]), filepath=str(ctx.audio_path(effect)),
                                 channel=channel, frame_start=effect["first_frame"])
        strip.volume = effect["gain"]


def build(ctx):
    setup_scene(ctx)
    evening_energy = build_light(ctx)
    build_cameras(ctx)
    build_gold(ctx, evening_energy)
    build_sound(ctx)
    ctx.scene.frame_set(ctx.frame_start)
