"""Builds "The Designer" voxel character in Blender (T-pose, rigid bone rig, no animation).

Run inside Blender:
    exec(compile(open(".../scene/characters/design-girl/scripts/designer.py").read(), "designer.py", "exec"), {"__name__": "designer"})
Everything is rebuilt from scratch in a scene called "Designer"; other scenes are untouched.

Conventions: 1 voxel = 0.04 m, Z up, the character faces -Y, so her LEFT is +X.
Voxel index i covers x in [i, i+1). All coordinates below are in voxel units.

Proportions ("more normal" pass): feet 0-2, shins 2-9, thighs 9-16 (hips at 16), torso 15-28,
neck 28, head 29-40 (11 tall, 12 wide, 11 deep), hood top 41, headphone band top 42.
Head is ~27.5% of the 40-voxel body height (1.60 m to the top of the hair, 1.68 m with band).

Variants (custom property "variant"): default is hood DOWN: Hood_Down + Hair_Bun +
Headphones_Head_HoodDown visible; Hood_Up, Headphones_Head (hood-up fit) and Headphones_Neck hidden.
Face layers (custom properties "layer" = eyes|brows|mouth, "expression" = name):
Face_<Eyes|Brows|Mouth>_<expression>; only *_neutral visible by default.
"""
import bpy
from mathutils import Matrix, Vector

S = 0.04  # metres per voxel
PREFIX = "DSG_"

PALETTE = {
    "skin": "#F2C9B0", "skin_shadow": "#E0A98E", "blush": "#E89A8F",
    "mouth": "#B5705F", "mouth_dark": "#5E3434", "sweat": "#BFE0F2",
    "hair": "#8A6143", "hair_hi": "#A87B58", "hair_shadow": "#5E3F2B",
    "iris": "#7C93A8", "pupil": "#2B2B33", "eye_hi": "#FFFFFF",
    "glasses": "#6E6259", "glasses_lo": "#6E6259", "lens": "#6E6259", "rivet": "#D9D6D0",
    "hoodie": "#F4F2EE", "hoodie_shadow": "#D9D6CF",
    "cup": "#E8A3A0", "cushion": "#F0965F", "band": "#EE9E78", "stem": "#C8CCD2",
    "ring": "#D4A84A", "watch": "#1E1E1E", "watch_face": "#33414F",
    "jeans": "#9DB2CC", "jeans_shadow": "#8399B6",
    "sneaker": "#F7F7F7", "sole": "#DCDCDC",
}
ALPHA = {"glasses": 0.85, "glasses_lo": 0.55, "lens": 0.1}

EXPRESSIONS = ["neutral", "smile", "shocked", "panic", "hmm", "delighted", "eyeroll", "sleepy"]


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
    a = ALPHA.get(key, 1.0)
    col = hex_rgba(PALETTE[key], 1.0)
    bsdf.inputs["Base Color"].default_value = col
    bsdf.inputs["Roughness"].default_value = 1.0
    for name in ("Specular IOR Level", "Specular"):
        if name in bsdf.inputs:
            bsdf.inputs[name].default_value = 0.0
    if a < 1.0:
        bsdf.inputs["Alpha"].default_value = a
        for attr, val in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND"),
                          ("use_backface_culling", False)):
            try:
                setattr(m, attr, val)
            except Exception:
                pass
    m.diffuse_color = col[:3] + (a,)
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


N26 = [(a, b, c) for a in (-1, 0, 1) for b in (-1, 0, 1) for c in (-1, 0, 1) if (a, b, c) != (0, 0, 0)]


def dilate(cells):
    out = set()
    for (i, j, k) in cells:
        for a, b, c in N26:
            out.add((i + a, j + b, k + c))
    return out - set(cells)


FACES = [
    ((1, 0, 0), [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)]),
    ((-1, 0, 0), [(0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)]),
    ((0, 1, 0), [(0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)]),
    ((0, -1, 0), [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)]),
    ((0, 0, 1), [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]),
    ((0, 0, -1), [(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)]),
]


