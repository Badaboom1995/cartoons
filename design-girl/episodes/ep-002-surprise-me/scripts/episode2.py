"""Episode 2 "Surprise Me" (voice input; Claude throws a neon party while she sleeps), scene EP2_Inspiration.

Script: ../script.md (14 voice lines, 27 shots).
Run inside Blender (Studio, Mascot and Designer scenes must exist; nothing in them is changed):
    exec(compile(open(".../episodes/ep-002-surprise-me/scripts/episode2.py").read(), "episode2.py", "exec"), {"__name__": "episode2"})

Images and sound effects come from scripts/make_episode2.py (overlays/, audio/sfx/), voices from
audio/voice/v01..v13 (+ v05b, her nap line), music and clicks from scene/audio/.
The set is linked: whole STU_ collections, or STU_ objects linked into EP2_ collections where some objects
had to be swapped for animated copies (walls, wall panel, posters, shelf, floor lamp, mouse, Clawd's dock).
Everything animated is an EP2_ copy or a new EP2_ object:
  cameras   one per shot, EP2_Cam_S<nn>_<name>, cuts = markers EP2_S<nn>_<name>; fisheye = 12 mm lens +
            Lens Distortion (node group EP2_Fisheye) as a Compositor strip modifier on the fisheye shots in EP2_Edit
  Designer  EP2_Designer_Rig + parts (action EP2_Designer; seated, then stands and walks out)
  Clawd     EP2_Clawd_* on EP2_Claude_Dock_Anchor; listening rings EP2_Listen_Ring_*
  screen    EP2_Screen_* planes on STU_Screen_Laptop, voice pill EP2_Mic_*, mic key EP2_Key_Mic
  party     EP2_DiscoBall*, EP2_Ball_Spot_*, EP2_Neon_*, EP2_Sweep_*, EP2_Lamp_Light_*, neon materials EP2_neon_*
  confetti  EP2_Confetti_* (rain; hidden in her shots 13-21; back for the tag, hoovered up by Clawd), _Last, _Sneeze
  EP2_Edit  the scene to watch / render: EP2_Inspiration as Scene strips (ch 1, cameras follow its markers),
            sound, and the subtitles as text strips (ch 7-8, from overlays/captions.json); workspace "EP2 Watch"
The party is a dream: on WAKE (cut to shot 13) music, neon, ball, party lights and confetti all stop on one frame.
  sound     in EP2_Edit: her voice ch 2, Claude ch 3, music ch 4, effects ch 5-6
Re-running rebuilds from scratch (cleanup()).
"""
import math
import os
import random
import wave

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector

REPO = "/Users/alexey/.paradev/projects/cartoons"
CHARACTER = os.path.join(REPO, "design-girl")
STUDIO_PY = os.path.join(CHARACTER, "scene", "locations", "studio", "scripts", "studio.py")
EP = os.path.join(CHARACTER, "episodes", "ep-002-surprise-me")
SHARED_SFX = os.path.join(CHARACTER, "scene", "audio", "sfx")
SHARED_MUSIC = os.path.join(CHARACTER, "scene", "audio", "music")
P = "EP2_"
SCENE = "EP2_Inspiration"
SRC = "Studio"
FPS = 24
END = 2160
END_CARD = False  # shot 27 "Surprise me" end card; False = the episode ends on shot 26
CLAWD_SCALE = 0.18
EDIT = "EP2_Edit"         # the edit scene: EP2_Inspiration as a Scene strip + sound + subtitles (Video Sequencer)
WORKSPACE = "EP2 Watch"   # big sequencer preview + timeline, window scene = EDIT
CAPTION_FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"   # same font/size as make_episode2.py wraps with
CAPTION_SIZE = 62
CAPTION_Y = 0.28          # text centre 72 % down the frame (bottom safe zone for TikTok / Reels)
INK_RGB = (30, 30, 30)
CLAUDE_RGB = (0xD9, 0x77, 0x57)

# ================================================================ timeline (frames, 24 fps)
SHOTS = [  # (no, name, first, last)
    (1, "Wide", 1, 60), (2, "Keys", 61, 112), (3, "ClawdLow", 113, 160), (4, "Face", 161, 298),
    (5, "OverClawd", 299, 394), (6, "ClawdPush", 395, 444),
    (7, "Front", 445, 600),                                                   # longer: her nap line
    (8, "Screen", 601, 644), (9, "FishWide", 645, 740), (10, "BallOrbit", 741, 780), (11, "ClawdWhip", 781, 820),
    (12, "FishTop", 821, 876),
    (13, "FaceCrash", 877, 1026), (14, "ClawdPOV", 1027, 1148), (15, "FaceShake", 1149, 1270),
    (16, "OverClawd2", 1271, 1332), (17, "Screen2", 1333, 1412), (18, "Face2", 1413, 1540),
    (19, "Front2", 1541, 1648), (20, "ClawdProud", 1649, 1718), (21, "WideExit", 1719, 1830),
    (22, "ClawdLook", 1831, 1890), (23, "TopDesk", 1891, 1930), (24, "ClawdSnap", 1931, 1966),
    (25, "TopSweep", 1967, 2046), (26, "ClawdInnocent", 2047, 2100),
    (27, "Card", 2101, END),
]
NAP = 450                         # line 5b "Okay... I'm gonna nap a little." (shot 7): smiles, leans back on "Okay..."
NAP_SHUT = 537                    # ...and her eyes close as she finishes the line (sleeping until WAKE)
VOICES = [  # (file, first frame, who, [(offset, overlay image)])
    ("v01_girl_hey_claude.wav", 76, "girl", [(0, "s01")]),
    ("v02_claude_im_here.wav", 124, "claude", [(0, "b02")]),
    ("v03_girl_deadline.wav", 164, "girl", [(0, "s03a"), (52, "s03b")]),
    ("v04_girl_surprise_me.wav", 301, "girl", [(0, "s04a"), (54, "s04b")]),
    ("v05_claude_cooking.wav", 397, "claude", [(0, "b05")]),
    ("v05b_girl_nap.wav", NAP, "girl", [(0, "s05a"), (36, "s05b")]),
    ("v06_girl_party.wav", 890, "girl", [(0, "s06a"), (28, "s06b"), (80, "s06c")]),
    ("v07_claude_no_party.wav", 1032, "claude", [(0, "b07a"), (30, "b07b"), (66, "b07c")]),
    ("v08_girl_moodboard.wav", 1151, "girl", [(0, "s08a"), (40, "s08b"), (80, "s08c")]),
    ("v09_claude_relax.wav", 1274, "claude", [(0, "b09")]),
    ("v10_girl_beautiful.wav", 1415, "girl", [(0, "s10a"), (45, "s10b")]),
    ("v11_girl_walk.wav", 1543, "girl", [(0, "s11a"), (43, "s11b")]),
    ("v12_claude_go.wav", 1652, "claude", [(0, "b12a"), (40, "b12b")]),
    ("v13_claude_oh_no.wav", 1936, "claude", [(0, "b13")]),
]
WAKE = 877                        # she jolts awake on the cut to shot 13: the party ends dead, like a dream
PRESS = (68, 74)                  # the one mic key press
MIC = (69, 1720)                  # voice pill on screen (fades out over the last 10 frames)
DUSK = (490, 600)                 # daylight fades to dusk
FLICKER = 601                     # moodboard starts glitching
BURST = 620                       # screen bursts into the party
MUSIC = (622, WAKE)               # disco music; record scratch on the wake cut - everything party stops on WAKE
FREEZE = (WAKE, WAKE + 12)        # Clawd freezes mid-dance, then turns to her
DENY = (1062, 1096)               # line 7 "Nooo. No party.": Clawd's innocent head shake
GLANCE = (1100, 1128)             # "...Definitely..." : he glances away (caught), back to her for "no party"
NEON = (635, 660)                 # neon ramps in, holds until WAKE (then off on the same frame)
BALL = (650, 700)                 # disco ball comes down; gone on WAKE
SPIN = (781, 805)                 # Clawd's spin in the whip-pan close-up
RAIN = (805, 845)                 # confetti starts falling (each piece falls ~24-30 frames, all landed before WAKE)
CONFETTI_BACK = 1831              # the desk confetti is hidden in all of her shots (13-21) and is back for the tag
SWATCHES = [1338, 1344, 1350, 1356, 1362]
MOODBOARD = 1380
STAND = (1726, 1736)
HEADPHONES = 1750
WALK_DIP = 0.05                   # hip drop at full stride
WALK = (1760, 1830)
LAST_PIECE = (1893, 1926)
SWEEP = (1967, 2046)
SNEEZE = 2076
MOUTH_MAP = {"shocked": "hmm", "panic": "hmm", "delighted": "smile", "sleepy": "neutral"}   # no round mouths
# her eyes come in two looks only: white + black pupil (open, tired, suspicious, wide, tiny) and closed arcs
# (^_^ = the Studio "delighted" eyes; "asleep" = the same arcs turned into a gentle U). The other Studio eye sets
# (blue iris blocks, dark lid bands) never show in EP2. Plain expression names map to an eye look here; a base
# key can also name the look directly, e.g. ("suspicious", "hmm", "neutral").
EYE_MAP = {"neutral": "open", "hmm": "tired", "eyeroll": "suspicious", "shocked": "wide", "panic": "tiny",
           "smile": "delighted", "delighted": "delighted", "sleepy": "asleep"}
FISHEYE = [(645, 740), (821, 876)]

DISCO_SRGB = [(0xFF, 0x4F, 0xA3), (0x8A, 0x5C, 0xFF), (0x2F, 0xD4, 0xE0), (0xB6, 0xF0, 0x3C), (0xFF, 0x9A, 0x3D)]
NEON_SRGB = [(0xFF, 0x2B, 0xD6), (0x2B, 0xE0, 0xFF), (0x9B, 0x3C, 0xFF)]     # pink, cyan, purple


def lin(c):
    return tuple(((v / 255) / 12.92 if v / 255 <= 0.04045 else ((v / 255 + 0.055) / 1.055) ** 2.4) for v in c)


DISCO_LIN = [lin(c) for c in DISCO_SRGB]
NEON_LIN = [lin(c) for c in NEON_SRGB]


def voice(i):
    """(start, end) frames of voice line i (1-based), from the WAV length."""
    fname, start = VOICES[i - 1][0], VOICES[i - 1][1]
    return start, start + len(wav_env(os.path.join(EP, "audio", "voice", fname))) - 1


# ================================================================ helpers
def modules():
    ns = {"__name__": "studio_helpers"}
    exec(compile(open(STUDIO_PY).read(), STUDIO_PY, "exec"), ns)
    return ns


def fcurves_of(idb):
    ad = idb.animation_data
    if not ad or not ad.action:
        return []
    try:
        return list(ad.action.fcurves)
    except AttributeError:
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
        return list(cb.fcurves) if cb else []


def key(idb, path, frame, value=None, index=-1):
    if value is not None:
        if index >= 0:
            getattr(idb, path)[index] = value
        else:
            setattr(idb, path, value)
    idb.keyframe_insert(data_path=path, frame=frame, index=index)


def key_socket(sock, frame, value):
    sock.default_value = value
    sock.keyframe_insert("default_value", frame=frame)


def name_action(idb, name):
    ad = idb.animation_data
    if ad and ad.action:
        ad.action.name = P + name


def set_interp(idb, kinds):
    for fc in fcurves_of(idb):
        for sub, it in kinds.items():
            if sub in fc.data_path:
                for kp in fc.keyframe_points:
                    kp.interpolation = it


def vis(o, frame, visible):
    key(o, "hide_render", frame, not visible)
    key(o, "hide_viewport", frame, not visible)


def show_only(objs, visible, frame):
    for o in objs:
        vis(o, frame, o in visible)


def const_vis(objs):
    for o in objs:
        set_interp(o, {"hide_": "CONSTANT"})


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def interp_keys(keys, f):
    """keys: [(frame, value)] sorted; smoothstep between neighbours, held outside."""
    if f <= keys[0][0]:
        return keys[0][1]
    for (a, va), (b, vb) in zip(keys, keys[1:]):
        if a <= f <= b:
            return va + (vb - va) * smooth((f - a) / (b - a)) if b > a else vb
    return keys[-1][1]


def interp_hold(keys, f):
    v = keys[0][1]
    for k, val in keys:
        if f >= k:
            v = val
    return v


def in_any(ranges, f):
    return any(a <= f <= b for a, b in ranges)


def look_at(loc, tgt):
    d = Vector(tgt) - Vector(loc)
    M = d.to_track_quat("-Z", "Y").to_matrix().to_4x4()
    M.translation = Vector(loc)
    return M


def no_light_effects(ob):
    for attr in ("visible_shadow", "visible_diffuse", "visible_glossy", "visible_transmission", "visible_volume_scatter"):
        if hasattr(ob, attr):
            setattr(ob, attr, False)


def bsdf(m):
    return next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)


def load_img(path):
    img = bpy.data.images.load(path, check_existing=True)
    img.name = P + os.path.splitext(os.path.basename(path))[0]
    img.reload()
    return img


def blended(m):
    for attr, val in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
        try:
            setattr(m, attr, val)
        except Exception:
            pass


def image_material(name, img, alpha=False, fade=False):
    """Emission from an image; alpha: blended with transparency; fade: a Value node multiplies alpha."""
    m = bpy.data.materials.new(P + name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Linear"
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    if alpha or fade:
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        fac = tex.outputs["Alpha"]
        if fade:
            v = nt.nodes.new("ShaderNodeValue")
            v.name = v.label = "fade"
            v.outputs[0].default_value = 1.0
            mul = nt.nodes.new("ShaderNodeMath")
            mul.operation = "MULTIPLY"
            nt.links.new(fac, mul.inputs[0])
            nt.links.new(v.outputs[0], mul.inputs[1])
            fac = mul.outputs[0]
        nt.links.new(fac, mix.inputs["Fac"])
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs["Surface"])
        blended(m)
    else:
        nt.links.new(em.outputs[0], out.inputs["Surface"])
    m.use_backface_culling = False
    return m


