"""Episode 1 "Сделай красиво" (25 s, 9:16, 24 fps) on top of the Studio set.

Run inside Blender (the Studio, Designer and Mascot scenes must exist; Studio is not rebuilt):
    exec(compile(open(".../episodes/ep-001-sdelay-krasivo/scripts/episode1.py").read(), "episode1.py", "exec"), {"__name__": "episode1"})
Exec with any other __name__ to only define the functions (build, cleanup, check).

Timing comes from scripts/episode1_timeline.py; images and sounds from
scripts/make_episode1.py (overlays/ here, shared sounds in scene/audio/). Everything this adds is named EP1_*;
cleanup() removes it and restores what it animated on STU_ objects. Re-running rebuilds.
  cameras   EP1_Cam_<shot>, switched by timeline markers EP1_S<scene>_<shot>
  screen    EP1_Screen_<state> planes on the laptop screen, one visible per frame
  overlays  EP1_Overlay_caption / _bubble / _card, full-frame planes on their cameras
  Clawd     EP1_Clawd_* (posed copy of the Mascot) on STU_Claude_Dock_Anchor, sparkles EP1_Sparkles
  Designer  action on STU_Designer_Rig (re-seated by studio.seat_designer), face layers keyed
  sound     sequencer strips EP1_* (key ticks, Enter, chime, pop, disco)
"""
import importlib.util
import json
import math
import os

import bpy
from mathutils import Matrix, Vector

REPO = "/Users/alexey/.paradev/projects/cartoons"
CHARACTER = os.path.join(REPO, "design-girl")
STUDIO_PY = os.path.join(CHARACTER, "scene", "locations", "studio", "scripts", "studio.py")
EP_DIR = os.path.join(CHARACTER, "episodes", "ep-001-sdelay-krasivo")
TIMELINE_PY = os.path.join(EP_DIR, "scripts", "episode1_timeline.py")
AUDIO_DIR = os.path.join(CHARACTER, "scene", "audio")
P = "EP1_"
SCENE = "Studio"

CLAWD_SCALE = 0.18          # mascot (0.9 m wide) -> 0.16 m on the dock
OVERLAY_D = 0.1             # overlay planes this far in front of their camera
SCREEN_LIFT = 0.0006        # state planes float this far in front of the laptop screen

# hands, desk-relative (x, y world; z above the desktop): (wrist, fingertip), as studio.SEAT_HANDS
KL = ((0.08, 0.32, 0.10), (0.05, 0.19, 0.055))       # left hand on the keyboard
KR = ((-0.08, 0.32, 0.10), (-0.05, 0.19, 0.055))     # right hand on the keyboard
MR = ((-0.24, 0.33, 0.12), (-0.25, 0.20, 0.080))     # right hand on the mouse
ER = ((-0.15, 0.31, 0.10), (-0.12, 0.185, 0.050))    # right hand on Enter (pressed)
BR = ((-0.15, 0.30, 0.10), (-0.12, 0.160, 0.050))    # right hand on Backspace (pressed)
MOUSE_DRAG = (-0.06, 0.03)                           # mouse travel for the drag (to her right, towards her)
EXPRESSIONS = [(1, "sleepy"), (97, "smile"), (241, "shocked"), (313, "neutral"), (361, "hmm"),
               (457, "neutral"), (487, "smile")]     # (first frame, Designer face)
CLAWD_EYES = [(1, "neutral"), (40, "blink"), (43, "neutral"), (130, "blink"), (133, "neutral")]


def up(h, dz):
    (w, t) = h
    return ((w[0], w[1], w[2] + 0.6 * dz), (t[0], t[1], t[2] + dz))


def shift(h, dx, dy):
    (w, t) = h
    return ((w[0] + dx, w[1] + dy, w[2]), (t[0] + dx, t[1] + dy, t[2]))


# ---------------------------------------------------------------- modules
def modules():
    ns = {"__name__": "studio_helpers"}
    exec(compile(open(STUDIO_PY).read(), STUDIO_PY, "exec"), ns)
    spec = importlib.util.spec_from_file_location("episode1_timeline", TIMELINE_PY)
    tl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tl)
    return ns, tl


# ---------------------------------------------------------------- animation helpers
def fcurves_of(idb):
    ad = idb.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    try:
        return list(act.fcurves)
    except AttributeError:                       # Blender 5: layered actions
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(act, ad.action_slot)
        return list(cb.fcurves) if cb else []


def key(idb, path, frame, value=None, index=-1):
    if value is not None:
        if index >= 0:
            getattr(idb, path)[index] = value
        else:
            setattr(idb, path, value)
    idb.keyframe_insert(data_path=path, frame=frame, index=index)


def tag_action(idb, name):
    ad = idb.animation_data
    if ad and ad.action and not ad.action.name.startswith(P):
        ad.action.name = P + name


def set_interp(idb, kinds):
    """kinds: {data_path substring: interpolation} for this ID's F-curves."""
    for fc in fcurves_of(idb):
        for sub, it in kinds.items():
            if sub in fc.data_path:
                for kp in fc.keyframe_points:
                    kp.interpolation = it