class Builder:
    def __init__(self, scene_name="Designer"):
        self.mats = {}
        self.objects = {}
        self.cleanup(scene_name)
        self.scene = bpy.data.scenes.new(scene_name)
        self.col = bpy.data.collections.new(PREFIX + "Character")
        self.scene.collection.children.link(self.col)
        self.arm = None

    @staticmethod
    def cleanup(scene_name):
        sc = bpy.data.scenes.get(scene_name)
        if sc:
            for o in list(sc.collection.all_objects):
                bpy.data.objects.remove(o, do_unlink=True)
            for c in list(sc.collection.children_recursive):
                bpy.data.collections.remove(c)
            if len(bpy.data.scenes) > 1:
                bpy.data.scenes.remove(sc)
            else:
                sc.name = scene_name + "_old"
        for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.armatures, bpy.data.lights,
                     bpy.data.cameras, bpy.data.worlds, bpy.data.collections):
            for d in list(coll):
                if d.name.startswith(PREFIX) and d.users == 0:
                    coll.remove(d)
        for d in list(bpy.data.materials):
            if d.name.startswith(PREFIX):
                bpy.data.materials.remove(d)

    def mat(self, key):
        if key not in self.mats:
            self.mats[key] = make_material(key)
        return self.mats[key]

    def part(self, name, pivot, bone, vox=None, boxes=None, polys=None, offset=(0, 0, 0), tags=None, hidden=False,
             cell=1.0):
        """vox: {(i,j,k): mat} on a grid of `cell` voxels; boxes: [(x0,y0,z0,x1,y1,z1,mat)];
        polys: [(points, faces, mat)] raw polygons; all in voxel units (world, before pivot)."""
        vox = vox or {}
        boxes = boxes or []
        polys = polys or []
        verts, vindex, faces, fmats = [], {}, [], []
        slots = []

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
                faces.append([vid((offset[0] + (i + cx) * cell, offset[1] + (j + cy) * cell, offset[2] + (k + cz) * cell))
                              for cx, cy, cz in corners])
                fmats.append(slot(m))
        for (x0, y0, z0, x1, y1, z1, m) in boxes:
            lo, sz = (x0, y0, z0), (x1 - x0, y1 - y0, z1 - z0)
            for _, corners in FACES:
                faces.append([vid(tuple(lo[a] + c[a] * sz[a] for a in range(3))) for c in corners])
                fmats.append(slot(m))
        for pts, pfaces, m in polys:
            ids = [vid(p) for p in pts]
            for f in pfaces:
                faces.append([ids[n] for n in f])
                fmats.append(slot(m))

        me = bpy.data.meshes.new(PREFIX + name)
        me.from_pydata(verts, [], faces)
        for m in slots:
            me.materials.append(self.mat(m))
        me.polygons.foreach_set("material_index", fmats)
        me.update()
        ob = bpy.data.objects.new(name, me)
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
        """bones: [(name, parent, head, tail)] in voxel units."""
        ad = bpy.data.armatures.new(PREFIX + "Rig")
        arm = bpy.data.objects.new("Designer_Rig", ad)
        self.col.objects.link(arm)
        self.arm = arm
        win = bpy.context.window
        win.scene = self.scene
        vl = self.scene.view_layers[0]
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
        arm.select_set(False)


# ================================================================ layout constants
HEAD_I = (-6, 5)      # 12 wide
HEAD_J = (-6, 4)      # 11 deep, face plane at y = -6
HEAD_K = (29, 39)     # 11 tall, chin row 29, hair top 39 (top surface z = 40)
HEAD_PIVOT = (0, 0, 28)
FACE_Y = -6.0
EYE_X = (1, -4)       # left eye x 1..4, right eye x -4..-1
EYE_TOP = 34.0        # eyes cover z 32..34 (3 wide x 2 tall)
TORSO_PIVOT = (0, 0, 16)


def head_dist(i, j, k):
    di = min(i - HEAD_I[0], HEAD_I[1] - i)
    return di, j - HEAD_J[0], HEAD_J[1] - j, HEAD_K[1] - k, k - HEAD_K[0]


def rounded_core(i, j, k):
    """Rounded head volume used for both the head and the hood shell."""
    di, djf, djb, dk, _ = head_dist(i, j, k)
    return not (di + djb < 2 or di + dk < 2 or djb + dk < 2)


# ---------------------------------------------------------------- face overlays
def px(x, z, w, hgt, m, y0=FACE_Y - 0.1):
    return (x, y0, z, x + w, FACE_Y, z + hgt, m)


FRONT1 = FACE_Y - 0.14   # layer in front of a px() overlay
FRONT2 = FACE_Y - 0.18
CMAP = {"h": "eye_hi", "p": "pupil", "i": "iris", "w": "eye_hi", "s": "skin_shadow"}


def eye_grid(rows, top=EYE_TOP, cell=1.0):
    out = []
    for ex in EYE_X:
        for r, row in enumerate(rows):
            for c, ch in enumerate(row):
                if ch != ".":
                    out.append(px(ex + c * cell, top - (r + 1) * cell, cell, cell, CMAP[ch]))
    return out


def eye_boxes(fn):
    out = []
    for ex in EYE_X:
        out += fn(ex)
    return out


BROW_DZ = 0.5   # brows lifted above the large round frames' top bar