def flat_material(name, rgb_lin, strength=1.0, alpha_fade=False):
    m = bpy.data.materials.new(P + name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = tuple(rgb_lin) + (1.0,)
    em.inputs["Strength"].default_value = strength
    if alpha_fade:
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        mix.name = "fade"
        mix.inputs["Fac"].default_value = 1.0
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs["Surface"])
        blended(m)
    else:
        nt.links.new(em.outputs[0], out.inputs["Surface"])
    m.use_backface_culling = False
    return m


def quad(name, verts, material, col):
    me = bpy.data.meshes.new(P + name)
    me.from_pydata(verts, [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name="UVMap")
    for li, c in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
        uv.data[li].uv = c
    me.materials.append(material)
    ob = bpy.data.objects.new(P + name, me)
    col.objects.link(ob)
    return ob


def copy_obj(src, name, col, data=False):
    c = src.copy()
    if data and src.data is not None:
        c.data = src.data.copy()
        c.data.name = P + name
        if getattr(c.data, "animation_data", None):
            c.data.animation_data_clear()
    c.name = P + name
    c.animation_data_clear()
    col.objects.link(c)
    return c


def own_material(m, name):
    c = m.copy()
    c.name = P + name
    if c.node_tree and c.node_tree.animation_data:
        c.node_tree.animation_data_clear()
    if c.animation_data:
        c.animation_data_clear()
    return c


def coll(name, parent):
    c = bpy.data.collections.new(P + name)
    parent.children.link(c)
    return c


_ENV = {}


def wav_env(path, thresh=0.03):
    """Per video frame: speaking (RMS above thresh)."""
    if path in _ENV:
        return _ENV[path]
    with wave.open(path) as w:
        n, r, ch = w.getnframes(), w.getframerate(), w.getnchannels()
        x = np.frombuffer(w.readframes(n), "<i2").astype(np.float32) / 32767
    if ch > 1:
        x = x.reshape(-1, ch).mean(1)
    hop = r / FPS
    out = []
    i = 0
    while int((i + 1) * hop) <= len(x):
        seg = x[int(i * hop):int((i + 1) * hop)]
        out.append(float(np.sqrt((seg ** 2).mean())) > thresh)
        i += 1
    _ENV[path] = out
    return out


def talking(who):
    """{frame: True} while `who` ('girl' / 'claude') is audibly speaking."""
    t = {}
    for fname, start, w, _ in VOICES:
        if w == who:
            for i, on in enumerate(wav_env(os.path.join(EP, "audio", "voice", fname))):
                if on:
                    t[start + i] = True
    return t


def windows(who, pre=2, post=3):
    out = []
    for i, (fname, start, w, _) in enumerate(VOICES):
        if w == who:
            a, b = voice(i + 1)
            out.append((a - pre, b + post))
    return out


def shot(no):
    return next(s for s in SHOTS if s[0] == no)


# ================================================================ cleanup
def cleanup():
    for name in (EDIT, SCENE):
        sc = bpy.data.scenes.get(name)
        if sc:
            try:
                for win in bpy.context.window_manager.windows:
                    if win.scene == sc:
                        win.scene = bpy.data.scenes[SRC]
            except Exception:
                pass
            bpy.data.scenes.remove(sc)
    for o in list(bpy.data.objects):
        if o.name.startswith(P):
            bpy.data.objects.remove(o, do_unlink=True)
    for c in list(bpy.data.collections):
        if c.name.startswith(P):
            bpy.data.collections.remove(c)
    for ng in list(bpy.data.node_groups):
        if ng.name.startswith(P):
            bpy.data.node_groups.remove(ng)
    for _ in range(3):
        for coll_ in (bpy.data.meshes, bpy.data.curves, bpy.data.lights, bpy.data.cameras, bpy.data.armatures,
                      bpy.data.materials, bpy.data.images, bpy.data.actions, bpy.data.sounds):
            for d in list(coll_):
                if d.name.startswith(P) and d.users == 0:
                    coll_.remove(d)
    for snd in list(bpy.data.sounds):          # voice / effect sounds of earlier builds
        if snd.users == 0 and "episode2" in snd.filepath:
            bpy.data.sounds.remove(snd)


# ================================================================ scene + set
def make_scene():
    src = bpy.data.scenes[SRC]
    sc = bpy.data.scenes.new(SCENE)
    try:
        sc.render.engine = src.render.engine
    except TypeError:
        pass
    for a in ("resolution_x", "resolution_y", "resolution_percentage", "fps", "fps_base", "pixel_aspect_x",
              "pixel_aspect_y", "film_transparent", "use_motion_blur"):
        try:
            setattr(sc.render, a, getattr(src.render, a))
        except Exception:
            pass
    for p in src.eevee.bl_rna.properties:
        if p.identifier == "rna_type" or p.is_readonly:
            continue
        try:
            setattr(sc.eevee, p.identifier, getattr(src.eevee, p.identifier))
        except Exception:
            pass
    for a in ("view_transform", "look", "exposure", "gamma"):
        try:
            setattr(sc.view_settings, a, getattr(src.view_settings, a))
        except Exception:
            pass
    try:
        sc.display_settings.display_device = src.display_settings.display_device
    except Exception:
        pass
    sc.world = src.world
    sc.frame_start, sc.frame_end = 1, (END if END_CARD else shot(26)[3])
    sc.render.fps, sc.render.fps_base = FPS, 1.0
    return sc


NEON_COPIES = {  # STU object -> (neon colour index, emission peak) for each of its materials
    "STU_Wall_Back": (0, 0.9), "STU_Wall_Left": (1, 0.9), "STU_Wall_Right": (2, 0.9), "STU_Wall_Panel": (2, 0.7),
    "STU_Shelf": (1, 1.5),
}


def build_set(sc, root):
    D = bpy.data.objects
    for n in ("STU_Desk", "STU_ShelfItems", "STU_Exterior"):
        sc.collection.children.link(bpy.data.collections[n])
    sset = coll("Set", root)
    swap = {"STU_Floor_Lamp", "STU_Mouse", "STU_Claude_Dock", "STU_Claude_Dock_Anchor"} | set(NEON_COPIES)
    swap |= {o.name for o in bpy.data.collections["STU_Posters"].objects}
    cols = {}
    for n in ("STU_Room", "STU_Decor", "STU_DeskItems", "STU_Shelf", "STU_Posters"):
        c = coll(n[4:], sset)
        cols[n] = c
        for o in bpy.data.collections[n].objects:
            if o.name not in swap:
                c.objects.link(o)
    neon = []                                    # (material, colour index, peak)
    # walls, panel, shelf: copies with their own (neon) materials
    for name, (ci, peak) in NEON_COPIES.items():
        src = D[name]
        home = next(n for n, c in cols.items() if src.name in bpy.data.collections[n].objects)
        o = copy_obj(src, name[4:], cols[home])
        for k, slot in enumerate(o.material_slots):
            if slot.material:
                is_frame = "frame" in slot.material.name
                m = own_material(slot.material, "neon_%s_%d" % (name[4:], k))
                slot.link = "OBJECT"
                slot.material = m
                neon.append((m, (ci + k) % 3, peak * (3.0 if is_frame else 1.0)))
    # posters + frames
    pc = {}
    for o in bpy.data.collections["STU_Posters"].objects:
        c = copy_obj(o, o.name[4:], cols["STU_Posters"])
        pc[o] = c
    for o, c in pc.items():
        if o.parent in pc:
            c.parent = pc[o.parent]
            c.matrix_parent_inverse = o.matrix_parent_inverse.copy()
    for n, (o, c) in enumerate(pc.items()):
        for slot in c.material_slots:
            if slot.material:
                is_frame = "Frame" in o.name
                m = own_material(slot.material, "neon_" + o.name[4:])
                slot.link = "OBJECT"
                slot.material = m
                neon.append((m, n % 3, 3.0 if is_frame else 0.45))
    items = cols["STU_DeskItems"]
    mouse = copy_obj(D["STU_Mouse"], "Mouse", items)          # a still copy at home (EP1 drags the original)
    for fc in fcurves_of(D["STU_Mouse"]):
        if fc.data_path == "location" and len(fc.keyframe_points):
            mouse.location[fc.array_index] = fc.keyframe_points[0].co[1]
    dock = copy_obj(D["STU_Claude_Dock"], "Claude_Dock", items)
    dock_glow = None
    for slot in dock.material_slots:
        if slot.material and slot.material.name == "STU_dock_glow":
            dock_glow = own_material(slot.material, "dock_glow")
            bsdf(dock_glow).inputs["Emission Strength"].default_value = 1.0
            slot.link = "OBJECT"
            slot.material = dock_glow
    anchor = copy_obj(D["STU_Claude_Dock_Anchor"], "Claude_Dock_Anchor", items)
    anchor.parent = dock
    anchor.matrix_parent_inverse = D["STU_Claude_Dock_Anchor"].matrix_parent_inverse.copy()
    lamp = copy_obj(D["STU_Floor_Lamp"], "Floor_Lamp", cols["STU_Room"])
    lamp_mats = []
    for slot in lamp.material_slots:
        m = slot.material
        if m and m.name.startswith("STU_lamp_glow"):
            c = own_material(m, m.name[4:])
            slot.link = "OBJECT"
            slot.material = c
            lamp_mats.append(c)
        elif m:
            slot.link = "OBJECT"
            slot.material = m
    lights = coll("Lights_Day", root)
    day = []
    for o in bpy.data.collections["STU_Lights_Day"].objects:
        c = copy_obj(o, "Day_" + o.name[4:].replace("Day_", ""), lights, data=True)
        warm = Vector((1.0, 0.78, 0.55))           # late afternoon: a little warmer
        c.data.color = tuple(0.8 * Vector(o.data.color) + 0.2 * warm)
        day.append(c)
    return dict(dock=dock, dock_glow=dock_glow, anchor=anchor, lamp=lamp, lamp_mats=lamp_mats, day=day,
                neon=neon, items=items)


# ================================================================ laptop screen, voice pill, mic key
def screen_frame():
    scr = bpy.data.objects["STU_Screen_Laptop"]
    n = (scr.matrix_world.to_3x3() @ Vector((0, -1, 0))).normalized()
    return scr, scr.matrix_world.translation.copy(), n


def screen_plane(name, img, parent, w, h, lift, col, fade=False):
    m = image_material(name, img, alpha=fade, fade=fade)
    ob = quad(name, [(-w / 2, 0, -h / 2), (w / 2, 0, -h / 2), (w / 2, 0, h / 2), (-w / 2, 0, h / 2)], m, col)
    ob.parent = parent
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_basis = Matrix.Translation((0, -lift, 0))
    no_light_effects(ob)
    return ob


def run_states(planes, runs):
    allp = list(planes.values())
    show_only(allp, [], 1)
    for f, k in runs:
        show_only(allp, [planes[k]] if k is not None else [], f)
    const_vis(allp)


def build_screens(col):
    scr, _, _ = screen_frame()
    w, h = 0.272, 0.272 / 1.6
    sd = os.path.join(EP, "overlays", "screens")
    names = (["empty", "moodboard"] + ["flicker_%d" % i for i in range(4)] +
             ["confetti_%d" % i for i in range(6)] + ["palette_%d" % i for i in range(6)])
    base = {k: screen_plane("Screen_" + k, load_img(os.path.join(sd, k + ".png")), scr, w, h, 0.0006, col) for k in names}
    runs = [(1, "empty")]
    for i, f in enumerate(range(FLICKER, BURST, 3)):
        runs.append((f, "flicker_%d" % [0, 1, 2, 3, 1, 3, 2][i % 7]))
    for i, f in enumerate(range(BURST, MUSIC[1], 3)):
        runs.append((f, "confetti_%d" % (i if i < 6 else 2 + (i - 6) % 4)))
    runs.append((WAKE, "empty"))                      # woke up: just her empty moodboard
    runs.append((shot(17)[2], "palette_0"))
    for n, f in enumerate(SWATCHES):
        runs.append((f, "palette_%d" % (n + 1)))
    runs.append((MOODBOARD, "moodboard"))
    run_states(base, runs)
    # voice-input pill: idle (flat wave) or talking (wave states), driven by her voice
    pill = {"idle": screen_plane("Mic_idle", load_img(os.path.join(sd, "mic_idle.png")), scr, w, h, 0.0012, col, fade=True)}
    for i in range(6):
        pill[i] = screen_plane("Mic_%d" % i, load_img(os.path.join(sd, "mic_%d.png" % i)), scr, w, h, 0.0012, col, fade=True)
    talk = talking("girl")
    mruns, last = [], "off"
    for f in range(1, END + 1):
        if not (MIC[0] <= f <= MIC[1]):
            st = None
        elif talk.get(f):
            st = (f // 2) % 6
        else:
            st = "idle"
        if st != last:
            mruns.append((f, st))
            last = st
    run_states(pill, [r for r in mruns if r[0] > 1] if mruns and mruns[0][1] is None else mruns)
    for o in pill.values():
        nt = o.active_material.node_tree
        sock = next(n for n in nt.nodes if n.type == "VALUE").outputs[0]
        for f, v in ((1, 0.0), (MIC[0], 0.0), (MIC[0] + 3, 1.0), (MIC[1] - 10, 1.0), (MIC[1], 0.0)):
            key_socket(sock, f, v)
        name_action(nt, "Mic_fade_" + o.name[4:])
    return base, pill


def build_key(col):
    img = load_img(os.path.join(EP, "overlays", "key_mic.png"))
    m = bpy.data.materials.new(P + "Key_Mic")
    m.use_nodes = True
    nt = m.node_tree
    b = bsdf(m)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(tex.outputs["Color"], b.inputs["Emission Color"])
    b.inputs["Emission Strength"].default_value = 0.3
    b.inputs["Roughness"].default_value = 0.5
    sx, sy, sz = 0.013, 0.011, 0.004
    v = [(-sx, -sy, -sz), (sx, -sy, -sz), (sx, sy, -sz), (-sx, sy, -sz), (-sx, -sy, sz), (sx, -sy, sz), (sx, sy, sz), (-sx, sy, sz)]
    faces = [(4, 5, 6, 7), (0, 3, 2, 1), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    me = bpy.data.meshes.new(P + "Key_Mic")
    me.from_pydata(v, [], faces)
    uv = me.uv_layers.new(name="UVMap")
    for li in range(len(uv.data)):
        uv.data[li].uv = (0.05, 0.05)
    for k, li in enumerate(me.polygons[0].loop_indices):       # mic glyph on top, upright for her
        uv.data[li].uv = [(1, 1), (0, 1), (0, 0), (1, 0)][k]
    me.materials.append(m)
    ob = bpy.data.objects.new(P + "Key_Mic", me)
    col.objects.link(ob)
    ob.location = (-0.115, 0.15, 0.735)
    z0 = ob.location.z
    es = b.inputs["Emission Strength"]
    a, bb = PRESS
    for f, z, e in ((1, z0, 0.3), (a - 1, z0, 0.3), (a, z0 - 0.0045, 2.0), (bb, z0 - 0.0045, 2.0), (bb + 1, z0, 1.2),
                    (MIC[1], z0, 1.2), (MIC[1] + 1, z0, 0.3)):
        key(ob, "location", f, z, 2)
        key_socket(es, f, e)
    set_interp(ob, {"location": "CONSTANT"})
    set_interp(nt, {"": "CONSTANT"})
    name_action(ob, "Key_Mic")
    name_action(nt, "Key_Mic_glow")
    return ob


# ================================================================ the Designer
def build_designer(col, ns):
    src = bpy.data.collections["STU_Designer"]
    rig_src = bpy.data.objects["STU_Designer_Rig"]
    copies = {}
    for o in src.objects:
        c = o.copy()
        c.name = P + o.name[4:]
        c.animation_data_clear()
        col.objects.link(c)
        copies[o] = c
    for o, c in copies.items():
        if o.parent in copies:
            c.parent = copies[o.parent]
            c.parent_type, c.parent_bone = o.parent_type, o.parent_bone
            c.matrix_parent_inverse = o.matrix_parent_inverse.copy()
    rig = copies[rig_src]
    rig.matrix_world = rig_src.matrix_world.copy()
    glasses = next(c for o, c in copies.items() if o.name == "STU_Designer_Glasses")
    for slot in glasses.material_slots:              # frame (front + lower rim) solid; lenses stay clear
        m = slot.material
        if m and m.name.startswith("STU_Designer_DSG_glasses"):
            c = own_material(m, m.name[4:])
            b = bsdf(c)
            b.inputs["Alpha"].default_value = 1.0
            b.inputs["Transmission Weight"].default_value = 0.0
            for attr, val in (("surface_render_method", "DITHERED"), ("blend_method", "OPAQUE")):
                try:
                    setattr(c, attr, val)
                except Exception:
                    pass
            c.diffuse_color = tuple(c.diffuse_color[:3]) + (1.0,)
            slot.link = "OBJECT"
            slot.material = c
    rig.hide_render = True
    for pb in rig.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    rig["note"] = "EP2 copy of STU_Designer_Rig (Episode 2 action)"
    return rig, list(copies.values())


def up(h, dz):
    (w, t) = h
    return ((w[0], w[1], w[2] + 0.6 * dz), (t[0], t[1], t[2] + dz))


KL = ((0.08, 0.32, 0.10), (0.05, 0.19, 0.06))
KR = ((-0.08, 0.32, 0.10), (-0.05, 0.19, 0.06))
KEY = ((-0.15, 0.275, 0.123), (-0.115, 0.15, 0.073))      # hand mesh sits ~0.06 below the bone tip
CHIN = ((-0.07, 0.26, 0.13), (-0.03, 0.27, 0.26))
LAP_L = ((0.15, 0.52, -0.02), (0.10, 0.40, -0.05))
LAP_R = ((-0.15, 0.52, -0.02), (-0.10, 0.40, -0.05))
CHEEK_L = ((0.30, 0.30, 0.30), (0.28, 0.34, 0.44))
CHEEK_R = ((-0.30, 0.30, 0.30), (-0.28, 0.34, 0.44))


def seated_poses():
    p = []

    def pose(f, L, R, torso, head):
        p.append((f, {".L": L, ".R": R}, torso, head))

    for i, f in enumerate(range(1, 58, 3)):                   # working: typing, eyes on the laptop
        tap = 0.012
        pose(f, up(KL, tap if i % 2 else 0.0), up(KR, 0.0 if i % 2 else tap), (4, 0), (10 + (i % 3 == 0), -2 + (i % 5 == 0)))
    pose(60, KL, KR, (4, 0), (10, -2))
    pose(63, KL, up(KEY, 0.06), (3, 0), (12, 0))
    pose(66, KL, up(KEY, 0.02), (4, 0), (14, 0))
    pose(PRESS[0], KL, KEY, (4, 0), (14, 0))
    pose(PRESS[1] - 1, KL, KEY, (4, 0), (14, 0))
    pose(PRESS[1] + 3, KL, up(KEY, 0.04), (3, 0), (10, -10))   # "Hey, Claude..."
    pose(90, KL, up(KEY, 0.04), (3, 0), (6, -18))
    pose(150, KL, up(KEY, 0.04), (3, 0), (6, -18))
    pose(162, KL, CHIN, (6, 0), (4, -8))                       # chin in hand, the deadline sigh
    pose(230, KL, CHIN, (7, 0), (6, -6))
    pose(260, KL, CHIN, (9, 0), (8, -4))
    pose(296, KL, CHIN, (8, 0), (6, -8))
    pose(305, KL, KR, (3, 0), (5, -18))                        # to Clawd: "surprise me"
    pose(390, KL, KR, (2, 0), (4, -18))
    pose(440, KL, KR, (2, 0), (4, -16))
    pose(450, KL, KR, (0, 0), (2, -10))
    pose(NAP + 40, LAP_L, LAP_R, (-12, 0), (-6, -6))           # "Okay..." - leans back
    pose(NAP + 50, LAP_L, LAP_R, (-12, 0), (-4, 0))            # "I'm gonna nap a little."
    pose(NAP_SHUT + 11, LAP_L, LAP_R, (-13, 0), (20, 8))       # eyes shut, dozes off
    for i, f in enumerate(range(600, WAKE - 3, 60)):
        pose(f, LAP_L, LAP_R, (-12 - i % 2, 0), (24 - 4 * (i % 2), 8))
    pose(WAKE - 4, LAP_L, LAP_R, (-12, 0), (22, 8))
    pose(WAKE, up(KL, 0.08), up(KR, 0.08), (2, 0), (-4, 0))    # jolts awake
    pose(900, up(KL, 0.06), up(KR, 0.06), (3, 0), (2, -20))    # "Claude?!"
    pose(1148, up(KL, 0.06), up(KR, 0.06), (3, 0), (2, -20))
    pose(1154, CHEEK_L, CHEEK_R, (4, 0), (4, -12))             # panic, hands on cheeks
    pose(1200, CHEEK_L, CHEEK_R, (5, 0), (4, -20))
    pose(1265, CHEEK_L, CHEEK_R, (4, 0), (4, -14))
    pose(1274, up(KL, 0.03), up(KR, 0.03), (3, 0), (4, -18))   # "Hey, relax."
    pose(1292, up(KL, 0.03), up(KR, 0.03), (5, 0), (10, -4))   # looks at the screen
    pose(1410, up(KL, 0.03), up(KR, 0.03), (6, 0), (12, 0))
    pose(1500, up(KL, 0.03), up(KR, 0.03), (2, 0), (8, -6))
    pose(1538, up(KL, 0.03), up(KR, 0.03), (0, 0), (4, -14))
    pose(1546, KL, KR, (-4, 0), (2, -18))                      # relieved: "Thank you, Claude"
    pose(STAND[0] - 6, KL, KR, (-3, 0), (2, -18))
    pose(STAND[0], up(KL, 0.03), up(KR, 0.03), (14, 0), (4, -10))                  # about to stand
    return p


def standing_bases(arm, legs, arms, torso=(0.0, 0.0), head=(0.0, 0.0)):
    """matrix_basis per bone for a standing pose given bone directions (armature space).
    legs: {'.L': (thigh dir, shin dir)}, arms: {'.L': (upper arm dir, forearm dir, hand dir)}."""
    bones = arm.data.bones
    pose = {}

    def turn(pitch, yaw):
        return Matrix.Rotation(math.radians(yaw), 3, "Z") @ Matrix.Rotation(math.radians(pitch), 3, "X")

    def place(name, direction=None, rot=None):
        b = bones[name]
        rest = b.matrix_local
        if b.parent is None:
            head_pt = rest.translation
        else:
            p = b.parent
            head_pt = (pose[p.name] @ p.matrix_local.inverted() @ rest).translation
        R = rest.to_3x3()
        if rot is not None:
            R = rot @ R
        elif direction is not None:
            R = (R.col[1].normalized().rotation_difference(Vector(direction).normalized())).to_matrix() @ R
        M = R.to_4x4()
        M.translation = head_pt
        pose[name] = M

    place("root")
    place("hips")
    place("torso", rot=turn(*torso))
    place("head", rot=turn(*head))
    for s in (".L", ".R"):
        th, sh = legs[s]
        place("thigh" + s, th)
        place("shin" + s, sh)
        place("foot" + s)
        ua, fa, hd = arms[s]
        place("upper_arm" + s, ua)
        place("forearm" + s, fa)
        place("hand" + s, hd)
    out = {}
    for name, M in pose.items():
        b = bones[name]
        if b.parent is None:
            out[name] = b.matrix_local.inverted() @ M
        else:
            local_rest = b.parent.matrix_local.inverted() @ b.matrix_local
            out[name] = local_rest.inverted() @ pose[b.parent.name].inverted() @ M
    return out


def leg(a, bend=0.0):
    """Leg swung forward by a degrees (forward = -Y), knee bent back by bend degrees."""
    ra, rb = math.radians(a), math.radians(a - bend)
    return ((0, -math.sin(ra), -math.cos(ra)), (0, -math.sin(rb), -math.cos(rb)))


def arm_down(sx, a=0.0):
    ra = math.radians(a)
    return ((0.12 * sx, -math.sin(ra), -math.cos(ra)), (0.08 * sx, -0.12 - math.sin(ra), -1), (0.05 * sx, -0.08, -1))


def arm_ear(sx):
    return ((0.85 * sx, 0.05, 0.35), (-0.25 * sx, -0.1, 1.0), (-0.2 * sx, 0.0, 1.0))


def standing_poses():
    """(frame, legs, arms, torso, head)"""
    p = []
    still = {".L": leg(0), ".R": leg(0)}
    down = {".L": arm_down(1), ".R": arm_down(-1)}
    ears = {".L": arm_ear(1), ".R": arm_ear(-1)}
    p.append((STAND[1], still, down, (2, 0), (2, -14)))
    p.append((HEADPHONES - 6, still, ears, (0, 0), (0, -6)))
    p.append((HEADPHONES + 4, still, ears, (0, 0), (0, -6)))
    p.append((WALK[0], still, down, (2, 0), (0, 0)))
    for i, f in enumerate(range(WALK[0] + 4, WALK[1] + 1, 4)):
        ph = math.pi / 2 * (i + 1)
        a = 24 * math.sin(ph)
        legs = {".L": leg(a, 18 * max(0.0, -math.sin(ph))), ".R": leg(-a, 18 * max(0.0, math.sin(ph)))}
        arms = {".L": arm_down(1, -0.8 * a), ".R": arm_down(-1, 0.8 * a)}
        p.append((f, legs, arms, (4, 0), (0, 0)))
    return p


def talk_mouth(sc, neutral, parts):
    """Flat talking mouth for her lip sync: a wide, thin, slightly open slit (lip colour rim + dark inside).
    Shaped in world space on the neutral mouth (same centre, same facing), stored in the neutral mouth's local
    space, same parent bone - so it moves with her head exactly like the other mouths."""
    rig = neutral.parent                                  # rest-pose world matrix (hidden objects aren't evaluated)
    bone = rig.data.bones[neutral.parent_bone]
    M = (rig.matrix_world @ bone.matrix_local @ Matrix.Translation((0, bone.length, 0)) @ neutral.matrix_parent_inverse
         @ neutral.matrix_basis)
    me_n = neutral.data
    wv = [M @ v.co for v in me_n.vertices]
    centre = sum(wv, Vector()) / len(wv)
    R = rig.matrix_world.to_3x3()
    nrm = (R @ Vector((0, -1, 0))).normalized()           # her face looks along the rig's -Y in the rest pose
    up = (R @ Vector((0, 0, 1))).normalized()
    right = up.cross(nrm).normalized()
    front = max((v - centre).dot(nrm) for v in wv)        # in front of the neutral mouth's own surface
    Minv = M.inverted()

    def stadium(w, h, off, n=8):
        r = h / 2
        pts = []
        for k in range(n + 1):
            a = -math.pi / 2 + math.pi * k / n
            pts.append(((w / 2 - r) + r * math.cos(a), r * math.sin(a)))
        for k in range(n + 1):
            a = math.pi / 2 + math.pi * k / n
            pts.append((-(w / 2 - r) + r * math.cos(a), r * math.sin(a)))
        return [Minv @ (centre + right * x + up * z + nrm * (front + off)) for x, z in pts]

    outer = stadium(0.104, 0.020, 0.0004)
    inner = stadium(0.088, 0.009, 0.0008)
    me = bpy.data.meshes.new(P + "Designer_Face_Mouth_talk")
    me.from_pydata(outer + inner, [], [tuple(range(len(outer))), tuple(range(len(outer), len(outer) + len(inner)))])
    me.update()
    if (M.to_3x3() @ me.polygons[0].normal).dot(nrm) < 0:
        me.flip_normals()
    for nm in ("STU_Designer_DSG_mouth", "STU_Designer_DSG_mouth_dark"):
        me.materials.append(bpy.data.materials[nm])
    me.polygons[1].material_index = 1
    ob = neutral.copy()
    ob.data = me
    ob.name = P + "Designer_Face_Mouth_talk"
    ob["expression"] = "talk"
    ob.animation_data_clear()
    for c in neutral.users_collection:
        c.objects.link(ob)
    parts.append(ob)
    return ob


def build_eyes(neutral, parts):
    """EP2-only eye meshes (named apart from the Studio sets) in the neutral eyes' local space (same parent bone,
    same placement), so they move with her head like the Studio sets. Each eye is a 0.12 x 0.08 box (x 0.04..0.16
    and mirrored, z 0.16..0.24) on the face plane (y -0.244). Layers sit a hair in front of each other: white, pupil, lid (skin shadow), sweat.
    Pupils: centre column = looking at you; 'suspicious' slides both pupils towards Clawd (world -x)."""
    WHITE, PUP, LID, SWEAT = "DSG_eye_hi", "DSG_pupil", "DSG_skin_shadow", "DSG_sweat"
    X0, X1, Z0, Z1 = 0.04, 0.16, 0.16, 0.24

    def white():
        return [(X0, X1, Z0, Z1, WHITE, 0)]

    def pupil(x0, x1, z0, z1):
        return [(x0, x1, z0, z1, PUP, 1)]

    def lid(z):
        return [(X0 - 0.001, X1 + 0.001, z, Z1 + 0.001, LID, 2)]

    looks = {   # (+x eye parts, mirror_pupil): mirror_pupil False keeps the pupil on the same world side for both eyes
        "open": (white() + pupil(0.08, 0.12, 0.172, 0.228), True),
        "tired": (white() + pupil(0.08, 0.12, 0.172, 0.228) + lid(0.212), True),
        "suspicious": (white() + pupil(0.04, 0.08, 0.172, 0.228) + lid(0.206), False),
        "wide": (white() + pupil(0.088, 0.112, 0.188, 0.212), True),
        "tiny": (white() + pupil(0.091, 0.109, 0.186, 0.204)
                  + [(0.176, 0.196, 0.324, 0.356, SWEAT, 3), (0.182, 0.190, 0.356, 0.366, SWEAT, 3)], True),
        "asleep": ([(0.064, 0.136, 0.176, 0.192, PUP, 1), (0.04, 0.07, 0.188, 0.204, PUP, 1),
                    (0.13, 0.16, 0.188, 0.204, PUP, 1)], True),
    }
    out = {}
    for name, (rects, mirror_pupil) in looks.items():
        boxes = []
        for x0, x1, z0, z1, mat, layer in rects:
            boxes.append((x0, x1, z0, z1, mat, layer))
            if mat == SWEAT:
                continue                                       # one sweat drop, on her +x temple
            if mat == PUP and not mirror_pupil:                # same world side: shift into the other eye's box
                boxes.append((x0 - 0.20, x1 - 0.20, z0, z1, mat, layer))
            else:
                boxes.append((-x1, -x0, z0, z1, mat, layer))
        me = bpy.data.meshes.new(P + "Designer_Face_Eyes_" + name)
        mats = []
        verts, faces, fmat = [], [], []
        for x0, x1, z0, z1, mat, layer in boxes:
            if mat not in mats:
                mats.append(mat)
            yf, yb = -0.244 - 0.0005 * layer, -0.240
            b = len(verts)
            verts += [(x0, yf, z0), (x1, yf, z0), (x1, yf, z1), (x0, yf, z1),
                      (x0, yb, z0), (x1, yb, z0), (x1, yb, z1), (x0, yb, z1)]
            for q in ((0, 1, 2, 3), (5, 4, 7, 6), (4, 0, 3, 7), (1, 5, 6, 2), (3, 2, 6, 7), (4, 5, 1, 0)):
                faces.append(tuple(b + i for i in q))
                fmat.append(mats.index(mat))
        me.from_pydata(verts, [], faces)
        for mat in mats:
            me.materials.append(bpy.data.materials[mat])
        for p_, mi in zip(me.polygons, fmat):
            p_.material_index = mi
        me.update()
        ob = neutral.copy()
        ob.data = me
        ob.name = P + "Designer_Face_Eyes_" + name
        ob["expression"] = name
        ob.animation_data_clear()
        for c in neutral.users_collection:
            c.objects.link(ob)
        parts.append(ob)
        out[name] = ob
    return out


def animate_designer(sc, rig, parts, ns):
    prev = {}

    def key_bases(f, bases):
        for bn, M in bases.items():
            pb = rig.pose.bones[bn]
            pb.rotation_mode = "QUATERNION"
            q = M.to_quaternion()
            if bn in prev and prev[bn].dot(q) < 0:
                q.negate()
            prev[bn] = q
            pb.rotation_quaternion = q
            pb.keyframe_insert("rotation_quaternion", frame=f)

    # standing height: rest pose = standing straight; feet go to the floor
    for pb in rig.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    sc.view_layers[0].update()
    dg = sc.view_layers[0].depsgraph
    feet = [o for o in parts if o.name.startswith(P + "Designer_Foot")]
    zmin = min((o.evaluated_get(dg).matrix_world @ v.co).z for o in feet for v in o.evaluated_get(dg).data.vertices)
    L0 = rig.location.copy()
    stand_z = L0.z - zmin + 0.005
    for f, hands, torso, head in seated_poses():
        key_bases(f, ns["designer_pose_bases"](rig, hands, torso, head))
    for f, legs, arms, torso, head in standing_poses():
        key_bases(f, standing_bases(rig, legs, arms, torso, head))
    # where she is: seated, stands up beside the chair, walks out towards the camera's left
    rig.rotation_mode = "XYZ"
    sx = -0.55
    path = [(1, L0, 0), (STAND[0], L0, 0), (STAND[1], Vector((sx, 0.62, stand_z)), 0),
            (WALK[0], Vector((sx, 0.62, stand_z)), 0), (WALK[0] + 6, Vector((sx - 0.05, 0.60, stand_z)), -61),
            (WALK[0] + 18, Vector((-0.95, 0.40, stand_z)), -61), (WALK[0] + 24, Vector((-0.97, 0.30, stand_z)), 0),
            (WALK[1], Vector((-0.97, -1.90, stand_z)), 0), (WALK[1] + 8, Vector((-0.97, -2.60, stand_z)), 0)]
    def dip(f):
        return WALK_DIP * math.sin(math.pi / 2 * (f - WALK[0]) / 4) ** 2 if WALK[0] <= f <= WALK[1] else 0.0

    for f, loc, yaw in path:
        rig.location = loc - Vector((0, 0, dip(f)))
        rig.rotation_euler = (0, 0, math.radians(yaw))
        rig.keyframe_insert("location", frame=f)
        rig.keyframe_insert("rotation_euler", frame=f)
    for f in range(WALK[0] + 2, WALK[1] + 1, 2):                      # hips dip when the legs are spread
        rig.location.z = stand_z - dip(f)
        rig.keyframe_insert("location", index=2, frame=f)
    name_action(rig, "Designer")
    # face: per part (eyes / brows / mouth), keyed where it changes
    faces = {pt: {o["expression"]: o for o in parts if o.name.startswith(P + "Designer_Face_" + pt + "_")}
             for pt in ("Eyes", "Brows", "Mouth")}
    faces["Mouth"]["talk"] = talk_mouth(sc, faces["Mouth"]["neutral"], parts)
    faces["Eyes"].update(build_eyes(faces["Eyes"]["neutral"], parts))
    base = [(1, "neutral"), (36, "hmm"), (PRESS[1], "neutral"), (162, "hmm"), (230, "hmm"), (300, "neutral"),
            (372, "smile"), (NAP + 30, ("tired", "sleepy", "neutral")), (NAP_SHUT, "sleepy"), (WAKE, "shocked"),
            (902, ("suspicious", "hmm", "neutral")), (1060, ("suspicious", "hmm", "hmm")), (1149, "panic"), (1300, "hmm"),
            (1413, "panic"), (1422, "hmm"), (1470, "smile"), (1495, "delighted"), (1590, "smile")]
    state = {}
    for f in range(1, END + 1):
        e = interp_hold(base, f)
        e = (e, e, e) if isinstance(e, str) else e
        state[f] = {"Eyes": EYE_MAP.get(e[0], e[0]), "Brows": e[1], "Mouth": MOUTH_MAP.get(e[2], e[2])}
    for fname, start, who, _ in VOICES:                           # lip flap: flat talking slit <-> resting mouth
        if who != "girl":
            continue
        for i, on in enumerate(wav_env(os.path.join(EP, "audio", "voice", fname))):
            f = start + i
            rest = "smile" if state[f]["Mouth"] == "smile" else "neutral"
            state[f]["Mouth"] = "talk" if (on and (i // 3) % 3 != 2) else rest
    last = {}
    for f in range(1, END + 1):
        for pt, objs in faces.items():
            e = state[f][pt]
            if last.get(pt) != e:
                show_only(list(objs.values()), [objs[e]], f)
                last[pt] = e
    allf = [o for objs in faces.values() for o in objs.values()]
    # headphones from her head to her neck as she gets up
    hp_head = [o for o in parts if o.get("variant") == "headphones_head" and not o.hide_render]
    hp_neck = [o for o in parts if o.get("variant") == "headphones_neck"]
    for o in hp_head:
        vis(o, 1, True)
        vis(o, HEADPHONES, False)
    for o in hp_neck:
        vis(o, 1, False)
        vis(o, HEADPHONES, True)
    const_vis(allf + hp_head + hp_neck)
    for o in allf + hp_head + hp_neck:
        name_action(o, o.name[4:])
    return faces


def face_point(sc, f):
    """World point between her eyes at frame f. Measured on the head (always shown): a face set that is hidden at f
    isn't evaluated, so its matrix_world would be stale. The face sets share the head's parent bone and placement."""
    sc.frame_set(f)
    dg = sc.view_layers[0].depsgraph
    return bpy.data.objects[P + "Designer_Head"].evaluated_get(dg).matrix_world @ Vector((0.0, -0.242, 0.20))


def head_top(sc, f):
    """World point on top of her head (hair included) at frame f."""
    sc.frame_set(f)
    dg = sc.view_layers[0].depsgraph
    h = bpy.data.objects[P + "Designer_Head"].evaluated_get(dg)
    top = max((h.matrix_world @ v.co).z for v in h.data.vertices)
    return Vector((face_point(sc, f).x, (h.matrix_world @ Vector((0, -0.02, 0.24))).y, top))


ZZZ_SIZE = 0.17     # letter height (m): ~2.5x the old 0.07 so the "Zzz" reads in the wide party shots
ZZZ_LOOP = 48       # frames for one letter to rise, drift and fade; 3 letters a third of a loop apart
ZZZ_BOOST = {9: 3.0}  # shot -> size and path multiplier (the fisheye wide is far away: letters would be ~20 px)


def build_zzz(sc, col):
    """Big 'Z z Z' rising from just above her head while she sleeps: each letter fades in at the top of her head,
    drifts up and to her left, grows and fades out, then starts again (a loop). Shown from her eyes closing until
    the frame before WAKE (gone on the wake cut). They face the front cameras; in the top-down shot 12 they lie
    flat, turned to read upright from above. Shots in ZZZ_BOOST show them bigger (a per-shot cheat)."""
    font = bpy.data.fonts.load(CAPTION_FONT, check_existing=True)
    top = head_top(sc, (NAP_SHUT + WAKE) // 2) + Vector((0.02, -0.06, 0.05))
    a, b = NAP_SHUT + 8, WAKE                     # first letter appears; all hidden on WAKE
    flat = shot(12)
    out = []
    for i, body in enumerate("ZzZ"):
        m = flat_material("Zzz_%d" % i, lin((0xF2, 0xEC, 0xFF)), 2.5, alpha_fade=True)
        fade = m.node_tree.nodes["fade"].inputs["Fac"]
        cu = bpy.data.curves.new(P + "Zzz_%d" % i, "FONT")
        cu.body = body
        cu.font = font
        cu.size = ZZZ_SIZE
        cu.align_x = "CENTER"
        cu.align_y = "CENTER"
        cu.materials.append(m)
        ob = bpy.data.objects.new(P + "Zzz_%d" % i, cu)
        col.objects.link(ob)
        ob.rotation_mode = "XYZ"
        no_light_effects(ob)
        a_i = a + i * ZZZ_LOOP // 3
        vis(ob, 1, False)
        vis(ob, a_i, True)
        vis(ob, b, False)
        for f, rot in ((1, (math.radians(90), 0, 0)), (flat[2], (0, 0, math.pi)), (flat[3] + 1, (math.radians(90), 0, 0))):
            ob.rotation_euler = rot
            ob.keyframe_insert("rotation_euler", frame=f)
        for f in range(a_i, b + 1):                    # every frame: the loop wraps and the boost cuts are instant
            p = ((f - a_i) % ZZZ_LOOP) / ZZZ_LOOP
            k = next((ZZZ_BOOST.get(no, 1.0) for no, _, s0, s1 in SHOTS if s0 <= f <= s1), 1.0)
            ob.location = top + k * Vector((0.16 * p + 0.025 * math.sin(2 * math.pi * 1.5 * p), 0, 0.36 * p))
            s = k * (0.75 + 0.5 * p)
            ob.scale = (s, s, s)
            ob.keyframe_insert("location", frame=f)
            ob.keyframe_insert("scale", frame=f)
            key_socket(fade, f, smooth(p / 0.15) * (1 - smooth((p - 0.65) / 0.3)))
        key_socket(fade, a_i - 1, 0.0)
        set_interp(ob, {"hide_": "CONSTANT", "rotation_euler": "CONSTANT", "location": "LINEAR", "scale": "LINEAR"})
        set_interp(m.node_tree, {"": "LINEAR"})
        name_action(ob, ob.name[4:])
        name_action(m.node_tree, "Zzz_%d_fade" % i)
        out.append(ob)
    return out


# ================================================================ Clawd
def build_clawd(col, anchor):
    src = bpy.data.collections["MSC_Character"]
    arm_src = next(o for o in src.objects if o.type == "ARMATURE")
    copies = {}
    for o in src.objects:
        c = o.copy()
        c.name = P + "Clawd_" + o.name
        c.animation_data_clear()
        copies[o] = c
        col.objects.link(c)
    for o, c in copies.items():
        if o.parent in copies:
            c.parent = copies[o.parent]
            c.parent_type, c.parent_bone = o.parent_type, o.parent_bone
            c.matrix_parent_inverse = o.matrix_parent_inverse.copy()
    arm = copies[arm_src]
    arm.parent = anchor
    arm.matrix_parent_inverse = Matrix.Identity(4)
    arm.matrix_basis = Matrix.Diagonal((CLAWD_SCALE, CLAWD_SCALE, CLAWD_SCALE, 1))
    arm.hide_render = True
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    glow = {}
    for c in copies.values():
        for slot in getattr(c, "material_slots", []):
            m = slot.material
            if m is None:
                continue
            if m.name not in glow:
                g = own_material(m, "Clawd_" + m.name)
                b = bsdf(g)
                if b is not None:
                    b.inputs["Emission Color"].default_value = b.inputs["Base Color"].default_value
                    b.inputs["Emission Strength"].default_value = 0.0
                glow[m.name] = g
            slot.link = "OBJECT"
            slot.material = glow[m.name]
    eyes = {o["expression"]: o for o in copies.values() if "expression" in o.keys()}
    return arm, eyes, glow


def rot_basis(arm, bname, R3):
    b = arm.data.bones[bname]
    rest = b.matrix_local
    M = (R3 @ rest.to_3x3()).to_4x4()
    M.translation = rest.translation
    return rest.inverted() @ M


# desk path for the cleanup (world x, y) - fast motion through the open desk areas, back on the dock;
# every piece flies into Clawd as he passes (he hoovers the desk clean)
SWEEP_PATH = [(1967, (-0.30, -0.10)), (1972, (-0.44, -0.30)), (1977, (-0.465, 0.05)), (1982, (-0.42, 0.345)),
              (1990, (0.0, 0.345)), (1996, (0.32, 0.32)), (2001, (0.46, 0.30)), (2005, (0.32, 0.13)),
              (2010, (0.30, 0.33)), (2020, (-0.42, 0.345)), (2025, (-0.465, 0.05)), (2030, (-0.30, -0.10))]
DOCK_XY = Vector((-0.30, -0.10))


def sweep_xy(f):
    pts = SWEEP_PATH
    if f <= pts[0][0]:
        return Vector(pts[0][1])
    for (a, pa), (b, pb) in zip(pts, pts[1:]):
        if a <= f <= b:
            t = (f - a) / (b - a)
            return Vector(pa).lerp(Vector(pb), t)
    return Vector(pts[-1][1])


def clawd_state(f, talk, dance_w):
    """Per-frame pose of Clawd: dict(yaw deg, xy world or None, z, sq, pitch, roll, aL, aR)."""
    yaw_keys = [(1, 0), (118, 0), (130, 158), (NAP_SHUT + 23, 158), (NAP_SHUT + 41, 61), (MUSIC[0], 61), (MUSIC[0] + 12, 20),
                (FREEZE[1], 20), (FREEZE[1] + 12, 158), (1271, 158), (1285, 61), (1500, 61), (1512, 158),
                (WALK[0] + 6, 158), (WALK[0] + 18, 232), (WALK[1] - 20, 340), (1840, 360), (1848, 315), (1860, 315),
                (1868, 405), (1878, 405), (1886, 360), (1966, 360), (SWEEP[1] + 1, 350)]
    s = dict(yaw=interp_keys(yaw_keys, f), xy=None, z=0.0, sq=0.0, pitch=0.0, roll=0.0, aL=0.0, aR=0.0)
    for a, n, hgt in ((116, 12, 0.03), (1655, 12, 0.035), (1931, 6, 0.02)):
        if a <= f <= a + n:
            t = (f - a) / n
            s["z"] += hgt * math.sin(math.pi * t)
            if t < 0.15:
                s["sq"] += 0.10 * (1 - t / 0.15)
        if a + n < f <= a + n + 4:
            s["sq"] += 0.08 * (1 - (f - a - n) / 4)
    s["pitch"] = interp_keys([(1, 0), (398, 0), (406, 15), (440, 15), (448, 0), (SNEEZE - 8, 0), (SNEEZE - 2, -12),
                              (SNEEZE + 1, 22), (SNEEZE + 8, 0)], f)
    w = dance_w(f)
    if w > 0:
        t = f - MUSIC[0]
        beat = (t % 12) / 12
        s["z"] += w * 0.012 * abs(math.sin(math.pi * beat))
        s["roll"] = w * 16 * math.sin(2 * math.pi * t / 24)
        s["yaw"] += w * 28 * math.sin(2 * math.pi * t / 48)
        s["aL"] = w * 70 * max(0.0, math.sin(2 * math.pi * t / 24))
        s["aR"] = w * 70 * max(0.0, -math.sin(2 * math.pi * t / 24))
        s["sq"] += w * 0.05 * math.cos(2 * math.pi * beat)
    if DENY[0] <= f <= DENY[1]:                                     # "Nooo. No party." - quick innocent head shake
        env = math.sin(math.pi * (f - DENY[0]) / (DENY[1] - DENY[0]))
        s["yaw"] += 16 * env * math.sin(2 * math.pi * (f - DENY[0]) / 8)
        s["roll"] += 5 * env * math.sin(2 * math.pi * (f - DENY[0]) / 8 + 1.0)
    if GLANCE[0] <= f <= GLANCE[1]:                                 # "...Definitely..." - glances away, caught
        s["yaw"] += 48 * smooth((f - GLANCE[0]) / 6) * (1 - smooth((f - GLANCE[1] + 8) / 8))
    if SPIN[0] <= f:
        s["yaw"] += 360 * smooth((f - SPIN[0]) / (SPIN[1] - SPIN[0])) if f <= SPIN[1] else 0
    if talk.get(f) or talk.get(f + 1):
        amp = 0.5 if f >= 1930 else 1.0
        s["sq"] += amp * (0.07 if (f // 3) % 2 == 0 else -0.04)
        s["aR"] = max(s["aR"], amp * (25 if (f // 6) % 2 == 0 else 8))
    if 1655 <= f <= 1675:
        s["aL"] = s["aR"] = 65 * math.sin(math.pi * (f - 1655) / 20)
    if WALK[0] <= f <= WALK[0] + 40:                                # waves goodbye
        s["aL"] = 70 + 18 * math.sin(2 * math.pi * (f - WALK[0]) / 8)
    if 1931 <= f <= 1940:                                           # "...oh no." stretch
        s["sq"] -= 0.12 * math.sin(math.pi * (f - 1931) / 9)
    if SWEEP[0] <= f <= SWEEP[1]:
        xy = sweep_xy(f)
        nxt = sweep_xy(f + 2)
        d = nxt - xy
        if d.length > 1e-4:
            s["yaw"] = math.degrees(math.atan2(d.x, -d.y))          # face the way it runs
        s["xy"] = xy
        k = min(1.0, (xy - DOCK_XY).length / 0.06)                 # calm on the dock, frantic on the desk
        s["aL"] = 40 * k * abs(math.sin(math.pi * f / 3))
        s["aR"] = 40 * k * abs(math.cos(math.pi * f / 3))
        s["z"] += 0.008 * k * abs(math.sin(math.pi * f / 3))
    if SNEEZE - 8 <= f < SNEEZE:
        s["sq"] -= 0.10 * (f - SNEEZE + 8) / 8                      # inhale: stretch up
    if SNEEZE <= f <= SNEEZE + 5:
        s["sq"] += 0.16 * (1 - (f - SNEEZE) / 5)
    if SWEEP[1] < f:
        s["roll"] = 5 * math.sin(2 * math.pi * f / 36)              # innocent sway
    return s


def animate_clawd(sc, arm, eyes, glow, dock_glow, anchor):
    talk = talking("claude")
    listen = windows("girl", 2, 4)

    def dance_w(f):
        if FREEZE[0] <= f:
            return 0.0
        return smooth((f - MUSIC[0]) / 12) if f >= MUSIC[0] else 0.0

    inv = anchor.matrix_world.inverted()
    prev = {}
    yaws = []
    frames = list(range(1, END + 1, 2))
    states = []
    frozen = clawd_state(FREEZE[0] - 1, {}, lambda x: smooth((x - MUSIC[0]) / 12))
    for f in frames:
        s = clawd_state(f, talk, dance_w)
        if FREEZE[0] <= f < FREEZE[1]:                                 # freeze: hold the last dance pose
            s = dict(frozen)
        elif FREEZE[1] <= f < FREEZE[1] + 12:                          # then ease back to normal
            t = smooth((f - FREEZE[1]) / 12)
            s = {k: (frozen[k] + (v - frozen[k]) * t if isinstance(v, float) else v) for k, v in s.items()}
        states.append(s)
    # unwrap yaw so keys never spin the long way round
    yaw_prev = None
    for s in states:
        y = s["yaw"]
        if yaw_prev is not None:
            while y - yaw_prev > 180:
                y -= 360
            while y - yaw_prev < -180:
                y += 360
        s["yaw"] = y
        yaw_prev = y
    # FREEZE->her turn: the state machine's yaw keys handle it
    for f, s in zip(frames, states):
        if s["xy"] is not None:
            lp = inv @ Vector((s["xy"].x, s["xy"].y, anchor.matrix_world.translation.z))
            off = (s["xy"] - DOCK_XY).length
            dz = -0.04 * smooth((off - 0.08) / 0.04)                 # off the dock: down onto the desk
            loc = (lp.x, lp.y, s["z"] + dz)
        else:
            loc = (0, 0, s["z"])
        sq = s["sq"]
        arm.location = loc
        arm.rotation_mode = "XYZ"
        arm.rotation_euler = (0, 0, math.radians(s["yaw"]))
        arm.scale = (CLAWD_SCALE * (1 + 0.5 * sq), CLAWD_SCALE * (1 + 0.5 * sq), CLAWD_SCALE * (1 - sq))
        for p in ("location", "rotation_euler", "scale"):
            arm.keyframe_insert(p, frame=f)
        Rb = Matrix.Rotation(math.radians(s["pitch"]), 3, "X") @ Matrix.Rotation(math.radians(s["roll"]), 3, "Y")
        for bn, R in (("body", Rb), ("arm.L", Matrix.Rotation(math.radians(-s["aL"]), 3, "Y")),
                      ("arm.R", Matrix.Rotation(math.radians(s["aR"]), 3, "Y"))):
            pb = arm.pose.bones[bn]
            pb.rotation_mode = "QUATERNION"
            q = rot_basis(arm, bn, R).to_quaternion()
            if bn in prev and prev[bn].dot(q) < 0:
                q.negate()
            prev[bn] = q
            pb.rotation_quaternion = q
            pb.keyframe_insert("rotation_quaternion", frame=f)
    set_interp(arm, {"": "LINEAR"})
    name_action(arm, "Clawd")
    c2, c7, c9, c12 = voice(2)[0], voice(7)[0], voice(9)[0], voice(12)[0]
    ek = [(1, "neutral"), (30, "blink"), (33, "neutral"), (90, "blink"), (93, "neutral"), (116, "happy"),
          (130, "neutral"), (c2, "happy"), (c2 + 34, "neutral"), (250, "blink"), (253, "neutral"), (330, "blink"),
          (333, "neutral"), (395, "squint"), (448, "neutral"), (NAP_SHUT + 43, "squint"), (NAP_SHUT + 55, "neutral"),
          (MUSIC[0], "happy"), (MUSIC[1], "neutral"), (1058, "blink"), (1061, "happy"), (1096, "neutral"),
          (1112, "blink"), (1115, "neutral"), (1130, "happy"), (1146, "neutral"), (1210, "blink"), (1213, "neutral"), (c9, "happy"), (1333, "neutral"), (1512, "happy"),
          (1560, "blink"), (1563, "neutral"), (c12, "happy"), (1720, "neutral"), (1805, "blink"), (1808, "neutral"),
          (1850, "blink"), (1853, "neutral"), (SWEEP[0], "squint"), (SWEEP[1] + 1, "happy"), (2057, "blink"),
          (2060, "happy"), (SNEEZE - 2, "squint"), (SNEEZE + 8, "neutral"), (2090, "blink"), (2093, "happy")]
    for f, e in ek:
        show_only(list(eyes.values()), [eyes[e]], f)
    const_vis(list(eyes.values()))
    for g in glow.values():
        if "eye" in g.name:
            continue
        es = bsdf(g).inputs["Emission Strength"]
        for f in range(1, END + 1, 2):
            v = 0.0
            if in_any(listen, f):
                v = 0.35 + 0.25 * math.sin(2 * math.pi * f / 24)
            elif MUSIC[0] <= f < MUSIC[1]:
                v = 0.5 if (f // 6) % 2 == 0 else 0.15
            elif talk.get(f):
                v = 0.3
            elif 1655 <= f <= 1680:
                v = 0.6
            key_socket(es, f, v)
        name_action(g.node_tree, "glow_" + g.name)
    if dock_glow:
        es = bsdf(dock_glow).inputs["Emission Strength"]
        key_socket(es, 1, 1.0)
        for a, b in listen:
            for f, v in ((a - 4, 1.0), (a, 3.5), (b, 3.5), (b + 6, 1.0)):
                key_socket(es, f, v)
        for f, v in ((MUSIC[0] - 1, 1.0), (MUSIC[0], 3.0), (MUSIC[1] - 1, 3.0), (MUSIC[1], 1.0)):
            key_socket(es, f, v)
        name_action(dock_glow.node_tree, "dock_glow")


def build_rings(col, anchor):
    """Listening ripples on the dock whenever she speaks."""
    terra = lin((0xFF, 0xB0, 0x8A))
    listen = windows("girl", 2, 4)
    rings = []
    n = 40
    for i in range(3):
        m = flat_material("Listen_Ring_%d" % i, terra, 3.0, alpha_fade=True)
        verts, faces = [], []
        for k in range(n):
            a = 2 * math.pi * k / n
            verts += [(0.085 * math.cos(a), 0.085 * math.sin(a), 0), (0.095 * math.cos(a), 0.095 * math.sin(a), 0)]
        for k in range(n):
            a0, a1 = 2 * k, 2 * ((k + 1) % n)
            faces.append((a0, a1, a1 + 1, a0 + 1))
        me = bpy.data.meshes.new(P + "Listen_Ring_%d" % i)
        me.from_pydata(verts, [], faces)
        me.materials.append(m)
        ob = bpy.data.objects.new(P + "Listen_Ring_%d" % i, me)
        col.objects.link(ob)
        ob.parent = anchor
        ob.matrix_parent_inverse = Matrix.Identity(4)
        ob.location = (0, 0, 0.003)
        no_light_effects(ob)
        mix = m.node_tree.nodes["fade"]
        vis(ob, 1, False)
        for a, b in listen:
            vis(ob, a, True)
            vis(ob, b + 1, False)
            for f in range(a, b + 1, 2):
                p = ((f - a + 8 * i) % 24) / 24
                s = 1.0 + 1.3 * p
                ob.scale = (s, s, 1)
                ob.keyframe_insert("scale", frame=f)
                key_socket(mix.inputs["Fac"], f, (1 - p) * min(1.0, (f - a) / 6))
        set_interp(ob, {"hide_": "CONSTANT", "scale": "LINEAR"})
        set_interp(m.node_tree, {"": "LINEAR"})
        name_action(ob, ob.name[4:])
        name_action(m.node_tree, ob.name[4:] + "_fade")
        rings.append(ob)
    return rings


# ================================================================ the party
def party_color(f, offset=0, step=12):
    return DISCO_LIN[((f - MUSIC[0]) // step + offset) % 5]


def build_party(sc, col, S):
    m0, m1 = MUSIC
    n0, n1 = NEON
    # daylight: late afternoon -> dusk -> party dark -> (WAKE: straight back to dusk, as if nothing happened)
    for o in S["day"]:
        e0 = o.data.energy
        for f, k in ((1, 1.0), (DUSK[0], 1.0), (DUSK[1], 0.45), (n0, 0.45), (n1, 0.15), (m1 - 1, 0.15), (m1, 0.45), (END, 0.45)):
            key(o.data, "energy", f, e0 * k)
        set_interp(o.data, {"energy": "LINEAR"})
        name_action(o.data, o.name[4:])
    # neon materials: walls, panel, shelf, posters and frames
    for mat, ci, peak in S["neon"]:
        b = bsdf(mat)
        if b is None:
            continue
        es, ec = b.inputs["Emission Strength"], b.inputs["Emission Color"]
        for f, v in ((1, 0.0), (n0, 0.0), (n1, peak), (m1 - 1, peak), (m1, 0.0)):
            key_socket(es, f, v)
        key_socket(ec, 1, NEON_LIN[ci] + (1.0,))
        for k, f in enumerate(range(m0, m1, 12)):
            key_socket(ec, f, NEON_LIN[(ci + k) % 3] + (1.0,))
        key_socket(ec, m1, NEON_LIN[ci] + (1.0,))
        set_interp(mat.node_tree, {"Emission Strength": "LINEAR"})
        for fc in fcurves_of(mat.node_tree):
            if fc.data_path.endswith("default_value") and fc.array_index >= 0 and len(fc.keyframe_points) > 6:
                for kp in fc.keyframe_points:
                    kp.interpolation = "CONSTANT"
        name_action(mat.node_tree, mat.name[4:])
    # floor lamp: off, blinking neon at the party, off again on WAKE
    for k, m in enumerate(S["lamp_mats"]):
        bb = bsdf(m)
        es, ec, bc = bb.inputs["Emission Strength"], bb.inputs["Emission Color"], bb.inputs["Base Color"]
        warm = tuple(bc.default_value)
        key_socket(es, 1, 0.0)
        for f in range(m0, m1, 3):
            key_socket(es, f, 9.0 if ((f - m0) // 3) % 2 == 0 else 2.5)
        key_socket(es, m1, 0.0)
        key_socket(ec, 1, warm)
        key_socket(bc, 1, warm)
        for f in range(m0, m1, 6):
            c = party_color(f, 2 * k, 6) + (1.0,)
            key_socket(ec, f, c)
            key_socket(bc, f, c)
        key_socket(ec, m1, warm)
        key_socket(bc, m1, warm)
        set_interp(m.node_tree, {"": "CONSTANT"})
        name_action(m.node_tree, m.name[4:])
    lights = []
    for nm in ("STU_Lamp_Light_A", "STU_Lamp_Light_B"):
        o = copy_obj(bpy.data.objects[nm], nm[4:], col, data=True)
        warm, e0 = tuple(o.data.color), o.data.energy
        key(o.data, "energy", 1, 0.0)
        for f in range(m0, m1, 3):
            key(o.data, "energy", f, e0 * (1.6 if ((f - m0) // 3) % 2 == 0 else 0.5))
        key(o.data, "energy", m1, 0.0)
        key(o.data, "color", 1, warm)
        for f in range(m0, m1, 6):
            key(o.data, "color", f, party_color(f, 1, 6))
        key(o.data, "color", m1, warm)
        set_interp(o.data, {"": "CONSTANT"})
        name_action(o.data, o.name[4:])
        lights.append(o)
    # coloured washes on the walls (pink back, cyan left, purple right)
    for i, (loc, rot) in enumerate((((0, 0.9, 2.5), (math.radians(-60), 0, 0)),
                                    ((-0.9, -0.3, 2.4), (0, math.radians(-60), 0)),
                                    ((0.9, -0.3, 2.4), (0, math.radians(60), 0)))):
        ld = bpy.data.lights.new(P + "Neon_%d" % i, "AREA")
        ld.size = 1.2
        o = bpy.data.objects.new(P + "Neon_%d" % i, ld)
        col.objects.link(o)
        o.location, o.rotation_euler = loc, rot
        for f, v in ((1, 0.0), (n0, 0.0), (n1, 160.0), (m1 - 1, 160.0), (m1, 0.0)):
            key(ld, "energy", f, v)
        key(ld, "color", 1, NEON_LIN[i])
        for k, f in enumerate(range(m0, m1, 12)):
            key(ld, "color", f, NEON_LIN[(i + k) % 3])
        key(ld, "color", m1, NEON_LIN[i])
        set_interp(ld, {"color": "CONSTANT", "energy": "LINEAR"})
        name_action(ld, o.name[4:])
        lights.append(o)
    # two sweeping ceiling spots + the screen glow on her face, music only
    for i in range(2):
        ld = bpy.data.lights.new(P + "Sweep_%d" % i, "SPOT")
        ld.spot_size = math.radians(30)
        ld.spot_blend = 0.35
        o = bpy.data.objects.new(P + "Sweep_%d" % i, ld)
        col.objects.link(o)
        o.location = (0.0, 0.3, 2.7)
        o.rotation_mode = "ZYX"
        for f in (m0, m1):
            o.rotation_euler = (math.radians(38), 0, math.radians(180 * i + 360 * (f - m0) / 48))
            o.keyframe_insert("rotation_euler", frame=f)
        set_interp(o, {"rotation": "LINEAR"})
        name_action(o, o.name[4:])
        for f, v in ((1, 0.0), (m0 - 1, 0.0), (m0, 700.0), (m1 - 1, 700.0), (m1, 0.0)):
            key(ld, "energy", f, v)
        for f in range(m0, m1, 6):
            key(ld, "color", f, party_color(f, i * 2, 6))
        set_interp(ld, {"": "CONSTANT"})
        name_action(ld, o.name[4:])
        lights.append(o)
    ld = bpy.data.lights.new(P + "Light_Rainbow", "AREA")
    ld.size = 0.30
    o = bpy.data.objects.new(P + "Light_Rainbow", ld)
    col.objects.link(o)
    scr, c, n = screen_frame()
    o.matrix_world = Matrix.Translation(c + n * 0.05) @ n.to_track_quat("-Z", "Y").to_matrix().to_4x4()
    for f, v in ((1, 0.0), (BURST - 1, 0.0), (BURST, 40.0), (m1 - 1, 40.0), (m1, 0.0)):
        key(ld, "energy", f, v)
    for f in range(BURST, m1, 3):
        key(ld, "color", f, party_color(f, 0, 3))
    set_interp(ld, {"": "CONSTANT"})
    name_action(ld, o.name[4:])
    lights.append(o)
    return lights


def build_ball(col):
    """Mirror ball: comes down from the ceiling, spins, throws coloured spots; simply gone on WAKE (a dream)."""
    down0, down1 = BALL
    piv = bpy.data.objects.new(P + "DiscoBall_Pivot", None)
    col.objects.link(piv)
    piv.location = (0.0, -0.8, 3.3)
    for f, z in ((1, 3.3), (down0, 3.3), (down1, 2.15)):
        key(piv, "location", f, z, 2)
    name_action(piv, "DiscoBall_Pivot")
    mirror = bpy.data.materials.new(P + "DiscoBall_Mirror")
    mirror.use_nodes = True
    b = bsdf(mirror)
    b.inputs["Base Color"].default_value = (0.85, 0.86, 0.9, 1)
    b.inputs["Metallic"].default_value = 1.0
    b.inputs["Roughness"].default_value = 0.08
    sparkle = flat_material("DiscoBall_Sparkle", (1, 1, 1), 6.0)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.17)
    me = bpy.data.meshes.new(P + "DiscoBall")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mirror)
    me.materials.append(sparkle)
    rnd = random.Random(9)
    for poly in me.polygons:
        poly.material_index = 1 if rnd.random() < 0.18 else 0
        poly.use_smooth = False
    ball = bpy.data.objects.new(P + "DiscoBall", me)
    col.objects.link(ball)
    ball.parent = piv
    ball.rotation_mode = "XYZ"
    rot_end_fast = 2 * math.pi * (MUSIC[1] - down0) / 96
    for f, r in ((down0, 0.0), (MUSIC[1], rot_end_fast)):
        key(ball, "rotation_euler", f, r, 2)
    set_interp(ball, {"rotation": "LINEAR"})
    name_action(ball, "DiscoBall")
    # string up into the ceiling
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.004, radius2=0.004, depth=1.4)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, 0.17 + 0.7))
    sme = bpy.data.meshes.new(P + "DiscoBall_String")
    bm.to_mesh(sme)
    bm.free()
    sme.materials.append(mirror)
    string = bpy.data.objects.new(P + "DiscoBall_String", sme)
    col.objects.link(string)
    string.parent = piv
    spots = []
    for i in range(4):
        ld = bpy.data.lights.new(P + "Ball_Spot_%d" % i, "SPOT")
        ld.spot_size = math.radians(14)
        ld.spot_blend = 0.2
        ld.color = DISCO_LIN[i]
        o = bpy.data.objects.new(P + "Ball_Spot_%d" % i, ld)
        col.objects.link(o)
        o.parent = ball
        a = math.pi / 2 * i + 0.4
        d = Vector((math.cos(a), math.sin(a), -0.6)).normalized()
        o.matrix_basis = Matrix.Translation(d * 0.2) @ d.to_track_quat("-Z", "Y").to_matrix().to_4x4()
        for f, v in ((1, 0.0), (down0, 0.0), (down0 + 20, 600.0), (MUSIC[1] - 1, 600.0), (MUSIC[1], 0.0)):
            key(ld, "energy", f, v)
        set_interp(ld, {"energy": "LINEAR"})
        name_action(ld, o.name[4:])
        spots.append(o)
    for o in (ball, string):
        vis(o, 1, False)
        vis(o, down0 - 2, True)
        vis(o, MUSIC[1], False)
        const_vis([o])
        name_action(o, o.name[4:])
    # sparkles thrown at the lens in the orbit close-up
    sp = []
    a, b = shot(10)[2], shot(10)[3]
    mats = [flat_material("Ball_Sparkle_%d" % i, DISCO_LIN[i], 8.0) for i in range(5)]
    for i in range(14):
        s = 0.006
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=2 * s)
        sm = bpy.data.meshes.new(P + "Ball_Sparkle_%02d" % i)
        bm.to_mesh(sm)
        bm.free()
        sm.materials.append(mats[i % 5])
        o = bpy.data.objects.new(P + "Ball_Sparkle_%02d" % i, sm)
        col.objects.link(o)
        no_light_effects(o)
        d = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, -0.2))).normalized()
        t0 = a + rnd.randint(0, 24)
        vis(o, 1, False)
        vis(o, t0, True)
        vis(o, min(b + 1, t0 + 20), False)
        for f in range(t0, t0 + 21, 2):
            o.location = Vector((0, -0.8, 2.15)) + d * (0.18 + 0.05 * (f - t0))
            o.rotation_euler = (0.3 * (f - t0), 0.2 * (f - t0), 0)
            o.keyframe_insert("location", frame=f)
            o.keyframe_insert("rotation_euler", frame=f)
        const_vis([o])
        name_action(o, o.name[4:])
        sp.append(o)
    return piv, ball, spots


# ================================================================ confetti
DESK_TOP = 0.726
KB_TOP = 0.736


def desk_spots(n, seed=17):
    rnd = random.Random(seed)
    keep = []
    rects = [(-0.21, 0.21, -0.32, 0.05), (0.33, 0.51, -0.15, -0.01), (-0.29, -0.21, 0.13, 0.25), (-0.59, -0.45, 0.29, 0.36)]
    circles = [((-0.30, -0.10), 0.11), ((0.60, 0.14), 0.07), ((0.62, -0.24), 0.06), ((-0.58, -0.12), 0.09)]
    while len(keep) < n:
        x, y = rnd.uniform(-0.62, 0.62), rnd.uniform(-0.33, 0.34)
        if any(a <= x <= b and c <= y <= d for a, b, c, d in rects):
            continue
        if any((x - cx) ** 2 + (y - cy) ** 2 < r * r for (cx, cy), r in circles):
            continue
        z = KB_TOP if (-0.14 <= x <= 0.14 and 0.132 <= y <= 0.248) else DESK_TOP
        keep.append(Vector((x, y, z)))
    return keep


def confetti_piece(name, mat, col):
    s = 0.008
    me = bpy.data.meshes.new(P + name)
    me.from_pydata([(-s, -s * 0.6, 0), (s, -s * 0.6, 0), (s, s * 0.6, 0), (-s, s * 0.6, 0)], [], [(0, 1, 2, 3)])
    me.materials.append(mat)
    ob = bpy.data.objects.new(P + name, me)
    col.objects.link(ob)
    no_light_effects(ob)
    return ob


def build_confetti(sc, col, rig):
    mats = [flat_material("Confetti_%d" % i, DISCO_LIN[i], 2.0) for i in range(5)]
    rnd = random.Random(5)
    spots = desk_spots(54)
    pieces = []
    for i, spot in enumerate(spots):
        ob = confetti_piece("Confetti_%02d" % i, mats[i % 5], col)
        t0 = rnd.randint(*RAIN)
        dur = rnd.randint(24, 30)
        p0 = spot + Vector((rnd.uniform(-0.25, 0.25), rnd.uniform(-0.25, 0.25), 0))
        p0.z = rnd.uniform(1.9, 2.3)
        spin = Vector((rnd.uniform(-9, 9), rnd.uniform(-9, 9), rnd.uniform(-6, 6)))
        flat = rnd.uniform(0, math.pi)
        vis(ob, 1, False)
        vis(ob, t0, True)
        for f in range(t0, t0 + dur + 1, 2):
            t = (f - t0) / dur
            p = p0.lerp(spot, t)
            p.z = p0.z + (spot.z - p0.z) * t
            p.x += 0.03 * math.sin(9 * t + i) * (1 - t)
            ob.location = p
            ob.rotation_euler = tuple(spin * (1 - t) * 0.3) if t < 1 else (0, 0, flat)
            ob.keyframe_insert("location", frame=f)
            ob.keyframe_insert("rotation_euler", frame=f)
        ob.location, ob.rotation_euler = spot, (0, 0, flat)
        ob.keyframe_insert("location", frame=t0 + dur + 1)
        ob.keyframe_insert("rotation_euler", frame=t0 + dur + 1)
        vis(ob, WAKE, False)                 # her shots never show it ...
        vis(ob, CONFETTI_BACK, True)         # ... but the party really happened
        pieces.append((ob, spot, flat))
    # the last piece floating down in the desk insert
    last = confetti_piece("Confetti_Last", mats[0], col)
    spot = Vector((0.26, 0.10, DESK_TOP))
    a, b = LAST_PIECE
    vis(last, 1, False)
    vis(last, a, True)
    for f in range(a, b + 1, 2):
        t = (f - a) / (b - a)
        last.location = spot + Vector((0.05 * math.sin(7 * t), 0.02 * math.cos(5 * t), (1.25 - DESK_TOP) * (1 - t)))
        last.rotation_euler = (0.6 * math.sin(6 * t) * (1 - t), 0.4 * math.cos(5 * t) * (1 - t), 1.0)
        last.keyframe_insert("location", frame=f)
        last.keyframe_insert("rotation_euler", frame=f)
    pieces.append((last, spot, 1.0))
    # cleanup: Clawd hoovers up every piece as he runs past it - it flies into him and is gone; desk spotless
    path_frames = range(SWEEP[0], SWEEP[1] + 1)
    for k, (ob, spot, flat) in enumerate(pieces):
        tn = min(path_frames, key=lambda f: (sweep_xy(f) - spot.xy).length)
        tn = min(tn, SWEEP[1] - 12)
        into = sweep_xy(tn + 5).to_3d()
        into.z = 0.80
        for f, loc, sc_, rot in ((tn, spot, 1.0, (0, 0, flat)), (tn + 2, spot.lerp(into, 0.3) + Vector((0, 0, 0.03)), 0.9, (0.8, 0.3, flat)),
                                 (tn + 5, into, 0.15, (1.6, 0.6, flat))):
            ob.location, ob.rotation_euler, ob.scale = loc, rot, (sc_, sc_, sc_)
            for pth in ("location", "rotation_euler", "scale"):
                ob.keyframe_insert(pth, frame=f)
        vis(ob, tn + 6, False)
        set_interp(ob, {"hide_": "CONSTANT"})
        name_action(ob, ob.name[4:])
    # the sneeze: one piece shoots out of Clawd towards the lens
    sn = confetti_piece("Confetti_Sneeze", mats[1], col)
    cam_loc = Vector((-0.34, -0.46, 0.85))
    start = Vector((-0.30, -0.15, 0.86))
    vis(sn, 1, False)
    vis(sn, SNEEZE, True)
    for f in range(SNEEZE, shot(26)[3] + 1, 2):
        t = smooth((f - SNEEZE) / 14)
        sn.location = start.lerp(cam_loc + Vector((0.03, 0.12, 0.0)), t * 0.85)
        sn.rotation_euler = (1.4 + 0.5 * (f - SNEEZE), 0.3 * (f - SNEEZE), 0)
        sn.keyframe_insert("location", frame=f)
        sn.keyframe_insert("rotation_euler", frame=f)
    vis(sn, shot(26)[3] + 1, False)
    const_vis([sn])
    name_action(sn, sn.name[4:])
    sc.frame_set(1)
    return [p[0] for p in pieces]


# ================================================================ cameras
def make_cam(col, name, lens):
    cd = bpy.data.cameras.new(P + "Cam_" + name)
    cd.lens, cd.sensor_fit, cd.sensor_width, cd.clip_start, cd.clip_end = lens, "AUTO", 36.0, 0.01, 30.0
    ob = bpy.data.objects.new(P + "Cam_" + name, cd)
    col.objects.link(ob)
    ob.rotation_mode = "XYZ"
    return ob


def key_cam(ob, f, loc, tgt=None, lens=None, roll=0.0, top_yaw=None):
    if top_yaw is not None:
        M = Matrix.Translation(Vector(loc)) @ Matrix.Rotation(top_yaw, 4, "Z")
    else:
        M = look_at(loc, tgt) @ Matrix.Rotation(math.radians(roll), 4, "Z")
    ob.location = Vector(loc)
    ob.rotation_euler = M.to_euler("XYZ", ob.rotation_euler)
    ob.keyframe_insert("location", frame=f)
    ob.keyframe_insert("rotation_euler", frame=f)
    if lens:
        ob.data.lens = lens
        ob.data.keyframe_insert("lens", frame=f)


def shake(ob, strength, scale, a, b, seed):
    for fc in fcurves_of(ob):
        if fc.data_path == "rotation_euler":
            m = fc.modifiers.new("NOISE")
            m.strength, m.scale, m.phase = strength, scale, seed + 7 * fc.array_index
            m.use_restricted_range = True
            m.frame_start, m.frame_end = a, b
            m.blend_in = m.blend_out = 2


def build_cameras(sc, col):
    D = bpy.data.objects
    CL = Vector((-0.30, -0.10, 0.85))                 # Clawd
    BALLC = Vector((0.0, -0.8, 2.15))
    scr, sc_c, n = screen_frame()
    wide = D["STU_Cam_Wide"]
    wide_fwd = (wide.matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized()
    cams = {}

    def cam(no, lens):
        s = shot(no)
        ob = make_cam(col, "S%02d_%s" % (no, s[1]), lens)
        cams[no] = ob
        return ob, s[2], s[3]

    ob, a, b = cam(1, 26)                                                       # wide, slow push-in
    w0 = wide.matrix_world.translation
    key_cam(ob, a, w0, w0 + wide_fwd * 3, 26)
    key_cam(ob, b, w0 + wide_fwd * 0.5, w0 + wide_fwd * 3.5, 26)
    ob, a, b = cam(2, 35)                                                       # keys, static
    key_cam(ob, a, (-0.40, 0.04, 0.94), (-0.115, 0.15, 0.745), 35)
    ob, a, b = cam(3, 30)                                                       # Clawd, low, small push-in
    key_cam(ob, a, (-0.40, 0.24, 0.82), CL, 30)
    key_cam(ob, b, (-0.38, 0.16, 0.83), CL, 30)
    ob, a, b = cam(4, 35)                                                       # face, very slow push-in
    fp = face_point(sc, (a + b) // 2) + Vector((0, 0.08, 0.05))
    key_cam(ob, a, (0.42, -0.36, 1.32), fp, 35)
    key_cam(ob, b, (0.34, -0.24, 1.29), fp, 35)
    ob, a, b = cam(5, 35)                                                       # over Clawd's shoulder, her face
    key_cam(ob, a, (-0.45, -0.28, 0.93), face_point(sc, 340), 35)
    ob, a, b = cam(6, 30)                                                       # Clawd, quick push-in
    key_cam(ob, a, (-0.40, 0.24, 0.86), CL, 30)
    key_cam(ob, a + 10, (-0.37, 0.12, 0.86), CL, 30)
    key_cam(ob, b, (-0.365, 0.11, 0.86), CL, 30)
    ob, a, b = cam(7, 32)                                                       # front medium, slow pull-out
    key_cam(ob, a, (-0.25, -0.95, 1.20), (-0.14, 0.20, 1.0), 32)
    key_cam(ob, b, (-0.32, -1.40, 1.25), (-0.14, 0.20, 1.0), 32)
    ob, a, b = cam(8, 20)                                                       # screen, fast push-in
    key_cam(ob, a, sc_c + n * 0.42, sc_c, 20)
    key_cam(ob, a + 16, sc_c + n * 0.22, sc_c, 20)
    key_cam(ob, b, sc_c + n * 0.21, sc_c, 20)
    ob, a, b = cam(9, 12)                                                       # wide fisheye: roll + beat bob
    for f in range(a, b + 1, 6):
        t = (f - a) / (b - a)
        bob = 0.02 if ((f - a) // 6) % 2 else 0.0
        key_cam(ob, f, (0.0, -2.2, 1.45 + bob), (0.0, 0.3, 1.25 + bob), 12, roll=-5 + 10 * t)
    ob, a, b = cam(10, 24)                                                      # disco ball, low angle orbit
    for f in range(a, b + 1, 2):
        ang = math.radians(200 + 90 * (f - a) / (b - a))
        key_cam(ob, f, BALLC + Vector((0.75 * math.cos(ang), 0.75 * math.sin(ang), -0.45)), BALLC, 24)
    set_interp(ob, {"": "LINEAR"})
    ob, a, b = cam(11, 45)                                                      # Clawd: whip pan in + handheld
    loc = Vector((-0.52, -0.62, 0.98))
    away = loc + Matrix.Rotation(math.radians(75), 3, "Z") @ (CL - loc)
    key_cam(ob, a, loc, away, 45)
    key_cam(ob, a + 5, loc, CL, 45)
    key_cam(ob, b, loc + Vector((0.02, 0.03, 0)), CL, 45)
    shake(ob, 0.02, 3.0, a + 5, b, 1)
    ob, a, b = cam(12, 12)                                                      # top-down fisheye, slow spin
    key_cam(ob, a, (0.0, 0.15, 2.35), lens=12, top_yaw=math.pi)
    key_cam(ob, b, (0.0, 0.15, 2.35), lens=12, top_yaw=math.pi + 0.6)
    set_interp(ob, {"": "LINEAR"})
    ob, a, b = cam(13, 45)                                                      # face: crash zoom
    fp = face_point(sc, WAKE + 10)
    key_cam(ob, a, (0.40, -0.32, 1.30), fp, 14)
    key_cam(ob, a + 6, (0.40, -0.32, 1.30), fp, 45)
    key_cam(ob, b, (0.38, -0.29, 1.30), fp, 45)
    ob, a, b = cam(14, 32)                                                      # Clawd from her side, static
    key_cam(ob, a, (-0.36, 0.20, 0.92), CL + Vector((0, 0, -0.02)), 32)
    ob, a, b = cam(15, 35)                                                      # face, handheld
    key_cam(ob, a, (0.30, -0.28, 1.27), face_point(sc, (a + b) // 2), 35)
    key_cam(ob, b, (0.29, -0.27, 1.27), face_point(sc, (a + b) // 2), 35)
    shake(ob, 0.008, 6.0, a, b, 2)
    ob, a, b = cam(16, 35)                                                      # over Clawd's shoulder, slow push
    fp = face_point(sc, 1310)                                                   # she has turned to the screen
    key_cam(ob, a, (-0.47, -0.30, 0.94), fp, 35)
    key_cam(ob, b, (-0.42, -0.22, 0.93), fp, 35)
    ob, a, b = cam(17, 20)                                                      # screen, slow push-in
    key_cam(ob, a, sc_c + n * 0.42, sc_c, 20)
    key_cam(ob, b, sc_c + n * 0.31, sc_c, 20)
    ob, a, b = cam(18, 35)                                                      # face, slow push-in
    fp = face_point(sc, (a + b) // 2) + Vector((0, 0.08, 0.05))
    key_cam(ob, a, (0.40, -0.33, 1.31), fp, 35)
    key_cam(ob, b, (0.33, -0.22, 1.28), fp, 35)
    ob, a, b = cam(19, 32)                                                      # front medium, static
    key_cam(ob, a, (-0.30, -1.25, 1.22), (-0.14, 0.15, 1.0), 32)
    ob, a, b = cam(20, 30)                                                      # Clawd's proud hop
    key_cam(ob, a, (-0.38, 0.22, 0.88), CL, 30)
    ob, a, b = cam(21, 26)                                                      # wide, static, she walks out
    key_cam(ob, a, w0, w0 + wide_fwd * 3, 26)
    ob, a, b = cam(22, 35)                                                      # Clawd alone, very slow push-in
    key_cam(ob, a, (-0.33, -0.52, 0.86), CL, 35)
    key_cam(ob, b, (-0.325, -0.46, 0.86), CL, 35)
    ob, a, b = cam(23, 22)                                                      # desk insert, top-down
    key_cam(ob, a, (0.20, 0.06, 1.45), lens=22, top_yaw=math.pi)               # over where the last piece lands
    ob, a, b = cam(24, 60)                                                      # Clawd: snap zoom
    key_cam(ob, a, (-0.33, -0.50, 0.86), CL, 28)
    key_cam(ob, a + 3, (-0.33, -0.50, 0.86), CL, 60)
    key_cam(ob, b, (-0.33, -0.50, 0.86), CL, 60)
    ob, a, b = cam(25, 20)                                                      # top-down, fast-motion sweep
    key_cam(ob, a, (0.0, 0.0, 1.70), lens=20, top_yaw=math.pi)
    ob, a, b = cam(26, 40)                                                      # Clawd, innocent
    key_cam(ob, a, (-0.34, -0.46, 0.85), CL, 40)
    ob, a, b = cam(27, 50)                                                      # end card
    card = D["EP1_Cam_Card"]
    ob.location = card.matrix_world.translation
    ob.rotation_euler = card.matrix_world.to_euler()
    for o in cams.values():
        name_action(o, o.name[4:])
        if o.data.animation_data:
            name_action(o.data, o.name[4:] + "_lens")
            for fc in fcurves_of(o.data):
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
    return cams


def text_spans():
    """[(caption name, first, last)] for every subtitle, split at the pauses of each line."""
    out = []
    for i, (fname, start, who, parts) in enumerate(VOICES):
        a, b = voice(i + 1)
        nxt = VOICES[i + 1][1] - 2 if i + 1 < len(VOICES) else END
        end = min(b + 6, nxt)
        for k, (off, img) in enumerate(parts):
            lo = start + off
            hi = start + parts[k + 1][0] - 1 if k + 1 < len(parts) else end
            out.append((img, lo, hi))
    return out


# ================================================================ compositor (fisheye)
def build_fisheye_group():
    """Lens Distortion as a compositor node group for the Video Sequencer 'Compositor' strip modifier.
    The edit scene cuts its EP2_Inspiration Scene strip at the fisheye shots and only those pieces carry it,
    so it shows in the sequencer preview as well as in the final render (no keyframes needed)."""
    ng = bpy.data.node_groups.new(P + "Fisheye", "CompositorNodeTree")
    ng.interface.new_socket(name="Image", in_out="INPUT", socket_type="NodeSocketColor")
    ng.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    gi = ng.nodes.new("NodeGroupInput")
    ld = ng.nodes.new("CompositorNodeLensdist")
    ld.name = "Fisheye"
    out = ng.nodes.new("NodeGroupOutput")
    ng.links.new(gi.outputs[0], ld.inputs["Image"])
    ng.links.new(ld.outputs["Image"], out.inputs[0])
    ld.inputs["Distortion"].default_value = 0.35
    ld.inputs["Dispersion"].default_value = 0.03
    try:
        ld.inputs["Fit"].default_value = True
    except Exception:
        pass
    return ng


# ================================================================ sound
def build_sound(sc):
    se = sc.sequence_editor or sc.sequence_editor_create()
    strips = se.strips if hasattr(se, "strips") else se.sequences
    out = []
    for fname, f, who, _ in VOICES:
        st = strips.new_sound(name=P + "VO_" + fname[:-4], filepath=os.path.join(EP, "audio", "voice", fname),
                              channel=2 if who == "girl" else 3, frame_start=f)
        out.append((st.name, st.frame_final_start, st.frame_final_end - 1, st.channel))
    sfx = os.path.join(EP, "audio", "sfx")
    fx = [(sfx, "clock.wav", 1, 5, 0.35), (SHARED_SFX, "enter.wav", PRESS[0], 4, 0.8), (SHARED_SFX, "chime.wav", PRESS[0] + 1, 5, 0.5),
          (SHARED_SFX, "pop.wav", BURST, 4, 0.7), (sfx, "whoosh.wav", shot(11)[2] - 2, 5, 0.6),
          (sfx, "whoosh.wav", shot(13)[2] - 2, 5, 0.6), (sfx, "scratch.wav", WAKE, 4, 0.9),
          (SHARED_SFX, "chime.wav", MOODBOARD, 5, 0.5), (sfx, "clock.wav", shot(22)[2], 5, 0.35),
          (sfx, "whoosh.wav", shot(24)[2] - 2, 5, 0.5), (sfx, "chip.wav", SWEEP[0], 3, 0.5),
          (sfx, "sneeze.wav", SNEEZE - 9, 4, 0.8)]
    if END_CARD:
        fx.append((SHARED_SFX, "chime.wav", shot(27)[2], 5, 0.6))
    fx += [(SHARED_SFX, "pop.wav", f, 4, 0.5) for f in SWATCHES]
    fx += [(sfx, "step.wav", f, 5, 0.5) for f in range(WALK[0] + 4, WALK[1] + 1, 8)]
    for f in range(MUSIC[0], MUSIC[1], 72):
        fx.append((SHARED_MUSIC, "disco.wav", f, 3, 0.55))
    for i, (d, fname, f, ch, vol) in enumerate(fx):
        st = strips.new_sound(name="%sFX_%02d_%s" % (P, i, fname[:-4]), filepath=os.path.join(d, fname), channel=ch + 1,
                              frame_start=f)
        st.volume = vol
        if fname == "disco.wav" and st.frame_final_end > MUSIC[1]:
            st.frame_final_end = MUSIC[1]
    try:
        sc.sync_mode = "AUDIO_SYNC"
    except Exception:
        pass
    return out


# ================================================================ edit scene (Video Sequencer)
def srgb(c):
    """Text strip colours are COLOR_GAMMA (display sRGB), so 0-255 sRGB values go in as they are."""
    return tuple(v / 255 for v in c)


def set_output(sc):
    ims = sc.render.image_settings
    try:
        if hasattr(ims, "media_type"):
            ims.media_type = "VIDEO"
        ims.file_format = "FFMPEG"
        sc.render.ffmpeg.format = "MPEG4"
        sc.render.ffmpeg.codec = "H264"
        sc.render.ffmpeg.audio_codec = "AAC"
    except Exception as exc:
        print("video output not set:", exc)
    sc.render.filepath = os.path.join(EP, "renders", "ep-002_")


def build_captions(edit):
    """Subtitles as text strips: white bold on a dark rounded box (her) / on a Claude-orange box with a small
    'Claude' tag above (Claude). Centred, text centre at CAPTION_Y, max 2 lines (line breaks from captions.json)."""
    import json
    caps = json.load(open(os.path.join(EP, "overlays", "captions.json"), encoding="utf-8"))
    font = bpy.data.fonts.load(CAPTION_FONT, check_existing=True)
    strips = edit.sequence_editor.strips
    H = edit.render.resolution_y
    lead = 1.2 * CAPTION_SIZE
    made = []
    for name, a, b in text_spans():
        if a > edit.frame_end:
            continue
        b = min(b, edit.frame_end)
        cap = caps[name]
        st = strips.new_effect(name="%sSub_%s" % (P, name), type="TEXT", channel=7, frame_start=a, length=b - a + 1)
        st.text = "\n".join(cap["lines"])
        st.font = font
        st.font_size = CAPTION_SIZE
        st.color = (1, 1, 1, 1)
        st.use_box = True
        st.box_margin = 0.022
        st.box_roundness = 0.6
        st.box_color = srgb(CLAUDE_RGB if cap["who"] == "claude" else INK_RGB) + (0.94,)
        st.alignment_x = "CENTER"
        st.anchor_x = "CENTER"
        st.anchor_y = "CENTER"
        st.location = (0.5, CAPTION_Y)
        st.wrap_width = 0.0
        if cap["who"] == "claude":
            half = (len(cap["lines"]) * lead / 2) / H + 0.022 * edit.render.resolution_x / H
            tag = strips.new_effect(name="%sTag_%s" % (P, name), type="TEXT", channel=8, frame_start=a, length=b - a + 1)
            tag.text = "Claude"
            tag.font = font
            tag.font_size = 34
            tag.color = srgb(CLAUDE_RGB) + (1.0,)
            tag.use_box = True
            tag.box_margin = 0.012
            tag.box_roundness = 1.0
            tag.box_color = srgb(INK_RGB) + (0.94,)
            tag.alignment_x = "CENTER"
            tag.anchor_x = "CENTER"
            tag.anchor_y = "CENTER"
            tag.location = (0.5, CAPTION_Y + half + 0.028)
        made.append((st.name, a, b, cap["who"]))
    return made


def build_edit(sc):
    """EP2_Edit: the 3D scene as Scene strips (cameras switched by its markers), the fisheye shots carry a
    Compositor strip modifier, all sound, subtitles on top. This is the scene to watch and to render."""
    edit = bpy.data.scenes.new(EDIT)
    for a in ("resolution_x", "resolution_y", "resolution_percentage", "fps", "fps_base", "pixel_aspect_x", "pixel_aspect_y"):
        setattr(edit.render, a, getattr(sc.render, a))
    for a in ("view_transform", "look", "exposure", "gamma"):
        try:
            setattr(edit.view_settings, a, getattr(sc.view_settings, a))
        except Exception:
            pass
    edit.frame_start, edit.frame_end = sc.frame_start, sc.frame_end
    edit.render.use_sequencer = True
    edit.render.use_compositing = False
    try:
        edit.render.sequencer_gl_preview = "RENDERED"         # preview the scene strip with EEVEE, as rendered
        edit.render.use_sequencer_override_scene_strip = False
    except Exception:
        pass
    se = edit.sequence_editor_create()
    fish = build_fisheye_group()
    cuts = sorted({sc.frame_start, sc.frame_end + 1} | {x for a, b in FISHEYE for x in (a, b + 1)})
    pieces = []
    for lo, hi in zip(cuts, cuts[1:]):
        st = se.strips.new_scene(name="%sShot_%04d" % (P, lo), scene=sc, channel=1, frame_start=sc.frame_start)
        st.scene_camera = None                                # follow EP2_Inspiration's camera markers
        try:
            st.scene_input = "CAMERA"
        except Exception:
            pass
        st.volume = 0.0
        st.frame_final_start, st.frame_final_end = lo, hi
        if any(a <= lo <= b for a, b in FISHEYE):
            m = st.modifiers.new("Fisheye", "COMPOSITOR")
            m.node_group = fish
        pieces.append((st.name, st.frame_final_start, st.frame_final_end - 1, len(st.modifiers)))
    snd = build_sound(edit)
    build_sound(sc)  # same audio in the 3D scene so Layout playback has sound; EDIT's scene strips are at volume 0, so no doubling
    subs = build_captions(edit)
    if END_CARD:
        card = se.strips.new_image(name=P + "Card", filepath=os.path.join(EP, "overlays", "card.png"), channel=7,
                                   frame_start=shot(27)[2])
        card.frame_final_end = END + 1
    set_output(edit)
    try:
        edit.sync_mode = "AUDIO_SYNC"
    except Exception:
        pass
    return edit, pieces, snd, subs


def watch_layout(edit):
    """A workspace with a big sequencer preview over a sequencer timeline; window shows EP2_Edit."""
    win = bpy.context.window_manager.windows[0]
    ws = bpy.data.workspaces.get(WORKSPACE)
    if ws is None:
        tpl = os.path.join(bpy.utils.system_resource("SCRIPTS"), "startup", "bl_app_templates_system", "Video_Editing",
                           "startup.blend")
        before = set(bpy.data.workspaces)
        with bpy.context.temp_override(window=win, screen=win.screen):
            bpy.ops.workspace.append_activate(idname="Video Editing", filepath=tpl)
        new = [w for w in bpy.data.workspaces if w not in before]
        ws = new[0] if new else bpy.data.workspaces.get("Video Editing")
        ws.name = WORKSPACE
    win.workspace = ws
    win.scene = edit
    try:
        ws.use_pin_scene = True
    except Exception:
        pass
    if hasattr(ws, "sequencer_scene"):  # Blender 5.x: the VSE shows the workspace's sequencer scene, not the window scene
        ws.sequencer_scene = edit
    # NOTE: don't set SpaceSequenceEditor.proxy_render_size from a script here - its RNA update crashes
    # Blender 5.2 when the space isn't the active context (the template's preview already uses the scene size)
    return ws


# ================================================================ build
def build():
    cleanup()
    ns = modules()
    sc = make_scene()
    try:
        bpy.context.window.scene = sc
    except Exception:
        pass
    root = bpy.data.collections.new(P + "Episode2")
    sc.collection.children.link(root)
    S = build_set(sc, root)
    c_cam, c_scr, c_des, c_clawd, c_fx, c_party = (coll(n, root) for n in
                                                   ("Cameras", "Screen", "Designer", "Clawd", "FX", "Party"))
    build_screens(c_scr)
    keyob = build_key(c_fx)
    rig, parts = build_designer(c_des, ns)
    sc.view_layers[0].update()
    animate_designer(sc, rig, parts, ns)
    carm, ceyes, cglow = build_clawd(c_clawd, S["anchor"])
    animate_clawd(sc, carm, ceyes, cglow, S["dock_glow"], S["anchor"])
    build_rings(c_fx, S["anchor"])
    build_party(sc, c_party, S)
    build_ball(c_party)
    build_zzz(sc, c_fx)
    build_confetti(sc, c_fx, rig)
    cams = build_cameras(sc, c_cam)
    for no, name, a, b in SHOTS:
        if a > sc.frame_end:  # end card dropped when END_CARD is False
            continue
        mk = sc.timeline_markers.new("%sS%02d_%s" % (P, no, name), frame=a)
        mk.camera = cams[no]
    sc.camera = cams[1]
    sc.render.use_compositing = False                         # the fisheye lives in EP2_Edit (strip modifier)
    set_output(sc)
    sc.frame_set(1)
    for ob in (rig, carm):
        try:
            ob.hide_set(True, view_layer=sc.view_layers[0])     # eye-hidden only: still drives the parts
        except RuntimeError:
            pass
    edit, pieces, snd, subs = build_edit(sc)
    edit.frame_set(1)
    try:
        watch_layout(edit)
    except Exception as exc:
        print("watch layout not set:", exc)
        try:
            bpy.context.window.scene = edit
        except Exception:
            pass
    return dict(sc=sc, edit=edit, cams=cams, pieces=pieces, subs=subs, rig=rig, clawd=carm, sound=snd, key=keyob)


if __name__ == "episode2":
    R = build()
    print("scene", R["sc"].name, R["sc"].frame_start, R["sc"].frame_end, "edit", R["edit"].name)
    for s in R["sound"]:
        print("sound", s)
