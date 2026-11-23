"""Builds the Claude mascot ("Clawd") as a voxel companion in Blender (rest pose, rigid bone rig).

Run inside Blender:
    exec(compile(open(".../scene/characters/clawd/scripts/mascot.py").read(), "mascot.py", "exec"), {"__name__": "mascot"})
Everything is rebuilt from scratch in a scene called "Mascot". Only the "Mascot" scene and
datablocks prefixed "MSC_" are touched; other scenes (Port, Designer) are left alone.
Exec with any other __name__ to only define the functions (e.g. render_views) without rebuilding.

Style matches scene/characters/design-girl/scripts/designer.py: 1 voxel = 0.05 m, Z up, the character faces -Y
(so its LEFT is +X), feet on z = 0. Voxel index i covers x in [i, i+1). Coordinates are voxel units.

Shape follows the Claude Code terminal sprite:
     ▐▛███▜▌
    ▝▜█████▛▘
      ▘▘ ▝▝
i.e. a 12x4 "pixel" body (terminal pixels are ~1:2 tall), two 1-pixel eyes in the second row,
2-pixel arm stubs on the third row, four 1-pixel legs. Here 1 sprite pixel = 1.5 x 3 voxels.
"""
import os
import bpy
from mathutils import Matrix, Vector

S = 0.05  # metres per voxel
PREFIX = "MSC_"
SCENE = "Mascot"

PALETTE = {
    "orange": "#D97757",         # Claude terracotta
    "orange_shadow": "#C2633F",  # underside / bottom row
    "orange_hi": "#E8906F",      # top front rim highlight
    "eye": "#1E1A18",
}
ALPHA = {}


# ---------------------------------------------------------------- materials
def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_rgba(h, a=1.0):
    h = h.lstrip("#")
    return tuple(_lin(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4)) + (a,)


def make_material(key):
    m = bpy.data.materials.new(PREFIX + key)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None) or nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(bsdf.outputs[0], out.inputs[0])
    col = hex_rgba(PALETTE[key], 1.0)
    bsdf.inputs["Base Color"].default_value = col
    bsdf.inputs["Roughness"].default_value = 1.0
    for name in ("Specular IOR Level", "Specular"):
        if name in bsdf.inputs:
            bsdf.inputs[name].default_value = 0.0
    m.diffuse_color = col[:3] + (1.0,)
    return m


# ---------------------------------------------------------------- voxel helpers
def fill(v, i0, i1, j0, j1, k0, k1, mat):
    """Inclusive index ranges."""
    for i in range(i0, i1 + 1):
        for j in range(j0, j1 + 1):
            for k in range(k0, k1 + 1):
                v[(i, j, k)] = mat


def paint(v, i0, i1, j0, j1, k0, k1, mat):
    """Recolor only voxels that exist."""
    for i in range(i0, i1 + 1):
        for j in range(j0, j1 + 1):
            for k in range(k0, k1 + 1):
                if (i, j, k) in v:
                    v[(i, j, k)] = mat


def carve(v, pred):
    for key in [k for k in v if pred(*k)]:
        del v[key]


def mirror_vox(v):
    return {(-1 - i, j, k): m for (i, j, k), m in v.items()}


def mirror_boxes(bs):
    return [(-x1, y0, z0, -x0, y1, z1, m) for (x0, y0, z0, x1, y1, z1, m) in bs]


FACES = [
    ((1, 0, 0), [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)]),
    ((-1, 0, 0), [(0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)]),
    ((0, 1, 0), [(0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)]),
    ((0, -1, 0), [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)]),
    ((0, 0, 1), [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]),
    ((0, 0, -1), [(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)]),
]


def cleanup():
    """Remove only the Mascot scene and MSC_ datablocks."""
    sc = bpy.data.scenes.get(SCENE)
    if sc:
        for o in list(sc.collection.all_objects):
            bpy.data.objects.remove(o, do_unlink=True)
        for c in list(sc.collection.children_recursive):
            if c.name.startswith(PREFIX):
                bpy.data.collections.remove(c)
        win = bpy.context.window
        if win and win.scene == sc:
            other = next((s for s in bpy.data.scenes if s != sc), None)
            if other:
                win.scene = other
        bpy.data.scenes.remove(sc)
    for o in list(bpy.data.objects):
        if o.name.startswith(PREFIX):
            bpy.data.objects.remove(o, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.armatures, bpy.data.lights,
                 bpy.data.cameras, bpy.data.worlds, bpy.data.collections):
        for d in list(coll):
            if d.name.startswith(PREFIX):
                coll.remove(d)