def brows(lin, lout, rin, rout, t=0.38):
    """z of the inner and outer half of her left (+X) and right (-X) brow (before BROW_DZ)."""
    m = "hair_hi"
    lin, lout, rin, rout = (z + BROW_DZ for z in (lin, lout, rin, rout))
    return [px(1.0, lin, 1.4, t, m), px(2.4, lout, 1.4, t, m),
            px(-2.4, rin, 1.4, t, m), px(-3.8, rout, 1.4, t, m)]


def expression_layers():
    E = {}
    # eyes: rows top -> bottom, 3 columns from the eye's -X edge (same pattern both eyes: shared light)
    E["neutral"] = dict(
        eyes=eye_grid(["hpi", "ipi"]),
        brows=brows(35.0, 35.15, 35.0, 35.0),
        mouth=[px(-1, 30.1, 2, 0.35, "mouth"), px(-1.5, 30.45, 0.5, 0.35, "mouth"), px(1, 30.45, 0.5, 0.35, "mouth")])
    E["smile"] = dict(
        eyes=eye_grid(["hpi", ".p."]) + eye_boxes(lambda ex: [px(ex, 31.6, 3, 0.3, "skin_shadow")]),
        brows=brows(35.15, 35.25, 35.15, 35.25),
        mouth=[px(-1.25, 29.95, 2.5, 0.4, "mouth"), px(-1.85, 30.35, 0.6, 0.4, "mouth"), px(1.25, 30.35, 0.6, 0.4, "mouth"),
               px(-2.2, 30.75, 0.35, 0.3, "mouth"), px(1.85, 30.75, 0.35, 0.3, "mouth")])
    E["shocked"] = dict(
        eyes=eye_grid(["wpw", "www"]),
        brows=brows(35.75, 35.75, 35.75, 35.75),
        mouth=[px(-0.8, 29.5, 1.6, 1.5, "mouth"), px(-0.5, 29.75, 1.0, 1.0, "mouth_dark", y0=FRONT1)])
    E["panic"] = dict(
        eyes=eye_grid(["www", "wpw"]) + [px(4.4, 36.1, 0.5, 0.8, "sweat"), px(4.55, 36.9, 0.2, 0.25, "sweat")],
        brows=brows(35.8, 35.3, 35.8, 35.3),
        mouth=[px(-1.6, 29.5, 3.2, 1.3, "mouth"), px(-1.35, 29.65, 2.7, 1.0, "mouth_dark", y0=FRONT1),
               px(-1.1, 30.35, 2.2, 0.3, "eye_hi", y0=FRONT2)])
    E["hmm"] = dict(
        eyes=eye_boxes(lambda ex: [px(ex, 33.45, 3, 0.55, "skin_shadow"), px(ex, 33.05, 3, 0.4, "pupil")])
        + eye_grid(["iip"], top=33.05, cell=1.0),      # half-lidded, glancing to her left
        brows=brows(35.55, 35.75, 34.85, 34.85),
        mouth=[px(-0.3, 30.25, 1.7, 0.35, "mouth"), px(-0.8, 30.05, 0.5, 0.35, "mouth")])
    E["delighted"] = dict(
        eyes=eye_boxes(lambda ex: [px(ex, 32.6, 0.75, 0.5, "pupil"), px(ex + 0.6, 33.1, 1.8, 0.5, "pupil"),
                                   px(ex + 2.25, 32.6, 0.75, 0.5, "pupil")]),
        brows=brows(35.45, 35.4, 35.45, 35.4),
        mouth=[px(-1.6, 30.4, 3.2, 0.55, "mouth_dark"), px(-1.1, 29.85, 2.2, 0.55, "mouth_dark"),
               px(-0.6, 29.85, 1.2, 0.35, "blush", y0=FRONT1)])
    E["eyeroll"] = dict(
        eyes=eye_grid(["ipi", "www"]),
        brows=brows(35.35, 35.5, 34.9, 34.9),
        mouth=[px(-1.2, 30.25, 2.0, 0.35, "mouth"), px(0.8, 29.95, 0.5, 0.3, "mouth")])
    E["sleepy"] = dict(
        eyes=eye_boxes(lambda ex: [px(ex, 33.0, 3, 0.75, "skin_shadow"), px(ex, 32.6, 3, 0.4, "pupil"),
                                   px(ex + 0.5, 32.1, 2, 0.5, "iris")]),
        brows=brows(34.8, 34.65, 34.8, 34.65),
        mouth=[px(-0.4, 29.85, 0.8, 0.7, "mouth"), px(-0.2, 30.0, 0.4, 0.4, "mouth_dark", y0=FRONT1)])
    return E