def _get(idb, path, index):
    if "." in path:
        tgt, attr = path.rsplit(".", 1)
        v = getattr(idb.path_resolve(tgt), attr)
    else:
        v = getattr(idb, path)
    return v[index] if index >= 0 else v


def _set(idb, path, index, v):
    if index >= 0:
        getattr(idb, path)[index] = v
    elif "." in path:
        tgt, attr = path.rsplit(".", 1)
        setattr(idb.path_resolve(tgt), attr, v)
    else:
        setattr(idb, path, v)


def remember_value(idb, path, index=-1):
    """Store an STU_ value we are about to animate, so cleanup() can put it back."""
    import zlib
    k = "ep1_o_%08x" % zlib.crc32(("%s|%d" % (path, index)).encode())
    if k not in idb.keys():
        idb[k] = _get(idb, path, index)
        idb[k + "_p"] = path
        idb[k + "_i"] = index


def show_only(objs, visible, frame):
    for o in objs:
        h = o not in visible
        key(o, "hide_render", frame, h)
        key(o, "hide_viewport", frame, h)


# ---------------------------------------------------------------- cleanup
def cleanup():
    sc = bpy.data.scenes.get(SCENE)
    for o in list(bpy.data.objects):
        if o.name.startswith(P):
            bpy.data.objects.remove(o, do_unlink=True)
    for c in list(bpy.data.collections):
        if c.name.startswith(P):
            bpy.data.collections.remove(c)
    # put back STU_ values we animated, then drop our actions
    owners = list(bpy.data.objects) + list(bpy.data.lights) + list(bpy.data.materials) + \
        [m.node_tree for m in bpy.data.materials if m.node_tree]
    for idb in owners:
        ad = idb.animation_data
        if ad and ad.action and ad.action.name.startswith(P):
            idb.animation_data_clear()
        for k in [k for k in idb.keys() if k.startswith("ep1_o_") and not k.endswith(("_p", "_i"))]:
            try:
                _set(idb, idb[k + "_p"], idb[k + "_i"], idb[k])
            except Exception as exc:
                print("restore failed", idb.name, idb[k + "_p"], exc)
            for kk in (k, k + "_p", k + "_i"):
                del idb[kk]
    for coll in (bpy.data.actions, bpy.data.materials, bpy.data.meshes, bpy.data.images, bpy.data.lights,
                 bpy.data.cameras, bpy.data.armatures):
        for d in list(coll):
            if d.name.startswith(P) and d.users == 0:
                coll.remove(d)
    if sc:
        for m in list(sc.timeline_markers):
            if m.name.startswith(P):
                sc.timeline_markers.remove(m)
        se = sc.sequence_editor
        if se:
            strips = (se.strips if hasattr(se, "strips") else se.sequences)
            for s in list(strips):
                if s.name.startswith(P):
                    strips.remove(s)


# ---------------------------------------------------------------- builders
def coll(sc, name, parent=None):
    c = bpy.data.collections.get(P + name) or bpy.data.collections.new(P + name)
    par = parent or sc.collection
    if c.name not in par.children:
        par.children.link(c)
    return c


def emission_image_material(name, img, strength=1.0, alpha=False):
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
    em.inputs["Strength"].default_value = strength
    nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    if alpha:
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(tex.outputs["Alpha"], mix.inputs["Fac"])
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs["Surface"])
        for attr, val in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
            try:
                setattr(m, attr, val)
            except Exception:
                pass
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


def no_light_effects(ob):
    for attr in ("visible_shadow", "visible_diffuse", "visible_glossy", "visible_transmission",
                 "visible_volume_scatter"):
        if hasattr(ob, attr):
            setattr(ob, attr, False)


def look_at(loc, tgt):
    d = Vector(tgt) - Vector(loc)
    M = d.to_track_quat("-Z", "Y").to_matrix().to_4x4()
    M.translation = Vector(loc)
    return M


def screen_point(scr, u, v):
    """World point on the laptop screen plane at texture (u, v) (0..1, v up)."""
    w, h = 0.272, 0.272 / 1.6
    return scr.matrix_world @ Vector(((u - 0.5) * w, 0, (v - 0.5) * h))


def screen_normal(scr):
    return (scr.matrix_world.to_3x3() @ Vector((0, -1, 0))).normalized()