class Builder:
    def __init__(self):
        self.mats = {}
        self.objects = {}
        cleanup()
        self.scene = bpy.data.scenes.new(SCENE)
        self.col = bpy.data.collections.new(PREFIX + "Character")
        self.scene.collection.children.link(self.col)
        self.arm = None

    def mat(self, key):
        if key not in self.mats:
            self.mats[key] = make_material(key)
        return self.mats[key]

    def part(self, name, pivot, bone, vox=None, boxes=None, tags=None, hidden=False):
        """vox: {(i,j,k): mat}; boxes: [(x0,y0,z0,x1,y1,z1,mat)]; all in voxel units, world space."""
        vox = vox or {}
        boxes = boxes or []
        verts, vindex, faces, fmats, slots = [], {}, [], [], []

        def slot(m):
            if m not in slots:
                slots.append(m)
            return slots.index(m)

        def vid(p):
            key = (round(p[0], 4), round(p[1], 4), round(p[2], 4))
            if key not in vindex:
                vindex[key] = len(verts)
                verts.append(((key[0] - pivot[0]) * S, (key[1] - pivot[1]) * S, (key[2] - pivot[2]) * S))
            return vindex[key]

        for (i, j, k), m in vox.items():
            for (dx, dy, dz), corners in FACES:
                if (i + dx, j + dy, k + dz) in vox:
                    continue
                faces.append([vid((i + cx, j + cy, k + cz)) for cx, cy, cz in corners])
                fmats.append(slot(m))
        for (x0, y0, z0, x1, y1, z1, m) in boxes:
            lo, sz = (x0, y0, z0), (x1 - x0, y1 - y0, z1 - z0)
            for _, corners in FACES:
                faces.append([vid(tuple(lo[a] + c[a] * sz[a] for a in range(3))) for c in corners])
                fmats.append(slot(m))

        me = bpy.data.meshes.new(PREFIX + name)
        me.from_pydata(verts, [], faces)
        for m in slots:
            me.materials.append(self.mat(m))
        me.polygons.foreach_set("material_index", fmats)
        me.update()
        ob = bpy.data.objects.new(PREFIX + name, me)
        ob.location = Vector(pivot) * S
        self.col.objects.link(ob)
        ob["bone"] = bone
        for k, val in (tags or {}).items():
            ob[k] = val
        if hidden:
            ob.hide_viewport = True
            ob.hide_render = True
        self.objects[name] = ob
        return ob

    # ------------------------------------------------------------ rig
    def rig(self, bones):
        """bones: [(name, parent, head, tail)] in voxel units.
        Edit mode needs the window to show our scene: switch for this call only, then restore."""
        ad = bpy.data.armatures.new(PREFIX + "Rig")
        arm = bpy.data.objects.new(PREFIX + "Rig", ad)
        self.col.objects.link(arm)
        self.arm = arm
        win = bpy.context.window
        prev_scene = win.scene
        vl = self.scene.view_layers[0]
        try:
            win.scene = self.scene
            vl.objects.active = arm
            arm.select_set(True)
            with bpy.context.temp_override(window=win, scene=self.scene, view_layer=vl, active_object=arm, object=arm):
                bpy.ops.object.mode_set(mode="EDIT")
                eb = ad.edit_bones
                for name, parent, head, tail in bones:
                    b = eb.new(name)
                    b.head = Vector(head) * S
                    b.tail = Vector(tail) * S
                    b.roll = 0.0
                    if parent:
                        b.parent = eb[parent]
                bpy.ops.object.mode_set(mode="OBJECT")
            arm.select_set(False)
        finally:
            win.scene = prev_scene
        ad.display_type = "STICK"
        arm.show_in_front = True
        vl.update()
        for ob in self.objects.values():
            bname = ob["bone"]
            bone = ad.bones[bname]
            world = ob.matrix_basis.copy()
            ob.parent = arm
            ob.parent_type = "BONE"
            ob.parent_bone = bname
            pm = arm.matrix_world @ bone.matrix_local @ Matrix.Translation((0, bone.length, 0))
            ob.matrix_parent_inverse = pm.inverted()
            ob.matrix_basis = world