# ---------------------------------------------------------------- glasses (voxel, round panto)
# After the user's reference photo: large rounded frames, flat-ish top bar, rounded bottom, a small
# upsweep at the outer top corner, translucent smoky acetate that is lighter toward the bottom,
# keyhole bridge, metal rivet at the outer top corner, clear lenses. Built on a half-voxel grid
# (GL_CELL) so it stays stair-stepped voxel art while the frame is only 0.5 voxel thick.
GL_CELL = 0.5
GL_X0, GL_Z0 = 0.0, 30.5          # left lens: column 0 starts at x = 0, row 0 at z = 30.5 (cells of 0.5)
GL_Y = (-7.0, -6.5)               # frame depth: 0.5 voxel, floating 0.5 voxel in front of the face
GL_LENS_Y = (-6.78, -6.72)
# Frame cells of her LEFT lens per row (row 0 = bottom); columns 0..9 run from the nose to the temple.
GL_ROWS = {
    9: [8, 9],                     # upswept outer top corner
    8: list(range(1, 10)),         # top bar
    7: [0, 9], 6: [0, 9],          # inner side meets the other lens here = keyhole bridge
    5: [1, 9], 4: [1, 9], 3: [1, 9], 2: [1, 9],
    1: [2, 8],
    0: list(range(3, 8)),          # rounded bottom
}
GL_LENS = {7: (1, 8), 6: (1, 8), 5: (2, 8), 4: (2, 8), 3: (2, 8), 2: (2, 8), 1: (3, 7)}
GL_RIVET = (8, 8)                  # (col, row) recoloured light metal
GL_TEMPLE_ROW = 7
GL_LOW_ROWS = 4                    # rows below this use the lighter, more see-through acetate


def glasses_vox():
    v = {}
    y = int(round(GL_Y[0] / GL_CELL))
    X0, Z0 = int(GL_X0 / GL_CELL), int(GL_Z0 / GL_CELL)
    for r, cols in GL_ROWS.items():
        for c in cols:
            m = "rivet" if (c, r) == GL_RIVET else ("glasses" if r >= GL_LOW_ROWS else "glasses_lo")
            v[(X0 + c, y, Z0 + r)] = m
    zt = Z0 + GL_TEMPLE_ROW
    for X in range(X0 + 9, 13):                      # hinge out to the side of the head (x 4.5..6.5), set
        v[(X, y + 1, zt)] = "glasses"                # half a voxel behind the frame (clear of the hood rim)
    for Y in range(y + 1, -5):                       # temple arm back along the head (y -6.5..-2.5)
        v[(12, Y, zt)] = "glasses"
    v.update({(-1 - X, Y, Z): m for (X, Y, Z), m in v.items()})
    return v


def glasses_boxes():
    lens = []
    for r, (c0, c1) in GL_LENS.items():
        lens.append((GL_X0 + c0 * GL_CELL, GL_LENS_Y[0], GL_Z0 + r * GL_CELL,
                     GL_X0 + (c1 + 1) * GL_CELL, GL_LENS_Y[1], GL_Z0 + (r + 1) * GL_CELL, "lens"))
    return lens + mirror_boxes(lens)