def cameras(sc, ns, tl, col):
    scr = bpy.data.objects["STU_Screen_Laptop"]
    n = screen_normal(scr)
    site_c = screen_point(scr, 520 / 1600, 1 - 528 / 1000)          # centre of the site preview
    scr_c = screen_point(scr, 0.5, 0.5)
    eyes = next(o for o in bpy.data.objects if o.name.startswith("STU_Designer_Face_Eyes_neutral"))
    face = eyes.matrix_world @ (sum((Vector(c) for c in eyes.bound_box), Vector()) / 8)
    head = bpy.data.objects["STU_Designer_Rig"].matrix_world @ bpy.data.objects["STU_Designer_Rig"].data.bones["head"].head_local
    face_cam = face + Vector((0.66, -0.42, 0.06))
    clawd = bpy.data.objects["STU_Claude_Dock_Anchor"].matrix_world.translation + Vector((0, 0, 0.07))
    cams = {
        "S1_Medium": ((0.28, -1.20, 1.32), (0.0, 0.45, 1.12), 35),
        "S2_Keys": ((0.55, 0.45, 1.00), (-0.012, -0.008, 0.826), 24),   # past her left shoulder: keys below, chat above
        "S3_Claude": (tuple(clawd + Vector((-0.22, -0.52, 0.15))), tuple(clawd), 50),
        "S4_Screen": (tuple(scr_c + n * 0.38), tuple(scr_c), 20),   # whole screen: site and chat
        "S5_Face": (tuple(face_cam), tuple(face + Vector((0, 0, -0.02))), 50),
        "S6_Shoulder": ((-0.80, 1.05, 1.45), tuple(scr_c), 50),
        "S7_Front": ((-0.30, -1.25, 1.22), (-0.14, 0.15, 1.00), 32),
        "Card": ((0.0, -2.95, 1.40), (0.0, 0.0, 1.40), 50),
    }
    out = {}
    for name, (loc, tgt, lens) in cams.items():
        cd = bpy.data.cameras.new(P + "Cam_" + name)
        cd.lens = lens
        cd.sensor_fit = "AUTO"
        cd.sensor_width = 36.0
        cd.clip_start = 0.01
        cd.clip_end = 30.0
        ob = bpy.data.objects.new(P + "Cam_" + name, cd)
        col.objects.link(ob)
        ob.matrix_world = look_at(loc, tgt)
        ob["target"] = list(tgt)
        out[name] = ob
    yaw = math.degrees(math.atan2(face_cam.x - head.x, -(face_cam.y - head.y)))
    return out, yaw


def overlay(cam, img_name, col, sc):
    path = os.path.join(EP_DIR, "overlays", img_name)
    img = bpy.data.images.load(path, check_existing=True)
    img.name = P + os.path.splitext(img_name)[0]
    m = emission_image_material("Overlay_" + img_name.split("_")[1].split(".")[0], img, 1.0, alpha=True)
    hgt = OVERLAY_D * cam.data.sensor_width / cam.data.lens            # AUTO fit: sensor spans the long side
    wid = hgt * sc.render.resolution_x / sc.render.resolution_y
    d = -OVERLAY_D
    ob = quad("Overlay_" + img_name.split("_")[1].split(".")[0],
              [(-wid / 2, -hgt / 2, d), (wid / 2, -hgt / 2, d), (wid / 2, hgt / 2, d), (-wid / 2, hgt / 2, d)], m, col)
    ob.parent = cam
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_basis = Matrix.Identity(4)
    no_light_effects(ob)
    return ob


def screen_planes(sc, tl, col):
    scr = bpy.data.objects["STU_Screen_Laptop"]
    runs = json.load(open(os.path.join(EP_DIR, "overlays", "screen_timeline.json")))
    w, h = 0.272, 0.272 / 1.6
    planes = {}
    for _, _, fname in runs:
        if fname in planes:
            continue
        img = bpy.data.images.load(os.path.join(EP_DIR, "overlays", "screens", fname), check_existing=True)
        img.name = P + os.path.splitext(fname)[0]
        m = emission_image_material(os.path.splitext(fname)[0], img, 1.0)
        ob = quad(os.path.splitext(fname)[0].replace("screen_", "Screen_"),
                  [(-w / 2, 0, -h / 2), (w / 2, 0, -h / 2), (w / 2, 0, h / 2), (-w / 2, 0, h / 2)], m, col)
        ob.parent = scr
        ob.matrix_parent_inverse = Matrix.Identity(4)
        ob.matrix_basis = Matrix.Translation((0, -SCREEN_LIFT, 0))     # towards the viewer (plane faces -Y)
        no_light_effects(ob)
        ob["texture"] = fname
        planes[fname] = ob
    allp = list(planes.values())
    show_only(allp, [], 1)
    for a, b, fname in runs:
        show_only(allp, [planes[fname]], a)
    return planes, runs