# ================================================================ character
# Body: x [-9, 9), y [-4, 4), z [3, 15). Front face at y = -4.
BX0, BX1 = -9, 8      # inclusive voxel indices
BY0, BY1 = -4, 3
BZ0, BZ1 = 3, 14
FY0, FY1 = -4.14, -4.0  # thin overlay slab on the front face


def eye_boxes(shape):
    """Boxes for the character's LEFT eye (+X side, viewer's right); mirrored for the right."""
    def px(x0, z0, x1, z1):
        return (x0, FY0, z0, x1, FY1, z1, "eye")
    if shape == "neutral":   # tall rectangle, like the sprite
        return [px(4, 9, 6, 12)]
    if shape == "blink":     # flat line, a bit wider than the open eye
        return [px(3.5, 10, 6.5, 11)]
    if shape == "happy":     # closed, upturned arc (a bold pixel "n")
        return [px(3.5, 11, 6.5, 12), px(3.5, 10, 4.5, 11), px(5.5, 10, 6.5, 11)]
    if shape == "squint":    # viewer's right eye: <  (mirrored gives >)
        return [px(5, 9, 6, 10), px(4, 10, 5, 11), px(5, 11, 6, 12)]
    raise ValueError(shape)


def build():
    B = Builder()
    BODY_PIVOT = (0, 0, BZ0)

    # ---------------- body ------------------------------------------------
    body = {}
    fill(body, BX0, BX1, BY0, BY1, BZ0, BZ1, "orange")
    paint(body, BX0, BX1, BY0, BY1, BZ0, BZ0, "orange_shadow")     # underside row
    paint(body, BX0, BX1, BY0, BY0, BZ1, BZ1, "orange_hi")         # top front rim
    B.part("Body", BODY_PIVOT, "body", body)

    # ---------------- eyes (swappable overlay layers) -----------------------
    for shape, hidden in (("neutral", False), ("blink", True), ("happy", True), ("squint", True)):
        bx = eye_boxes(shape)
        B.part("Face_Eyes_" + shape, BODY_PIVOT, "body", boxes=bx + mirror_boxes(bx),
               tags={"layer": "eyes", "expression": shape}, hidden=hidden)

    # ---------------- arms: 3 long, 3 tall, 4 deep stubs --------------------
    arm = {}
    fill(arm, 9, 11, -2, 1, 6, 8, "orange")
    paint(arm, 9, 11, -2, 1, 6, 6, "orange_shadow")
    B.part("Arm.L", (9, 0, 7.5), "arm.L", arm)
    B.part("Arm.R", (-9, 0, 7.5), "arm.R", mirror_vox(arm))

    # ---------------- legs: four 2x2 pegs, 3 tall ---------------------------
    # Front view matches the sprite (four in a row); outer pair sits forward, inner pair back,
    # so the side view shows two legs and walk cycles have some depth.
    LEG_TOP = BZ0
    legs = (("outer", 6, -3), ("inner", 3, 1))   # (name, left-side x start, y start); right mirrored
    for nm, x0, y0 in legs:
        leg = {}
        fill(leg, x0, x0 + 1, y0, y0 + 1, 0, LEG_TOP - 1, "orange_shadow")
        cx, cy = x0 + 1, y0 + 1
        B.part("Leg_%s.L" % nm.capitalize(), (cx, cy, LEG_TOP), "leg_%s.L" % nm, leg)
        B.part("Leg_%s.R" % nm.capitalize(), (-cx, cy, LEG_TOP), "leg_%s.R" % nm, mirror_vox(leg))

    # ---------------- rig -------------------------------------------------
    bones = [
        ("root", None, (0, 0, 0), (0, 0, 2)),
        ("body", "root", (0, 0, BZ0), (0, 0, BZ1 + 1)),
    ]
    for s, sx in ((".L", 1), (".R", -1)):
        bones.append(("arm" + s, "body", (9 * sx, 0, 7.5), (12 * sx, 0, 7.5)))
        for nm, x0, y0 in legs:
            cx, cy = (x0 + 1) * sx, y0 + 1
            bones.append(("leg_%s%s" % (nm, s), "body", (cx, cy, LEG_TOP), (cx, cy, 0)))
    B.rig(bones)

    stage(B)
    return B