# ================================================================ character
def build():
    B = Builder()
    (i0, i1), (j0, j1), (k0, k1) = HEAD_I, HEAD_J, HEAD_K

    # ---------------- head (skin + hair) 12 x 11 x 11, plus neck ----------
    h = {}
    fill(h, i0, i1, j0, j1, k0, k1, "skin")
    fill(h, -2, 1, -2, 1, 28, 28, "skin")                       # neck
    for (i, j, k) in list(h):                                   # hair shell (top, back, sides)
        if k >= 37 or (k >= 35 and j > j0) or (k >= 32 and j >= -3) or (k >= 30 and j >= 1):
            h[(i, j, k)] = "hair"
    for i in (i0, i1):
        fill(h, i, i, j0, j0, 33, 36, "hair")                   # sideburns framing the face
    fill(h, i0, i1, j0, j0, 37, 38, "hair")                     # fringe
    for i in (-1, 0):
        h[(i, j0, 37)] = "skin"                                 # centre part notch
    for i in (-5, 4):                                           # loose strands framing the face
        fill(h, i, i, j0, j0, 32, 36, "hair")
        h[(i, j0, 32)] = "hair_hi"
    paint(h, -1, 0, j0, 1, k1, k1, "hair_shadow")               # part line on top
    paint(h, -1, 0, j0, j0, 38, 38, "hair_shadow")
    paint(h, -4, -3, -4, 2, k1, k1, "hair_hi")                  # highlights
    paint(h, 2, 3, -3, 1, k1, k1, "hair_hi")
    paint(h, -3, -2, j0, j0, 38, 38, "hair_hi")
    paint(h, 2, 2, j0, j0, 37, 38, "hair_hi")
    for (i, j, k), m in list(h.items()):                        # strand texture on the back and sides
        if m != "hair" or k >= k1:
            continue
        if j == j1 and i in (-4, 3) and k >= 35:              # two soft highlight strands on the back
            h[(i, j, k)] = "hair_hi"
        elif i in (i0, i1) and j >= -3 and j % 3 == 0 and k >= 33:
            h[(i, j, k)] = "hair_hi"
    paint(h, i0, i1, j1, j1, 30, 30, "hair_shadow")             # nape
    carve(h, lambda i, j, k: k >= k0 and (
        not rounded_core(i, j, k)
        or (head_dist(i, j, k)[0] == 0 and head_dist(i, j, k)[1] == 0)          # front vertical corners
        or (k == k0 and (head_dist(i, j, k)[0] == 0 or j == j1))                # jaw underside
        or (k == k0 and j == j0 and head_dist(i, j, k)[0] <= 1)))
    head_boxes = [
        (-0.5, FACE_Y - 0.1, 31.25, 0.5, FACE_Y, 31.75, "skin_shadow"),        # nose (shading only)
        px(2.5, 29.95, 1.8, 0.5, "blush"), px(-4.3, 29.95, 1.8, 0.5, "blush"),   # cheeks (below the frames)
        px(1.75, 30.25, 0.35, 0.35, "skin_shadow"), px(2.2, 30.65, 0.35, 0.35, "skin_shadow"),  # freckles
        px(-2.15, 30.4, 0.35, 0.35, "skin_shadow"),
    ]
    B.part("Head", HEAD_PIVOT, "head", h, head_boxes)

    # ---------------- face layers (swappable; neutral visible) -------------
    MOUTH_DZ = -0.35                                            # mouths sit a little lower, clear of the frames
    for name, layers in expression_layers().items():
        mouth = [(x0, y0, z0 + MOUTH_DZ, x1, y1, z1 + MOUTH_DZ, m) for (x0, y0, z0, x1, y1, z1, m) in layers["mouth"]]
        for layer, boxes in (("Eyes", layers["eyes"]), ("Brows", layers["brows"]), ("Mouth", mouth)):
            B.part("Face_%s_%s" % (layer, name), HEAD_PIVOT, "head", boxes=boxes,
                   tags={"layer": layer.lower(), "expression": name}, hidden=(name != "neutral"))

    # ---------------- glasses (voxel round panto, half-voxel grid) ------------------------------------
    B.part("Glasses", HEAD_PIVOT, "head", glasses_vox(), glasses_boxes(), cell=GL_CELL)

    # ---------------- hair bun (hood down) ---------------------------------
    bun = {}
    BJ = j1 + 1                                            # bun sits on the back of the head, low
    fill(bun, -3, 2, BJ, BJ + 2, 31, 35, "hair")
    carve(bun, lambda i, j, k: j > BJ and (i in (-3, 2)) + (j == BJ + 2) + (k in (31, 35)) >= 2)
    fill(bun, -2, 1, BJ + 3, BJ + 3, 32, 34, "hair")        # rounded cap
    paint(bun, -3, 2, BJ, BJ + 3, 35, 35, "hair_hi")        # lit top
    paint(bun, -2, 1, BJ + 2, BJ + 3, 32, 34, "hair_hi")    # lit back of the bun
    paint(bun, -3, 2, BJ, BJ + 2, 31, 31, "hair_shadow")    # underside
    paint(bun, -3, 2, BJ, BJ, 31, 35, "hair_shadow")        # tucked base
    for c, m in (((3, BJ + 1, 34), "hair"), ((-4, BJ + 1, 33), "hair_hi"), ((1, BJ + 1, 36), "hair_hi"),
                 ((-2, BJ + 2, 36), "hair"), ((2, BJ + 2, 30), "hair"), ((-3, BJ + 3, 34), "hair")):
        bun[c] = m                                         # messy tufts
    B.part("Hair_Bun", HEAD_PIVOT, "head", bun, tags={"variant": "hood_down"})

    # ---------------- hood up: 1-voxel shell around the rounded head -------
    core = {(i, j, k) for i in range(i0, i1 + 1) for j in range(j0, j1 + 1) for k in range(28, k1 + 1)
            if rounded_core(i, j, k)}
    hood = {c: "hoodie" for c in dilate(core) if c[2] >= 28}
    carve(hood, lambda i, j, k: j == j0 - 1 and -5 <= i <= 4 and k <= 37 and not (i in (-5, 4) and k == 37))
    paint(hood, i0 - 1, i1 + 1, j0 - 1, j0 - 1, 28, 41, "hoodie_shadow")   # rim
    paint(hood, -1, 0, j1 + 1, j1 + 1, 28, 41, "hoodie_shadow")           # back seam
    B.part("Hood_Up", HEAD_PIVOT, "head", hood, tags={"variant": "hood_up"}, hidden=True)

    # ---------------- hood down: collar + bundle on the upper back --------
    hd = {}
    fill(hd, -3, 2, -3, 2, 28, 28, "hoodie")               # collar ring around the neck
    carve(hd, lambda i, j, k: -2 <= i <= 1 and -2 <= j <= 1)
    widths = {28: 6, 27: 6, 26: 6, 25: 5, 24: 5, 23: 4, 22: 3, 21: 2}   # half-widths: rounded point at the bottom
    for k, hw in widths.items():
        fill(hd, -hw, hw - 1, 4, 4, k, k, "hoodie")        # layer against the back
        if k >= 22:
            fill(hd, -hw + 1, hw - 2, 5, 5, k, k, "hoodie")  # outer layer
    fill(hd, -3, 2, 6, 6, 24, 27, "hoodie")                # puff of the folded hood
    carve(hd, lambda i, j, k: j == 6 and i in (-3, 2) and k in (24, 27))
    fill(hd, -6, 5, 2, 3, 28, 28, "hoodie")                # neckline joins the collar
    paint(hd, -6, 5, 4, 4, 21, 27, "hoodie_shadow")        # inner layer peeks out as the hood's outline
    paint(hd, -4, 3, 4, 5, 28, 28, "hoodie_shadow")        # open mouth of the hood facing up
    paint(hd, -1, 0, 6, 6, 24, 27, "hoodie_shadow")        # centre seam
    B.part("Hood_Down", TORSO_PIVOT, "torso", hd, tags={"variant": "hood_down"})

    # ---------------- headphones on head (over the hood) -------------------
    # AirPods-Max style: tall rounded-rectangle pink cups, peach-orange cushions, a wide coral
    # canopy band and thin silver stems entering the top of each cup.
    CUP_J, CUP_K = (-3, 1), (30, 36)                         # cup footprint: 5 deep x 7 tall

    def cup_side():
        v = {}
        (ja, jb), (ka, kb) = CUP_J, CUP_K
        fill(v, 6, 7, ja, jb, ka, kb, "cushion")              # 2-thick ear cushion
        fill(v, 8, 8, ja, jb, ka, kb, "cup")
        carve(v, lambda i, j, k: j in (ja, jb) and k in (ka, kb))      # rounded corners
        fill(v, 9, 9, ja + 1, jb - 1, ka + 1, kb - 1, "cup")             # flat outer face
        return v

    def stem_boxes(bx, ztop):
        """Silver stem from the band end (x = bx, bottom at ztop) into the top of the +X cup."""
        cx, cy, z0 = 8.9, -0.5, CUP_K[1] + 1.0                # cup top centre
        r = 0.2
        return [(bx - r, cy - r, z0 + 0.35, bx + r, cy + r, ztop, "stem"),        # down from the band
                (min(bx, cx) - r, cy - r, z0 + 0.35, max(bx, cx) + r, cy + r, z0 + 0.75, "stem"),
                (cx - r, cy - r, z0, cx + r, cy + r, z0 + 0.75, "stem")]          # into the cup

    def headphones(solid, kmin):
        hp = cup_side()
        hp.update(mirror_vox(hp))
        band = {}
        for (i, j, k) in solid:                              # canopy arc hugging the head/hood contour
            if not -2 <= j <= 1:
                continue
            for a in (-1, 0, 1):
                for c in (-1, 0, 1):
                    q = (i + a, j, k + c)
                    if q[2] >= kmin and q not in solid and q not in hp:
                        band[q] = "band"
        hp.update(band)
        low = min(k for (_, _, k) in band)
        bx = max(i for (i, _, k) in band if k == low) + 0.5   # x centre of the band's lowest voxel (+X side)
        st = stem_boxes(bx, low + 0.3)
        return hp, st + mirror_boxes(st)

    hood_solid = set(core) | set(hood)
    head_solid = set(h) | {(i, j, k) for (i, j, k) in core if k >= 30}   # head volume incl. carved-in interior
    v, bx = headphones(hood_solid, 38)
    B.part("Headphones_Head", HEAD_PIVOT, "head", v, bx,
           tags={"variant": "headphones_head", "fit": "hood_up"}, hidden=True)
    v, bx = headphones(head_solid, 38)
    B.part("Headphones_Head_HoodDown", HEAD_PIVOT, "head", v, bx,
           tags={"variant": "headphones_head", "fit": "hood_down"})

    # ---------------- headphones around the neck (same cups, facing forward on the chest)
    hn = {}
    for (i, j, k), m in cup_side().items():                 # rotate the side cup: x(out) -> -y(front), y -> x
        hn[(j + 4, -i + 1, k - 10)] = m                     # x 1..6; cushion y -6..-4, cup front y -8..-6
    hn.update(mirror_vox(hn))
    sb = [(3.3, -6.7, 27.0, 3.7, -6.3, 28.6, "stem"),       # stems up from the cup tops
          (3.3, -6.7, 28.2, 3.7, -2.6, 28.6, "stem"),       # back under the chin to the band
          (2.3, -3.0, 28.1, 3.7, 3.2, 28.7, "band"),        # band beside and behind the neck (mostly hidden)
          ]
    sb = sb + mirror_boxes(sb) + [(-2.3, 2.6, 28.1, 2.3, 3.2, 28.7, "band")]
    B.part("Headphones_Neck", TORSO_PIVOT, "torso", hn, sb, tags={"variant": "headphones_neck"}, hidden=True)

    # ---------------- torso (oversized hoodie) ----------------------------
    t = {}
    fill(t, -7, 6, -4, 3, 15, 27, "hoodie")
    carve(t, lambda i, j, k: i in (-7, 6) and j in (-4, 3))
    carve(t, lambda i, j, k: k == 27 and (i in (-7, 6) or j in (-4, 3)))
    paint(t, -7, 6, -4, 3, 15, 15, "hoodie_shadow")        # ribbed hem
    paint(t, -4, 3, -4, -4, 17, 19, "hoodie_shadow")       # kangaroo pocket
    paint(t, -3, 2, -4, -4, 20, 20, "hoodie_shadow")
    for i in (-2, 1):
        paint(t, i, i, -4, -4, 23, 26, "hoodie_shadow")    # drawstrings
    B.part("Torso", TORSO_PIVOT, "torso", t)

    # ---------------- arms (T-pose along X) -------------------------------
    ua = {}
    fill(ua, 7, 12, -2, 1, 23, 26, "hoodie")
    fa = {}
    fill(fa, 13, 18, -2, 1, 23, 26, "hoodie")
    paint(fa, 18, 18, -2, 1, 23, 26, "hoodie_shadow")      # cuff (hand starts half inside it)
    hand = {}
    fill(hand, 0, 3, -1, 1, 0, 1, "skin")                  # palm down, fingers to +X
    hand[(1, -2, 0)] = "skin"                              # thumb (front)
    hand[(2, -2, 0)] = "skin"
    HAND_OFF = (18.5, -0.5, 24)
    B.part("UpperArm.L", (7, 0, 25), "upper_arm.L", ua)
    B.part("UpperArm.R", (-7, 0, 25), "upper_arm.R", mirror_vox(ua))
    B.part("Forearm.L", (13, 0, 25), "forearm.L", fa)
    B.part("Forearm.R", (-13, 0, 25), "forearm.R", mirror_vox(fa))
    B.part("Hand.L", (19, 0, 25), "hand.L", hand, offset=HAND_OFF)
    B.part("Hand.R", (-19, 0, 25), "hand.R", mirror_vox(hand), offset=(-HAND_OFF[0], HAND_OFF[1], HAND_OFF[2]))

    # watch: her left wrist (+X); ring: her right hand (-X), index finger
    watch = [(19.0, -1.62, 23.88, 19.9, 1.62, 26.12, "watch"), (19.1, -0.8, 26.12, 19.8, 0.8, 26.25, "watch_face")]
    B.part("Watch", (19, 0, 25), "hand.L", boxes=watch)
    ring = [(-21.75, -1.58, 23.88, -21.0, -0.42, 26.12, "ring")]
    B.part("Ring", (-19, 0, 25), "hand.R", boxes=ring)

    # ---------------- legs ------------------------------------------------
    LEG_OFF = (0.5, -0.5, 0)
    th = {}
    fill(th, 0, 4, -2, 2, 9, 15, "jeans")
    sh = {}
    fill(sh, 0, 4, -2, 2, 2, 8, "jeans")
    paint(sh, 0, 4, -2, 2, 2, 2, "jeans_shadow")           # hem
    ft = {}
    fill(ft, 0, 4, -4, 1, 0, 1, "sneaker")
    paint(ft, 0, 4, -4, 1, 0, 0, "sole")
    carve(ft, lambda i, j, k: k == 1 and j == -4)          # sloped toe
    carve(ft, lambda i, j, k: j == -4 and i in (0, 4))     # rounded toe
    for nm, v, piv, bone in (("Thigh", th, (3, 0, 16), "thigh"), ("Shin", sh, (3, 0, 9), "shin"),
                             ("Foot", ft, (3, 0, 2), "foot")):
        B.part(nm + ".L", piv, bone + ".L", v, offset=LEG_OFF)
        B.part(nm + ".R", (-piv[0], piv[1], piv[2]), bone + ".R", mirror_vox(v), offset=(-LEG_OFF[0], LEG_OFF[1], 0))

    # ---------------- rig -------------------------------------------------
    bones = [
        ("root", None, (0, 0, 0), (0, 0, 3)),
        ("hips", "root", (0, 0, 16), (0, 0, 19)),
        ("torso", "hips", (0, 0, 16), (0, 0, 28)),
        ("head", "torso", (0, 0, 28), (0, 0, 40)),
    ]
    for s, sx in ((".L", 1), (".R", -1)):
        bones += [
            ("upper_arm" + s, "torso", (7 * sx, 0, 25), (13 * sx, 0, 25)),
            ("forearm" + s, "upper_arm" + s, (13 * sx, 0, 25), (19 * sx, 0, 25)),
            ("hand" + s, "forearm" + s, (19 * sx, 0, 25), (22.5 * sx, 0, 25)),
            ("thigh" + s, "hips", (3 * sx, 0, 16), (3 * sx, 0, 9)),
            ("shin" + s, "thigh" + s, (3 * sx, 0, 9), (3 * sx, 0, 2)),
            ("foot" + s, "shin" + s, (3 * sx, 0, 2), (3 * sx, -4, 0.5)),
        ]
    B.rig(bones)

    stage(B)
    return B