def clawd(sc, tl, col):
    src = bpy.data.collections.get("MSC_Character")
    if src is None:
        raise RuntimeError("Mascot scene (MSC_Character) not found")
    arm_src = next(o for o in src.objects if o.type == "ARMATURE")
    copies = {}
    for o in src.objects:
        c = o.copy()
        c.name = P + "Clawd_" + o.name
        copies[o] = c
        col.objects.link(c)
    for o, c in copies.items():
        if o.parent in copies:
            c.parent = copies[o.parent]
            c.parent_type, c.parent_bone = o.parent_type, o.parent_bone
            c.matrix_parent_inverse = o.matrix_parent_inverse.copy()
    arm = copies[arm_src]
    anchor = bpy.data.objects["STU_Claude_Dock_Anchor"]
    arm.parent = anchor
    arm.matrix_parent_inverse = Matrix.Identity(4)
    arm.matrix_basis = Matrix.Diagonal((CLAWD_SCALE, CLAWD_SCALE, CLAWD_SCALE, 1))
    arm.hide_render = True
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    # own glowing material copies
    glow = {}
    for c in copies.values():
        for slot in getattr(c, "material_slots", []):
            m = slot.material
            if m is None:
                continue
            if m.name not in glow:
                g = m.copy()
                g.name = P + "Clawd_" + m.name
                b = next((n for n in g.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
                if b is not None:
                    b.inputs["Emission Color"].default_value = b.inputs["Base Color"].default_value
                    b.inputs["Emission Strength"].default_value = 0.0
                glow[m.name] = g
            slot.link = "OBJECT"
            slot.material = glow[m.name]
    return arm, copies, glow


def rot_basis(arm, bname, R3):
    """matrix_basis turning a bone by world rotation R3 about its head (parent at rest)."""
    b = arm.data.bones[bname]
    rest = b.matrix_local
    M = (R3 @ rest.to_3x3()).to_4x4()
    M.translation = rest.translation
    return rest.inverted() @ M


def key_bone(arm, bname, basis, frame, prev):
    pb = arm.pose.bones[bname]
    pb.rotation_mode = "QUATERNION"
    q = basis.to_quaternion()
    if bname in prev and prev[bname].dot(q) < 0:
        q.negate()
    prev[bname] = q
    pb.rotation_quaternion = q
    pb.keyframe_insert("rotation_quaternion", frame=frame)


# ---------------------------------------------------------------- the episode
def build():
    ns, tl = modules()
    sc = bpy.data.scenes[SCENE]
    cleanup()
    rig = ns["seat_designer"]()                        # fresh, deterministic seated pose
    sc.view_layers[0].update()
    sc.render.fps, sc.render.fps_base = tl.FPS, 1.0
    sc.frame_start, sc.frame_end = 1, tl.FRAME_END
    root = coll(sc, "Episode1")
    c_cam, c_scr, c_ovl, c_clawd, c_fx = (coll(sc, n, root) for n in ("Cameras", "Screen", "Overlays", "Clawd", "FX"))

    # ---- cameras + cuts
    cams, face_yaw = cameras(sc, ns, tl, c_cam)
    for scene_no, cam, a, b in tl.SHOTS:
        mk = sc.timeline_markers.new("%sS%d_%s" % (P, scene_no, cam), frame=a)
        mk.camera = cams[cam]
    sc.camera = cams[tl.SHOTS[0][1]]

    # ---- laptop screen states
    planes, runs = screen_planes(sc, tl, c_scr)

    # ---- overlays, visible only in their shot
    shot = {(s, c): (a, b) for s, c, a, b in tl.SHOTS}
    ovl = {
        "caption": (overlay(cams["S1_Medium"], "overlay_caption.png", c_ovl, sc), (12, shot[(1, "S1_Medium")][1])),
        "bubble": (overlay(cams["S3_Claude"], "overlay_bubble.png", c_ovl, sc), (tl.CLAUDE_REPLY, shot[(3, "S3_Claude")][1])),
        "card": (overlay(cams["Card"], "overlay_card.png", c_ovl, sc), shot[(8, "Card")]),
    }
    for name, (ob, (a, b)) in ovl.items():
        show_only([ob], [], 1)
        show_only([ob], [ob], a)
        if b < tl.FRAME_END:
            show_only([ob], [], b + 1)

    # ---- Clawd on the dock: lights up, nods, sparkles, thumbs up
    carm, ccopies, cglow = clawd(sc, tl, c_clawd)
    G = tl.CLAUDE_GLOW
    for g in cglow.values():
        if "eye" in g.name:
            continue
        b = next((n for n in g.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        es = b.inputs["Emission Strength"]
        for f, v in ((1, 0.0), (G, 0.0), (G + 6, 0.9), (tl.RAINBOW[0], 0.35)):
            es.default_value = v
            es.keyframe_insert("default_value", frame=f)
        tag_action(g.node_tree, "Clawd_glow_" + g.name)
    dock = bpy.data.materials["STU_dock_glow"]
    db = next(n for n in dock.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    remember_value(dock.node_tree, 'nodes["%s"].inputs["Emission Strength"].default_value' % db.name)
    base_es = db.inputs["Emission Strength"].default_value
    for f, v in ((1, base_es), (G, base_es), (G + 5, 4.0), (tl.RAINBOW[0], 2.0)):
        db.inputs["Emission Strength"].default_value = v
        db.inputs["Emission Strength"].keyframe_insert("default_value", frame=f)
    tag_action(dock.node_tree, "dock_glow")
    lamp = bpy.data.objects.get("STU_Glow_Dock")
    if lamp:
        remember_value(lamp.data, "energy")
        e0 = lamp.data.energy
        for f, v in ((1, e0), (G, e0), (G + 5, 3.0), (tl.RAINBOW[0], 1.5)):
            key(lamp.data, "energy", f, v)
        tag_action(lamp.data, "Glow_Dock")
    eyes = {o["expression"]: o for o in ccopies.values() if "expression" in o.keys()}
    eye_keys = CLAWD_EYES + [(G, "happy"), (tl.RAINBOW[0], "neutral"), (tl.RAINBOW[0] + 50, "blink"),
                             (tl.RAINBOW[0] + 53, "neutral"), (tl.SMILE, "happy")]
    for f, e in sorted(eye_keys):
        show_only(list(eyes.values()), [eyes[e]], f)
    prev = {}
    nod = [(G + 2, 0), (G + 8, 14), (G + 14, -4), (G + 20, 14), (G + 26, -4), (G + 32, 0)]
    for f, a in nod:
        key_bone(carm, "body", rot_basis(carm, "body", Matrix.Rotation(math.radians(a), 3, "X")), f, prev)
    rest_dir = carm.data.bones["arm.L"].matrix_local.to_3x3().col[1].normalized()
    R_up = rest_dir.rotation_difference(Vector((0.25, -0.15, 1.0)).normalized()).to_matrix()
    for f, R in ((tl.THUMB[0], Matrix.Identity(3)), (tl.THUMB[0] + 6, R_up), (tl.THUMB[1] - 6, R_up),
                 (tl.THUMB[1], Matrix.Identity(3))):
        key_bone(carm, "arm.L", rot_basis(carm, "arm.L", R), f, prev)
    tag_action(carm, "Clawd_pose")
    # sparkles circling Clawd while it answers
    spk = bpy.data.objects.new(P + "Sparkles", None)
    c_fx.objects.link(spk)
    spk.parent = bpy.data.objects["STU_Claude_Dock_Anchor"]
    spk.matrix_parent_inverse = Matrix.Identity(4)
    spk.location = (0, 0, 0.07)
    cols = [(1, 1, 1, 1), (1.0, 0.70, 0.54, 1), (0.79, 0.65, 0.94, 1)]
    smats = []
    for i, c in enumerate(cols):
        m = bpy.data.materials.new(P + "Sparkle_%d" % i)
        m.use_nodes = True
        b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        b.inputs["Base Color"].default_value = c
        b.inputs["Emission Color"].default_value = c
        b.inputs["Emission Strength"].default_value = 6.0
        smats.append(m)
    s = 0.006
    cube = [(-s, -s, -s), (s, -s, -s), (s, s, -s), (-s, s, -s), (-s, -s, s), (s, -s, s), (s, s, s), (-s, s, s)]
    faces = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    for i in range(8):
        me = bpy.data.meshes.new(P + "Sparkle_%d" % i)
        me.from_pydata(cube, [], faces)
        me.materials.append(smats[i % 3])
        ob = bpy.data.objects.new(P + "Sparkle_%d" % i, me)
        c_fx.objects.link(ob)
        ob.parent = spk
        a = 2 * math.pi * i / 8
        ob.location = (0.12 * math.cos(a), 0.12 * math.sin(a), 0.035 * math.sin(3 * a))
        ob.rotation_euler = (a, a * 0.5, 0)
        no_light_effects(ob)
    for f, v in ((G - 1, 0.0), (G + 6, 1.0), (shot[(3, "S3_Claude")][1] - 6, 1.0), (shot[(3, "S3_Claude")][1], 0.0)):
        key(spk, "scale", f, (v, v, v))
    key(spk, "rotation_euler", G - 1, (0, 0, 0))
    key(spk, "rotation_euler", shot[(3, "S3_Claude")][1], (0, 0, 4 * math.pi))
    set_interp(spk, {"rotation_euler": "LINEAR"})
    tag_action(spk, "Sparkles")

    # ---- the Designer
    arm = rig
    prev = {}
    KEYED = ["torso", "head", "upper_arm.L", "forearm.L", "hand.L", "upper_arm.R", "forearm.R", "hand.R"]
    poses = []                                            # (frame, hands, torso, head)

    def pose(f, L, R, torso=(0, 0), head=(10, 0)):
        poses.append((f, {".L": L, ".R": R}, torso, head))

    # 1: sighs at the grey site
    pose(1, KL, MR, (0, 0), (10, 0))
    pose(28, KL, MR, (0, 0), (10, 0))
    pose(42, KL, MR, (-4, 0), (4, 0))                     # breathe in
    pose(62, KL, MR, (5, 0), (17, 0))                     # ...and slump
    pose(96, KL, MR, (5, 0), (17, 0))
    # 2: types two words, decisive Enter
    pose(97, KL, KR, (2, 0), (12, 0))
    for i, f in enumerate(tl.KEYS_1):
        left = i % 2 == 0
        pose(f, up(KL, 0 if left else 0.025), up(KR, 0.025 if left else 0), (2, 0), (12, 0))
    pose(tl.ENTER_1 - 5, KL, up(ER, 0.05), (1, 0), (10, 0))
    pose(tl.ENTER_1 - 2, KL, up(ER, 0.07), (0, 0), (9, 0))
    pose(tl.ENTER_1, KL, ER, (3, 0), (12, 0))
    pose(tl.ENTER_1 + 5, KL, up(ER, 0.02), (1, 0), (10, 0))
    # 3-5: waits; then slowly turns to the camera, deadpan
    s5a, s5b = shot[(5, "S5_Face")]
    pose(s5a, KL, up(ER, 0.02), (1, 0), (10, 0))
    pose(s5a + 5, KL, up(ER, 0.02), (1, 0), (10, 0))
    pose(s5a + 30, KL, up(ER, 0.02), (0, 14), (3, face_yaw))
    pose(s5b, KL, up(ER, 0.02), (0, 14), (3, face_yaw))
    # 6: erases, retypes, drags the reference, sends
    pose(tl.EDIT_START, KL, KR, (2, 0), (12, 0))
    for f in tl.ERASE:
        pose(f, KL, BR, (2, 0), (12, 0))
        pose(f + 2, KL, up(BR, 0.025), (2, 0), (12, 0))
    for i, f in enumerate(tl.TYPE_2):
        left = i % 2 == 0
        pose(f, up(KL, 0 if left else 0.025), up(KR, 0.025 if left else 0), (2, 0), (12, 0))
    pose(tl.TYPE_2[-1] + 2, KL, KR, (2, 0), (12, 0))
    for i, f in enumerate(tl.DRAG):
        p = (i + 1) / len(tl.DRAG)
        e = p * p * (3 - 2 * p)
        pose(f, KL, shift(MR, MOUSE_DRAG[0] * e, MOUSE_DRAG[1] * e), (2, 0), (10, 0))
    pose(tl.DROP, KL, shift(MR, *MOUSE_DRAG), (2, 0), (10, 0))
    pose(tl.ENTER_2 - 2, KL, up(ER, 0.05), (1, 0), (10, 0))
    pose(tl.ENTER_2, KL, ER, (3, 0), (12, 0))
    pose(tl.ENTER_2 + 4, KL, up(ER, 0.02), (1, 0), (10, 0))
    # 7: the clean site; she leans back, smiles at Clawd
    pose(shot[(7, "S7_Front")][0], KL, up(ER, 0.02), (-3, 0), (2, -14))
    pose(shot[(7, "S7_Front")][0] + 14, KL, up(ER, 0.02), (-3, 0), (0, -20))
    pose(shot[(7, "S7_Front")][1], KL, up(ER, 0.02), (-3, 0), (0, -20))
    max_t = 0.0
    for f, hands, torso, head in poses:
        bases = ns["designer_pose_bases"](arm, hands, torso, head)
        for bn in KEYED:
            max_t = max(max_t, bases[bn].translation.length)
            key_bone(arm, bn, bases[bn], f, prev)
    tag_action(arm, "Designer")
    # S5: the camera pans with her face as she turns (turn: s5a + 5 .. s5a + 30), centred at the end
    eyes_n = next(o for o in bpy.data.objects if o.name.startswith("STU_Designer_Face_Eyes_neutral"))
    c5 = cams["S5_Face"]
    loc5 = c5.matrix_world.translation.copy()
    for f_pose, f_keys in ((s5a, (s5a, s5a + 5)), (s5a + 30, (s5a + 30, s5b))):
        sc.frame_set(f_pose)
        fpt = eyes_n.matrix_world @ (sum((Vector(c) for c in eyes_n.bound_box), Vector()) / 8)
        for fk in f_keys:
            c5.matrix_world = look_at(loc5, fpt + Vector((0, 0, -0.02)))
            c5.keyframe_insert("rotation_euler", frame=fk)
            c5.keyframe_insert("location", frame=fk)
    tag_action(c5, "Cam_S5_pan")
    # the mouse travels with her hand during the drag
    mouse = bpy.data.objects["STU_Mouse"]
    remember_value(mouse, "location", 0)
    remember_value(mouse, "location", 1)
    m0 = mouse.location.copy()
    key(mouse, "location", tl.DRAG[0] - 3, m0)
    for i, f in enumerate(tl.DRAG):
        p = (i + 1) / len(tl.DRAG)
        e = p * p * (3 - 2 * p)
        key(mouse, "location", f, m0 + Vector((MOUSE_DRAG[0] * e, MOUSE_DRAG[1] * e, 0)))
    key(mouse, "location", shot[(7, "S4_Screen")][0] - 1, m0 + Vector((MOUSE_DRAG[0], MOUSE_DRAG[1], 0)))
    key(mouse, "location", shot[(7, "S4_Screen")][0], m0)
    tag_action(mouse, "Mouse")
    # faces
    faces = [o for o in bpy.data.objects if o.name.startswith("STU_Designer_Face_") and "expression" in o.keys()]
    for f, expr in EXPRESSIONS:
        show_only(faces, [o for o in faces if o["expression"] == expr], f)
    for o in faces:
        tag_action(o, o.name)

    # ---- rainbow light from the screen on her face (scenes 4-6)
    ld = bpy.data.lights.new(P + "Rainbow", "AREA")
    ld.size = 0.30
    lo = bpy.data.objects.new(P + "Light_Rainbow", ld)
    c_fx.objects.link(lo)
    scr = bpy.data.objects["STU_Screen_Laptop"]
    n = screen_normal(scr)
    lo.matrix_world = Matrix.Translation(screen_point(scr, 0.5, 0.5) + n * 0.05) @ n.to_track_quat("-Z", "Y").to_matrix().to_4x4()
    hues = [(1.0, 0.2, 0.85), (0.2, 0.9, 1.0), (1.0, 0.95, 0.2), (0.3, 1.0, 0.45)]
    for f, v in ((1, 0.0), (tl.RAINBOW[0] - 1, 0.0), (tl.RAINBOW[0], 45.0), (shot[(5, "S5_Face")][1], 45.0),
                 (shot[(6, "S6_Shoulder")][0], 18.0), (tl.WIPE[0], 18.0), (tl.CLEAN, 0.0)):
        key(ld, "energy", f, v)
    for k, f in enumerate(range(tl.RAINBOW[0], tl.RAINBOW[1], tl.RAINBOW_STEP)):
        key(ld, "color", f, hues[k % 4])
    key(ld, "color", tl.RAINBOW[1], hues[0])
    set_interp(ld, {"color": "CONSTANT"})
    tag_action(ld, "Rainbow")

    # constant steps for every visibility key
    for o in list(planes.values()) + [v[0] for v in ovl.values()] + faces + list(eyes.values()):
        set_interp(o, {"hide_": "CONSTANT"})

    # ---- sound
    se = sc.sequence_editor or sc.sequence_editor_create()
    strips = (se.strips if hasattr(se, "strips") else se.sequences)
    chan = {"enter.wav": 3, "chime.wav": 4, "disco.wav": 5, "pop.wav": 6}
    for i, (fname, f) in enumerate(tl.sound_cues()):
        ch = chan.get(fname, 1 + i % 2)
        st = strips.new_sound(name="%s%02d_%s" % (P, i, fname[:-4]), filepath=os.path.join(AUDIO_DIR, "music" if fname == "disco.wav" else "sfx", fname),
                              channel=ch, frame_start=f)
        if fname == "tick.wav":
            st.volume = 0.6
    for attr, val in (("sync_mode", "AUDIO_SYNC"),):
        try:
            setattr(sc, attr, val)
        except Exception:
            pass

    # ---- output (not rendered here)
    out = []
    ims = sc.render.image_settings
    try:
        if hasattr(ims, "media_type"):
            ims.media_type = "VIDEO"
        ims.file_format = "FFMPEG"
        sc.render.ffmpeg.format = "MPEG4"
        sc.render.ffmpeg.codec = "H264"
        sc.render.ffmpeg.audio_codec = "AAC"
        out.append("mp4/h264/aac")
    except Exception as exc:
        out.append("video output not set: %s" % exc)
    sc.render.filepath = os.path.join(EP_DIR, "renders", "ep-001_")
    sc.frame_set(1)
    return dict(cams=cams, planes=planes, runs=runs, ovl=ovl, clawd=carm, rig=arm, max_basis_t=max_t,
                face_yaw=face_yaw, output=out, n_poses=len(poses))


# ---------------------------------------------------------------- numeric checks (no rendering)
def check(res):
    ns, tl = modules()
    sc = bpy.data.scenes[SCENE]
    vl = sc.view_layers[0]
    rep, ok = [], True

    def req(cond, msg):
        nonlocal ok
        rep.append(("OK   " if cond else "FAIL ") + msg)
        ok &= bool(cond)

    req(sc.render.fps == 24 and sc.frame_start == 1 and sc.frame_end == tl.FRAME_END,
        f"24 fps, frames 1..{sc.frame_end}, {sc.render.resolution_x}x{sc.render.resolution_y}")
    mks = sorted((m.frame, m.camera.name) for m in sc.timeline_markers if m.name.startswith(P))
    req([f for f, _ in mks] == [a for _, _, a, _ in tl.SHOTS], f"{len(mks)} camera cuts at the shot starts")
    req(res["max_basis_t"] < 1e-4, f"posed bones only rotate (max basis translation {res['max_basis_t']:.1e})")

    subjects = {   # shot camera -> [(label, world point getter, accepted first-hit name prefixes)]
        "S1_Medium": [("face", "face", ("STU_Designer_",))],
        "S2_Keys": [("keyboard", "keys", ("STU_Keyboard", "STU_Designer_")),
                    ("screen", "site", ("EP1_Screen_",))],
        "S3_Claude": [("Clawd", "clawd", ("EP1_Clawd_",))],
        "S4_Screen": [("site", "site", ("EP1_Screen_",)), ("chat", "chat", ("EP1_Screen_",))],
        "S5_Face": [("face", "face", ("STU_Designer_",))],
        "S6_Shoulder": [("screen", "screen", ("EP1_Screen_",))],
        "S7_Front": [("face", "face", ("STU_Designer_",)), ("Clawd", "clawd", ("EP1_Clawd_",))],
        "Card": [],
    }
    scr = bpy.data.objects["STU_Screen_Laptop"]
    for scene_no, cam_key, a, b in tl.SHOTS:
        for f in (a, (a + b) // 2, b):
            sc.frame_set(f)
            dg = vl.depsgraph
            cam = res["cams"][cam_key]
            vis = [o for o in res["planes"].values() if not o.hide_render]
            want = next(r[2] for r in res["runs"] if r[0] <= f <= r[1])
            req(len(vis) == 1 and vis[0]["texture"] == want, f"f{f}: one screen state, {want}")
            if f != (a + b) // 2:
                continue
            ovis = sorted(n for n, (o, _) in res["ovl"].items() if not o.hide_render)
            exp = sorted(n for n, (o, (oa, ob_)) in res["ovl"].items() if oa <= f <= ob_)
            req(ovis == exp, f"f{f} {cam_key}: overlays shown {ovis}")
            eyes = [o for o in sc.objects if o.name.startswith("STU_Designer_Face_Eyes_") and not o.hide_render]
            pts = {}
            if eyes:
                e = eyes[0].evaluated_get(dg)
                pts["face"] = e.matrix_world @ (sum((Vector(c) for c in e.bound_box), Vector()) / 8)
            kb = bpy.data.objects["STU_Keyboard"]
            pts["keys"] = kb.matrix_world.translation + Vector((0.06, 0.0, 0.01))
            pts["site"] = screen_point(scr, 520 / 1600, 1 - 528 / 1000)
            pts["screen"] = screen_point(scr, 0.5, 0.5)
            pts["chat"] = screen_point(scr, 1320 / 1600, 1 - 600 / 1000)
            pts["clawd"] = bpy.data.objects["STU_Claude_Dock_Anchor"].matrix_world.translation + Vector((0, 0, 0.06))
            origin = cam.matrix_world.translation
            from bpy_extras.object_utils import world_to_camera_view
            for label, pk, prefixes in subjects[cam_key]:
                p = pts[pk]
                d = (p - origin).normalized()
                start = origin + d * (OVERLAY_D + 0.03)
                hit, loc, nrm, idx, ob, _ = sc.ray_cast(dg, start, d, distance=(p - start).length + 0.05)
                name = ob.name if hit else "nothing"
                u, v, _ = world_to_camera_view(sc, cam, p)
                inside = 0.05 <= u <= 0.95 and 0.05 <= v <= 0.95
                req(hit and name.startswith(prefixes) and inside,
                    f"f{f} {cam_key}: {label} visible (first hit {name}; in frame at x {u:.2f}, y {v:.2f})")
            near, near_ob = 9.0, "-"
            for o in sc.objects:
                if o.type != "MESH" or o.hide_render or o.name.startswith(P + "Overlay") or o.name.startswith(P + "Sparkle"):
                    continue
                oe = o.evaluated_get(dg)
                mw = oe.matrix_world
                bb = [mw @ Vector(c) for c in oe.bound_box]
                ctr = sum(bb, Vector()) / 8
                if (ctr - origin).length - max((c - ctr).length for c in bb) > near:
                    continue
                for v in oe.data.vertices:
                    w = mw @ v.co
                    dd = (w - origin).length
                    if dd < near:
                        uu, vv, zz = world_to_camera_view(sc, cam, w)
                        if zz > 0 and -0.1 <= uu <= 1.1 and -0.1 <= vv <= 1.1:     # in front, in (or at) frame
                            near, near_ob = dd, o.name
            req(near > 0.12, f"f{f} {cam_key}: nothing too close in view (nearest {near_ob} {near:.2f} m)")
    # Clawd on the dock
    sc.frame_set(1)
    dg = vl.depsgraph
    body = next(o for o in sc.objects if o.name.startswith("EP1_Clawd_") and o.name.endswith("Body"))
    be = body.evaluated_get(dg)
    zs = [(be.matrix_world @ v.co) for v in be.data.vertices]
    top = bpy.data.objects["STU_Claude_Dock_Anchor"].matrix_world.translation.z
    req(abs(min(v.z for v in zs) - (top + 3 * 0.05 * CLAWD_SCALE)) < 0.003,
        f"Clawd body {max(v.x for v in zs) - min(v.x for v in zs):.3f} m wide, legs on the dock (body bottom {min(v.z for v in zs):.3f}, dock top {top:.3f})")
    se = sc.sequence_editor
    strips = [s for s in (se.strips if hasattr(se, "strips") else se.sequences) if s.name.startswith(P)]
    disco = [s for s in strips if "disco" in s.name]
    req(len(strips) == len(tl.sound_cues()) and disco and disco[0].frame_final_end == tl.RAINBOW[1],
        f"{len(strips)} sound strips; disco frames {disco[0].frame_final_start}..{disco[0].frame_final_end - 1}" if disco else "no disco")
    rep.append("output: %s -> %s" % (res["output"], sc.render.filepath))
    rep.append("ALL OK" if ok else "SOME CHECKS FAILED")
    sc.frame_set(1)
    return "\n".join(rep)


if __name__ == "episode1":
    r = build()
    print(check(r))