# ================================================================ lighting / camera
CAM_TARGET = (0, 0, 0.42)
VIEWS = {  # name: camera location (m)
    "front": (0.0, -5.8, 0.75),
    "three_quarter": (3.7, -4.5, 1.3),
    "side": (5.8, 0.0, 0.75),
    "back": (0.0, 5.8, 0.75),
}


def stage(B):
    sc = B.scene
    w = bpy.data.worlds.new(PREFIX + "World")
    try:
        w.use_nodes = True
    except Exception:
        pass
    bg = next((n for n in w.node_tree.nodes if n.type == "BACKGROUND"), None)
    if bg:
        bg.inputs[0].default_value = hex_rgba("#C9D3E0")
        bg.inputs[1].default_value = 0.9
    sc.world = w

    def light(name, kind, energy, loc, rot, **kw):
        ld = bpy.data.lights.new(PREFIX + name, kind)
        ld.energy = energy
        for k, v in kw.items():
            try:
                setattr(ld, k, v)
            except Exception:
                pass
        ob = bpy.data.objects.new(PREFIX + name, ld)
        ob.location = loc
        ob.rotation_euler = rot
        sc.collection.objects.link(ob)
        return ob

    light("Key", "SUN", 2.2, (2, -3, 4), (0.85, 0.0, 0.6), angle=0.6)
    light("Fill", "SUN", 0.6, (-3, -2, 2), (1.1, 0.0, -0.9), angle=1.0)

    cd = bpy.data.cameras.new(PREFIX + "Camera")
    cd.lens = 85
    cam = bpy.data.objects.new(PREFIX + "Camera", cd)
    cam.location = VIEWS["three_quarter"]
    sc.collection.objects.link(cam)
    tgt = bpy.data.objects.new(PREFIX + "Camera_Target", None)
    tgt.location = CAM_TARGET
    tgt.empty_display_size = 0.1
    sc.collection.objects.link(tgt)
    c = cam.constraints.new("TRACK_TO")
    c.target = tgt
    sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y = 1080, 1920
    try:
        sc.render.engine = "BLENDER_EEVEE"
    except TypeError:
        pass
    for attr, val in (("view_transform", "Standard"), ("look", "None")):
        try:
            setattr(sc.view_settings, attr, val)
        except Exception:
            pass
    for attr, val in (("use_gtao", True), ("gtao_distance", 0.25), ("use_fast_gi", True),
                      ("fast_gi_distance", 0.25), ("use_shadows", True), ("use_raytracing", False)):
        try:
            setattr(sc.eevee, attr, val)
        except Exception:
            pass


# ================================================================ preview renders
def render_views(outdir, views=None, prefix="mascot_", res=(540, 960), samples=16):
    """Render the Mascot scene from each named view to PNGs; the window's scene is untouched."""
    sc = bpy.data.scenes[SCENE]
    cam = bpy.data.objects[PREFIX + "Camera"]
    os.makedirs(outdir, exist_ok=True)
    old = (sc.render.resolution_x, sc.render.resolution_y, sc.render.filepath, tuple(cam.location))
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.image_settings.file_format = "PNG"
    try:
        sc.eevee.taa_render_samples = samples
    except Exception:
        pass
    paths = []
    try:
        for name in (views or list(VIEWS)):
            cam.location = VIEWS[name]
            sc.render.filepath = os.path.join(outdir, prefix + name + ".png")
            bpy.ops.render.render(write_still=True, scene=SCENE)
            paths.append(sc.render.filepath)
    finally:
        sc.render.resolution_x, sc.render.resolution_y, sc.render.filepath = old[:3]
        cam.location = old[3]
    return paths


if __name__ == "mascot":
    B = build()
    print("built", len(B.objects), "parts;", sum(len(o.data.polygons) for o in B.objects.values()), "faces")