# ================================================================ lighting / camera
def stage(B):
    sc = B.scene
    w = bpy.data.worlds.new(PREFIX + "World")
    try:
        w.use_nodes = True
    except Exception:
        pass
    bg = next((n for n in w.node_tree.nodes if n.type == "BACKGROUND"), None)
    if bg:
        bg.inputs[0].default_value = hex_rgba("#F2F4F8")
        bg.inputs[1].default_value = 0.82
    sc.world = w

    def light(name, kind, energy, rot, **kw):
        ld = bpy.data.lights.new(PREFIX + name, kind)
        ld.energy = energy
        for k, v in kw.items():
            try:
                setattr(ld, k, v)
            except Exception:
                pass
        ob = bpy.data.objects.new(name, ld)
        ob.location = (0, 0, 3)
        ob.rotation_euler = rot
        sc.collection.objects.link(ob)
        return ob

    light("Key", "SUN", 1.12, (0.8, 0.0, 0.55), angle=0.7)      # front-left-above (camera side)
    light("Fill", "SUN", 0.3, (1.15, 0.0, -0.9), angle=1.0)
    light("Rim", "SUN", 0.5, (-0.9, 0.0, 0.3), angle=0.8)      # from behind so the back reads

    cd = bpy.data.cameras.new(PREFIX + "Camera")
    cd.lens = 85
    cam = bpy.data.objects.new("Camera", cd)
    cam.location = (2.5, -7.9, 1.35)
    sc.collection.objects.link(cam)
    tgt = bpy.data.objects.new("Camera_Target", None)
    tgt.location = (0, 0, 0.84)
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
    for attr, val in (("use_gtao", True), ("gtao_distance", 0.2), ("use_shadows", True), ("use_raytracing", False)):
        try:
            setattr(sc.eevee, attr, val)
        except Exception:
            pass


def show(objects=None, expression=None, hood=None, headphones=None):
    """Toggle variants / expressions. hood: 'up'|'down'; headphones: 'head'|'neck'."""
    sc = bpy.data.scenes["Designer"]
    if hood is None:
        hood = "down" if sc.objects["Hood_Up"].hide_viewport else "up"
    if headphones is None:
        headphones = "neck" if sc.objects["Headphones_Neck"].hide_viewport is False else "head"
    for ob in sc.objects:
        hide = None
        if expression and "expression" in ob.keys():
            hide = ob["expression"] != expression
        v = ob.get("variant")
        if v in ("hood_up", "hood_down"):
            hide = v != ("hood_" + hood)
        if v in ("headphones_head", "headphones_neck"):
            hide = v != ("headphones_" + headphones)
            if v == "headphones_head" and not hide:
                hide = ob.get("fit") != ("hood_" + hood)
        if hide is not None:
            ob.hide_viewport = hide
            ob.hide_render = hide


if __name__ == "designer":
    B = build()
    print("built", len(B.objects), "parts;", sum(len(o.data.polygons) for o in B.objects.values()), "faces")
